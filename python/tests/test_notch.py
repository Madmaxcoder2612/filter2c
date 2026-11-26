import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from scipy import signal

from filter2c import generate_header, runtime_header
from filter2c.cli import main
from filter2c.design import notch
from filter2c.target import check_board_log, create_sketch, read_test_signal
from filter2c.verify import (
    VerificationError,
    find_compiler,
    make_test_signal,
    measure_attenuation,
)
from test_target import ARDUINO_STUB, needs_cpp, run_sketch_on_pc

needs_compiler = pytest.mark.skipif(find_compiler() is None, reason="no C compiler available")
ROOT = Path(__file__).resolve().parents[2]


def test_notch_is_one_normalised_section():
    design = notch(50, 30, 1000)
    assert design.sos.shape == (1, 6)
    assert design.sos[0, 3] == 1.0
    assert design.q == 30
    assert "Q 30" in design.describe()


def test_gain_is_one_at_dc_and_nyquist_and_zero_at_the_notch():
    design = notch(50, 30, 1000)
    _, h = signal.sosfreqz(design.sos, worN=[0.0, 2 * np.pi * 50 / 1000, np.pi])
    assert abs(h[0]) == pytest.approx(1.0, abs=1e-9)
    assert abs(h[1]) < 1e-9
    assert abs(h[2]) == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("q", [5, 10, 30])
def test_minus_3_db_width_is_about_f0_over_q(q):
    design = notch(50, q, 1000)
    freqs = np.linspace(1, 400, 400_000)
    _, h = signal.sosfreqz(design.sos, worN=2 * np.pi * freqs / 1000)
    below = freqs[np.abs(h) < 1 / np.sqrt(2)]
    assert below.max() - below.min() == pytest.approx(50 / q, rel=0.05)


@pytest.mark.parametrize(
    "freq, q, fs",
    [(0, 30, 1000), (-5, 30, 1000), (500, 30, 1000), (600, 30, 1000), (50, 0, 1000),
     (50, 0.1, 1000), (50, 1000, 1000), (50, float("nan"), 1000), (50, 30, 0),
     (50, 30, float("inf")), (float("nan"), 30, 1000)],
)
def test_bad_notch_arguments_are_rejected(freq, q, fs):
    with pytest.raises(ValueError):
        notch(freq, q, fs)


def test_test_signal_with_tone_contains_the_tone_and_default_is_unchanged():
    plain = make_test_signal(1000, 4096)
    with_tone = make_test_signal(1000, 4096, tones_hz=(50.0,))
    n = np.arange(4096)
    difference = with_tone.astype(np.float64) - plain.astype(np.float64)
    assert np.allclose(difference, 0.5 * np.sin(2 * np.pi * 50 * n / 1000), atol=1e-5)


@needs_compiler
@pytest.mark.parametrize("freq, q, fs", [(50, 5, 1000), (50, 30, 1000), (60, 30, 1000), (50, 30, 500)])
def test_c_code_removes_the_notch_frequency(freq, q, fs):
    design = notch(freq, q, fs)
    result = measure_attenuation(design, generate_header(design, "n"), runtime_header(), "n")
    assert result.passed
    assert result.attenuation_db > 60


@needs_compiler
def test_a_slightly_wrong_coefficient_is_caught():
    design = notch(50, 30, 1000)
    broken = design.sos.copy()
    broken[0, 1] *= 1.05  # b1 off by 5 %: the zero no longer sits on the unit circle at 50 Hz
    from filter2c.design import FilterDesign
    wrong = FilterDesign("Notch", 2, 1000.0, 50.0, broken, q=30.0)
    result = measure_attenuation(design, generate_header(wrong, "n"), runtime_header(), "n")
    assert not result.passed
    assert result.attenuation_db < 40


@needs_compiler
def test_attenuation_at_a_passband_frequency_is_small():
    """The notch must not remove everything: a 200 Hz tone should pass almost unchanged."""
    design = notch(50, 30, 1000)
    result = measure_attenuation(design, generate_header(design, "n"), runtime_header(), "n",
                                 frequency_hz=200.0, minimum_db=0.0)
    assert abs(result.attenuation_db) < 0.1


