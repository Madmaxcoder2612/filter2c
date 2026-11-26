"""Tests for the on-board self-test workflow.

No board is available in the tests. Instead the generated sketch is compiled on
the PC against a tiny stand-in for the Arduino functions it uses, run, and its
printed output is fed to the log checker, exactly as a copy from the Serial
Monitor would be. This checks the sketch logic and the log format, not the
board itself.
"""
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from filter2c import butterworth_lowpass
from filter2c.cli import main
from filter2c.target import (
    META_FILE,
    check_board_log,
    create_sketch,
    parse_board_log,
    read_test_signal,
)
from filter2c.verify import VerificationError, find_compiler

needs_cpp = pytest.mark.skipif(
    shutil.which("g++") is None and shutil.which("clang++") is None,
    reason="no C++ compiler available",
)

ARDUINO_STUB = """#pragma once
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <type_traits>

struct SerialStub {
    void begin(unsigned long) {}
    explicit operator bool() const { return true; }
    void println(const char *s) { puts(s); }
    void print(const char *s) { fputs(s, stdout); }
    void print(char c) { ::putchar(c); }
    template <typename T>
    typename std::enable_if<std::is_integral<T>::value>::type print(T v) { ::printf("%lld", (long long)v); }
    template <typename T>
    typename std::enable_if<std::is_integral<T>::value>::type println(T v) { ::printf("%lld", (long long)v); ::putchar(10); }
    void print(double v, int digits) { ::printf("%.*f", digits, v); }
    void println(double v, int digits) { ::printf("%.*f\\n", digits, v); }
    int printf(const char *format, ...) __attribute__((format(printf, 2, 3)))
    {
        va_list args;
        va_start(args, format);
        int n = vprintf(format, args);
        va_end(args);
        return n;
    }
};
static SerialStub Serial __attribute__((unused));

struct EspStub {
    uint32_t getCycleCount() { static uint32_t c = 0; c += 100000; return c; }
};
static EspStub ESP __attribute__((unused));

static inline unsigned int getCpuFrequencyMhz() { return 240; }
static inline void delay(unsigned long) {}
static unsigned long g_stub_us = 0;
static inline unsigned long micros() { g_stub_us += 250; return g_stub_us; }
static inline unsigned long millis() { return g_stub_us / 1000; }
static inline int analogRead(int) { static int calls = 0; return ((calls++ / 50) % 2) ? 3900 : 120; }
static inline void pinMode(int, int) {}
static inline void digitalWrite(int, int) {}
#define OUTPUT 1
#define HIGH 1
#define LOW 0
#define A0 14
"""


def make_sketch(tmp_path, order=4, cutoff=40.0, fs=1000.0, name="lp40", folder="MySketch"):
    design = butterworth_lowpass(order, cutoff, fs)
    sketch = tmp_path / folder
    create_sketch(design, name, sketch)
    return design, sketch


