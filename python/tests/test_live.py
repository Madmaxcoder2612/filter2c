"""Tests for the live check with the board's analog input.

No board is available here, so the live sketch is compiled on the PC against a small
stand-in for the Arduino functions (see test_target.py) and its output is fed to the
checker. Synthetic logs cover the failure cases. A real board log is checked in
test_live_board_result.py once one has been recorded.
"""
import subprocess
import shutil
from pathlib import Path

import numpy as np
import pytest
from scipy import signal

from filter2c import butterworth_lowpass, notch
from filter2c.cli import main
from filter2c.live import check_live_log, create_live_sketch, parse_live_log
from filter2c.target import check_board_log, create_sketch
from filter2c.verify import VerificationError
from test_target import ARDUINO_STUB, needs_cpp

ROOT = Path(__file__).resolve().parents[2]


def make_live_folder(tmp_path, design=None, name="lp40", folder="Live"):
    design = design or butterworth_lowpass(4, 40, 1000)
    sketch = tmp_path / folder
    create_live_sketch(design, name, sketch)
    return design, sketch


def square_wave(n=2000):
    return np.where((np.arange(n) // 100) % 2, 4000, 100)


def synthetic_log(design, raw, period_us=1000.0, start_us=0, prefix="", tamper=None):
    """A log in exactly the format the sketch prints."""
    n = raw.size
    t = (start_us + np.round(period_us * np.arange(n))).astype(np.int64) % (2 ** 32)
    out = signal.sosfilt(design.sos, raw.astype(float))
    if tamper is not None:
        out[tamper] += 50.0
    lines = ["garbage before", f"{prefix}FILTER2C_LIVE_BEGIN"]
    lines += [f"{prefix}{int(t[i])},{int(raw[i])},{out[i]:.5f}" for i in range(n)]
    lines += [f"{prefix}FILTER2C_LIVE_END", "FILTER2C_LIVE_SAMPLES=%d" % n]
    return "\n".join(lines)


def run_live_sketch_on_pc(sketch: Path, tmp_path: Path) -> str:
    gpp = shutil.which("g++") or shutil.which("clang++")
    stub = tmp_path / "stub"
    stub.mkdir(exist_ok=True)
    (stub / "Arduino.h").write_text(ARDUINO_STUB, newline="\n")
    main_cpp = tmp_path / "main.cpp"
    main_cpp.write_text(
        f'#include "{(sketch / (sketch.name + ".ino")).as_posix()}"\n'
        "int main() { setup(); loop(); return 0; }\n", newline="\n")
    exe = tmp_path / "live.exe"
    build = subprocess.run(
        [gpp, "-std=c++11", "-Wall", "-Wextra", "-Werror", "-I", str(stub), "-I", str(sketch),
         str(main_cpp), "-o", str(exe)], capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    return subprocess.run([str(exe)], capture_output=True, text=True, check=True).stdout


# ---------------------------------------------------------------- the sketch folder

def test_live_sketch_folder_contents(tmp_path):
    _, sketch = make_live_folder(tmp_path)
    assert sorted(p.name for p in sketch.iterdir()) == sorted(
        ["Live.ino", "lp40.h", "filter2c.h", "filter2c_target.json"])
    ino = (sketch / "Live.ino").read_text(encoding="utf-8")
    assert "PERIOD_US = 1000ul" in ino and "SAMPLES = 2000u" in ino and "921600" in ino
    assert '"mode": "live"' in (sketch / "filter2c_target.json").read_text(encoding="utf-8")


@pytest.mark.parametrize("fs, ok", [(1000, True), (250, True), (500, True), (300, False),
                                    (7000, False)])
def test_sampling_rate_must_give_whole_microseconds(tmp_path, fs, ok):
    design = butterworth_lowpass(2, 20, fs)
    if ok:
        create_live_sketch(design, "f", tmp_path / "S")
    else:
        with pytest.raises(ValueError):
            create_live_sketch(design, "f", tmp_path / "S")


@pytest.mark.parametrize("name", ["raw", "timeUs", "Serial", "int", "setup", "a b"])
def test_bad_filter_names_are_rejected(tmp_path, name):
    with pytest.raises(ValueError):
        create_live_sketch(butterworth_lowpass(4, 40, 1000), name, tmp_path / "S")


def test_bad_folder_name_and_sample_count(tmp_path):
    design = butterworth_lowpass(4, 40, 1000)
    with pytest.raises(ValueError):
        create_live_sketch(design, "f", tmp_path / "bad name")
    with pytest.raises(ValueError):
        create_live_sketch(design, "f", tmp_path / "S", samples=10)


# ------------------------------------------------------------ compiled on the PC

@needs_cpp
def test_live_sketch_runs_and_passes_the_check(tmp_path):
    design, sketch = make_live_folder(tmp_path)
    report = check_live_log(sketch, run_live_sketch_on_pc(sketch, tmp_path))
    assert report.passed
    assert report.mean_period_us == pytest.approx(1000.0, rel=0.002)
    assert report.raw_max - report.raw_min > 3000
    assert report.relative_error < 1e-5


@needs_cpp
def test_live_sketch_works_for_other_filters(tmp_path):
    for design, name in ((butterworth_lowpass(2, 20, 250), "lp"), (notch(50, 30, 500), "n50")):
        folder = tmp_path / f"Live_{name}"
        create_live_sketch(design, name, folder)
        out_dir = tmp_path / f"out_{name}"
        out_dir.mkdir()
        assert check_live_log(folder, run_live_sketch_on_pc(folder, out_dir)).passed


@needs_cpp
def test_cli_end_to_end(tmp_path, capsys):
    folder = tmp_path / "LiveCli"
    assert main(["target-sketch", "butter-lowpass", "--order", "4", "--cutoff", "40", "--fs",
                 "1000", "--name", "lp40", "--live", "-o", str(folder)]) == 0
    log = tmp_path / "live.txt"
    log.write_text(run_live_sketch_on_pc(folder, tmp_path), encoding="utf-8")
    capsys.readouterr()
    assert main(["check-live-log", str(folder), str(log)]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 3 and "Timing:" in out and "Input activity:" in out


# --------------------------------------------------------------- synthetic logs

def test_a_perfect_log_passes(tmp_path):
    design, sketch = make_live_folder(tmp_path)
    report = check_live_log(sketch, synthetic_log(design, square_wave()))
    assert report.passed and report.late_fraction == 0.0
    assert report.std_period_us == pytest.approx(0.0, abs=1e-9)


def test_timestamp_prefixes_repeats_and_a_cut_off_block_are_accepted(tmp_path):
    design, sketch = make_live_folder(tmp_path)
    one = synthetic_log(design, square_wave(), prefix="12:00:01.000 -> ")
    cut = "\n".join(one.splitlines()[:500])
    assert check_live_log(sketch, "\n".join([one, one, cut])).passed


def test_micros_wrap_around_is_handled(tmp_path):
    design, sketch = make_live_folder(tmp_path)
    log = synthetic_log(design, square_wave(), start_us=2 ** 32 - 700_000)
    assert check_live_log(sketch, log).timing_ok


def test_a_wrong_filter_value_fails_the_accuracy_check(tmp_path):
    design, sketch = make_live_folder(tmp_path)
    report = check_live_log(sketch, synthetic_log(design, square_wave(), tamper=900))
    assert not report.accuracy_ok and report.timing_ok and report.signal_ok


def test_a_slow_loop_fails_the_timing_check(tmp_path):
    design, sketch = make_live_folder(tmp_path)
    report = check_live_log(sketch, synthetic_log(design, square_wave(), period_us=1100.0))
    assert not report.timing_ok and report.accuracy_ok


def test_late_samples_are_counted(tmp_path):
    design, sketch = make_live_folder(tmp_path)
    log = synthetic_log(design, square_wave()).splitlines()
    # Delay the sample after every 100th one by a further 1000 us: 19 intervals become twice as
    # long (2000 readings have 19 such boundaries).
    rows = []
    for line in log:
        parts = line.split(",")
        if len(parts) == 3 and parts[0].isdigit():
            idx = int(parts[0]) // 1000
            parts[0] = str(int(parts[0]) + 1000 * (idx // 100))
            line = ",".join(parts)
        rows.append(line)
    report = check_live_log(sketch, "\n".join(rows))
    assert report.late_fraction == pytest.approx(19 / 1999, abs=1e-6)


def test_a_flat_input_fails_the_signal_check(tmp_path):
    design, sketch = make_live_folder(tmp_path)
    report = check_live_log(sketch, synthetic_log(design, np.full(2000, 2000)))
    assert not report.signal_ok and report.accuracy_ok and report.timing_ok
    assert not report.passed


def test_unreadable_or_incomplete_logs_are_rejected(tmp_path):
    design, sketch = make_live_folder(tmp_path)
    good = synthetic_log(design, square_wave())
    lines = good.splitlines()
    for text in ("", "no markers here", "\n".join(lines[:-3]),
                 "\n".join(lines[:300] + lines[301:]),
                 "\n".join(lines[:300] + ["1,2"] + lines[301:]),
                 "\n".join(lines[:300] + ["a,b,c"] + lines[301:])):
        with pytest.raises(VerificationError):
            check_live_log(sketch, text)


def test_parse_returns_the_three_columns():
    text = "FILTER2C_LIVE_BEGIN\n10,100,1.5\n1010,200,2.5\nFILTER2C_LIVE_END\n"
    t, raw, out = parse_live_log(text, 2)
    assert t.tolist() == [10, 1010] and raw.tolist() == [100, 200] and out.tolist() == [1.5, 2.5]


# ----------------------------------------------------------------- mixing up folders

def test_the_two_checks_refuse_the_wrong_folder(tmp_path):
    design, live = make_live_folder(tmp_path)
    selftest = tmp_path / "SelfTest"
    create_sketch(design, "lp40", selftest)
    with pytest.raises(VerificationError):
        check_board_log(live, "FILTER2C_BEGIN")
    with pytest.raises(VerificationError):
        check_live_log(selftest, synthetic_log(design, square_wave()))
    with pytest.raises(VerificationError):
        check_live_log(tmp_path, "x")


def test_cli_reports_a_missing_log(tmp_path, capsys):
    _, live = make_live_folder(tmp_path)
    assert main(["check-live-log", str(live), str(tmp_path / "missing.txt")]) == 2
    assert "error" in capsys.readouterr().err


def test_cli_fails_on_a_flat_input(tmp_path, capsys):
    design, live = make_live_folder(tmp_path)
    log = tmp_path / "flat.txt"
    log.write_text(synthetic_log(design, np.full(2000, 2000)), encoding="utf-8")
    assert main(["check-live-log", str(live), str(log)]) == 1
    assert "hint:" in capsys.readouterr().err


# ---------------------------------------------------------------- committed example

def test_committed_live_example_matches_the_tool(tmp_path):
    fresh = tmp_path / "LiveCheck40Hz"
    create_live_sketch(butterworth_lowpass(4, 40, 1000), "lp40", fresh)
    committed = ROOT / "examples" / "LiveCheck40Hz"
    assert sorted(p.name for p in committed.iterdir()) == sorted(p.name for p in fresh.iterdir())
    for path in fresh.iterdir():
        assert (committed / path.name).read_bytes() == path.read_bytes(), path.name
    assert (committed / "filter2c.h").read_bytes() == (ROOT / "src" / "filter2c.h").read_bytes()


def test_saved_esp32_s3_live_log_passes():
    """The real run on an ESP32-S3 (GPIO2 wired to GPIO1) that the README quotes."""
    text = (ROOT / "results" / "esp32-s3-live-log.txt").read_text(encoding="utf-8")
    report = check_live_log(ROOT / "examples" / "LiveCheck40Hz", text)
    assert report.passed
    assert report.mean_period_us == pytest.approx(1000.0, abs=2.0)
    assert report.std_period_us < 5.0 and report.late_fraction == 0.0
    assert report.raw_max - report.raw_min > 4000
    assert report.relative_error < 1e-5