def test_unstable_design_is_refused():
    from filter2c.design import FilterDesign
    bad = FilterDesign("bad", 2, 1000.0, 50.0, np.array([[1.0, 0.0, 0.0, 1.0, -2.5, 1.2]]))
    with pytest.raises(VerificationError):
        measure_attenuation(bad, "", "", "n")


@needs_compiler
def test_cli_notch_verify(tmp_path, capsys):
    out = tmp_path / "n.h"
    code = main(["notch", "--freq", "50", "--q", "30", "--fs", "1000", "--name", "n",
                 "-o", str(out), "--verify"])
    text = capsys.readouterr().out
    assert code == 0
    assert "Attenuation of a 50 Hz tone" in text and "PASS" in text
    assert "n_sections" in out.read_text(encoding="utf-8")


@needs_compiler
def test_cli_notch_with_impossible_attenuation_fails(tmp_path):
    code = main(["notch", "--freq", "50", "--q", "30", "--fs", "1000", "--name", "n",
                 "-o", str(tmp_path / "n.h"), "--verify", "--min-attenuation-db", "400"])
    assert code == 1


@pytest.mark.parametrize("extra", [["--freq", "600"], ["--q", "0"], ["--name", "int"]])
def test_cli_notch_bad_input(tmp_path, extra):
    args = {"--freq": "50", "--q": "30", "--fs": "1000", "--name": "n"}
    args.update(dict(zip(extra[::2], extra[1::2])))
    argv = ["notch"] + [part for kv in args.items() for part in kv] + ["-o", str(tmp_path / "x.h")]
    assert main(argv) == 2
    assert not (tmp_path / "x.h").exists()


def test_notch_sketch_contents_and_test_signal_has_the_tone(tmp_path):
    folder = tmp_path / "NotchTest"
    create_sketch(notch(50, 30, 1000), "notch50", folder)
    assert (folder / "notch50.h").exists()
    x = read_test_signal(folder)
    n = np.arange(x.size)
    w = 2 * np.pi * 50 / 1000
    amplitude = 2 / x.size * np.hypot(np.sum(x * np.cos(w * n)), np.sum(x * np.sin(w * n)))
    assert amplitude == pytest.approx(0.5, abs=0.05)


@needs_cpp
def test_notch_sketch_runs_and_passes_the_board_check(tmp_path):
    folder = tmp_path / "NotchTest"
    create_sketch(notch(50, 30, 1000), "notch50", folder)
    report = check_board_log(folder, run_sketch_on_pc(folder, tmp_path))
    assert report.passed
    assert report.relative_error < 1e-4


def test_committed_hum_example_is_up_to_date():
    folder = ROOT / "examples" / "HumNotch50Hz"
    expected = generate_header(notch(50, 30, 1000), "notch50")
    assert (folder / "notch50.h").read_text(encoding="utf-8").replace("\r\n", "\n") == expected
    assert (folder / "filter2c.h").read_bytes() == (ROOT / "src" / "filter2c.h").read_bytes()


@needs_cpp
def test_hum_sketch_runs_one_sample_and_prints_the_plotter_format(tmp_path):
    folder = ROOT / "examples" / "HumNotch50Hz"
    gpp = shutil.which("g++") or shutil.which("clang++")
    stub = tmp_path / "stub"
    stub.mkdir()
    (stub / "Arduino.h").write_text(ARDUINO_STUB, newline="\n")
    main_cpp = tmp_path / "main.cpp"
    main_cpp.write_text(
        f'#include "{(folder / "HumNotch50Hz.ino").as_posix()}"\n'
        "int main() { setup(); loop(); return 0; }\n", newline="\n")
    exe = tmp_path / "hum.exe"
    build = subprocess.run(
        [gpp, "-std=c++11", "-Wall", "-Wextra", "-Werror", "-I", str(stub), "-I", str(folder),
         str(main_cpp), "-o", str(exe)], capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    out = subprocess.run([str(exe)], capture_output=True, text=True, check=True).stdout
    assert re.fullmatch(r"raw:-?[0-9.]+,notch:-?[0-9.]+\n", out), out