def run_sketch_on_pc(sketch: Path, tmp_path: Path) -> str:
    """Compile the .ino as C++ with the Arduino stand-in and return what it prints."""
    gpp = shutil.which("g++") or shutil.which("clang++")
    stub_dir = tmp_path / "stub"
    stub_dir.mkdir(exist_ok=True)
    (stub_dir / "Arduino.h").write_text(ARDUINO_STUB, newline="\n")
    main_cpp = tmp_path / "main.cpp"
    main_cpp.write_text(
        f'#include "{(sketch / (sketch.name + ".ino")).as_posix()}"\n'
        "int main() { setup(); loop(); return 0; }\n", newline="\n")
    exe = tmp_path / "sketch.exe"
    build = subprocess.run(
        [gpp, "-std=c++11", "-Wall", "-Wextra", "-Werror", "-I", str(stub_dir),
         "-I", str(sketch), str(main_cpp), "-o", str(exe)],
        capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    return subprocess.run([str(exe)], capture_output=True, text=True, check=True).stdout


def test_sketch_folder_contents(tmp_path):
    _, sketch = make_sketch(tmp_path)
    names = sorted(p.name for p in sketch.iterdir())
    assert names == sorted(["MySketch.ino", "lp40.h", "testsignal.h", "filter2c.h", META_FILE])
    ino = (sketch / "MySketch.ino").read_text(encoding="utf-8")
    assert '#include "lp40.h"' in ino and "filter2c_process(&lp40" in ino


def test_test_signal_header_reads_back_exactly(tmp_path):
    design, sketch = make_sketch(tmp_path)
    from filter2c.verify import make_test_signal
    assert np.array_equal(read_test_signal(sketch), make_test_signal(design.fs_hz, 1024))


@pytest.mark.parametrize("name", ["setup", "Serial", "testsignal", "filter2c", "int", "a b"])
def test_bad_filter_names_are_rejected(tmp_path, name):
    with pytest.raises(ValueError):
        create_sketch(butterworth_lowpass(4, 40, 1000), name, tmp_path / "S")


@pytest.mark.parametrize("folder", ["my sketch", ".hidden", "a/b"[:1] + "$"])
def test_bad_folder_names_are_rejected(tmp_path, folder):
    with pytest.raises(ValueError):
        create_sketch(butterworth_lowpass(4, 40, 1000), "lp40", tmp_path / folder)


@needs_cpp
def test_sketch_runs_and_its_output_passes_the_check(tmp_path):
    _, sketch = make_sketch(tmp_path)
    log = run_sketch_on_pc(sketch, tmp_path)
    report = check_board_log(sketch, log)
    assert report.passed
    assert report.relative_error < 1e-5
    assert report.cpu_mhz == 240
    assert report.samples == 1024


@needs_cpp
@pytest.mark.skipif(find_compiler() is None, reason="no C compiler available")
def test_pc_run_is_identical_to_pc_build(tmp_path):
    _, sketch = make_sketch(tmp_path)
    report = check_board_log(sketch, run_sketch_on_pc(sketch, tmp_path))
    assert report.identical_to_pc_build is True


@needs_cpp
def test_log_with_timestamps_and_repeats_is_accepted(tmp_path):
    _, sketch = make_sketch(tmp_path)
    log = run_sketch_on_pc(sketch, tmp_path)
    stamped = "\n".join(f"12:00:{i % 60:02d}.123 -> {line}" for i, line in enumerate(log.splitlines()))
    truncated_extra_block = "\n".join(log.splitlines()[:500])  # a second block cut off halfway
    text = "garbage before\n" + stamped + "\n" + stamped + "\n" + truncated_extra_block
    assert check_board_log(sketch, text).passed


@needs_cpp
def test_tampered_log_fails(tmp_path):
    _, sketch = make_sketch(tmp_path)
    lines = run_sketch_on_pc(sketch, tmp_path).splitlines()
    lines[400] = "5.0"  # one wrong sample
    report = check_board_log(sketch, "\n".join(lines))
    assert not report.passed


@needs_cpp
def test_incomplete_or_wrong_logs_are_rejected(tmp_path):
    _, sketch = make_sketch(tmp_path)
    lines = run_sketch_on_pc(sketch, tmp_path).splitlines()
    with pytest.raises(VerificationError):
        check_board_log(sketch, "")
    with pytest.raises(VerificationError):
        check_board_log(sketch, "\n".join(lines[:-3]))  # statistics missing
    with pytest.raises(VerificationError):
        check_board_log(sketch, "\n".join(lines[:300] + lines[301:]))  # a sample missing
    with pytest.raises(VerificationError):
        check_board_log(sketch, "\n".join(lines[:300] + ["not a number"] + lines[301:]))


def test_parse_rejects_nonpositive_statistics():
    text = ("FILTER2C_BEGIN\n1.0\nFILTER2C_END\nFILTER2C_SAMPLES=1\n"
            "FILTER2C_CPU_MHZ=0\nFILTER2C_CYCLES_PER_SAMPLE=10\n")
    with pytest.raises(VerificationError):
        parse_board_log(text, 1)


def test_folder_without_metadata_is_rejected(tmp_path):
    with pytest.raises(VerificationError):
        check_board_log(tmp_path, "FILTER2C_BEGIN")


@needs_cpp
def test_cli_end_to_end(tmp_path, capsys):
    sketch = tmp_path / "Esp32Test"
    assert main(["target-sketch", "butter-lowpass", "--order", "4", "--cutoff", "40", "--fs", "1000",
                 "--name", "lp40", "-o", str(sketch)]) == 0
    log_file = tmp_path / "board.txt"
    log_file.write_text(run_sketch_on_pc(sketch, tmp_path), encoding="utf-8")
    capsys.readouterr()
    assert main(["check-board-log", str(sketch), str(log_file)]) == 0
    out = capsys.readouterr().out
    assert "PASS" in out and "Speed: 240 MHz" in out


def test_cli_reports_missing_log_file(tmp_path, capsys):
    sketch = tmp_path / "S1"
    main(["target-sketch", "butter-lowpass", "--order", "4", "--cutoff", "40", "--fs", "1000",
          "--name", "lp40", "-o", str(sketch)])
    assert main(["check-board-log", str(sketch), str(tmp_path / "missing.txt")]) == 2
    assert "error" in capsys.readouterr().err


def test_committed_esp32_example_is_up_to_date(tmp_path):
    """examples/ESP32SelfTest must equal what target-sketch generates today."""
    root = Path(__file__).resolve().parents[2]
    fresh = tmp_path / "ESP32SelfTest"
    create_sketch(butterworth_lowpass(4, 40, 1000), "lp40", fresh)
    committed = root / "examples" / "ESP32SelfTest"
    for path in fresh.iterdir():
        assert (committed / path.name).read_bytes() == path.read_bytes(), path.name
    assert (committed / "filter2c.h").read_bytes() == (root / "src" / "filter2c.h").read_bytes()


def test_committed_esp32_s3_board_log_passes():
    """The real board log in results/ is the evidence behind the README. It must keep passing."""
    root = Path(__file__).resolve().parents[2]
    text = (root / "results" / "esp32-s3-board-log.txt").read_text(encoding="utf-8")
    report = check_board_log(root / "examples" / "ESP32SelfTest", text)
    assert report.passed
    assert report.relative_error < 1e-5
    assert report.cpu_mhz == 240
    assert 40 < report.cycles_per_sample < 46
