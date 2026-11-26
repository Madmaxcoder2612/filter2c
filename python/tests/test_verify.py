import shutil
from pathlib import Path

import numpy as np
import pytest

from filter2c import butterworth_lowpass, generate_header, runtime_header
from filter2c.design import FilterDesign
from filter2c.verify import (
    VerificationError,
    check_stability,
    compare_with_scipy,
    find_compiler,
    make_test_signal,
    run_c_filter,
)

needs_compiler = pytest.mark.skipif(find_compiler() is None, reason="no C compiler available")
ROOT = Path(__file__).resolve().parents[2]


def test_stability_of_normal_design():
    result = check_stability(butterworth_lowpass(4, 40, 1000))
    assert result.stable
    assert 0.9 < result.max_pole_radius < 1.0
    assert result.margin == pytest.approx(1.0 - result.max_pole_radius)


def test_stability_detects_a_pole_outside_the_unit_circle():
    bad = FilterDesign("bad", 2, 1000.0, 40.0, np.array([[1.0, 0.0, 0.0, 1.0, -2.5, 1.2]]))
    assert not check_stability(bad).stable


def test_test_signal_is_reproducible_and_float32():
    a, b = make_test_signal(1000), make_test_signal(1000)
    assert a.dtype == np.float32
    assert np.array_equal(a, b)


@needs_compiler
def test_c_code_matches_scipy():
    design = butterworth_lowpass(4, 40, 1000)
    result = compare_with_scipy(design, generate_header(design, "lp40"), runtime_header(), "lp40")
    assert result.passed
    assert result.relative_error < 1e-5


@needs_compiler
def test_c_code_matches_scipy_for_other_orders_and_rates():
    for order, cutoff, fs in [(1, 10, 200), (2, 20, 100), (3, 50, 500), (6, 100, 2000)]:
        design = butterworth_lowpass(order, cutoff, fs)
        result = compare_with_scipy(design, generate_header(design, "f"), runtime_header(), "f")
        assert result.passed, (order, cutoff, fs, result)


@needs_compiler
def test_verification_catches_a_wrong_coefficient():
    design = butterworth_lowpass(4, 40, 1000)
    header = generate_header(design, "lp40")
    broken = header.replace("-1.57524002f", "-1.47524002f")
    assert broken != header
    result = compare_with_scipy(design, broken, runtime_header(), "lp40")
    assert not result.passed


@needs_compiler
def test_c_step_response_settles_to_one():
    design = butterworth_lowpass(4, 40, 1000)
    y = run_c_filter(generate_header(design, "lp40"), runtime_header(), "lp40",
                     np.ones(1000, dtype=np.float32))
    assert y[-1] == pytest.approx(1.0, abs=1e-4)
    assert y[0] < 0.01


@needs_compiler
@pytest.mark.parametrize("order", [2, 4])
def test_c_gain_matches_analytic_butterworth(order):
    """Independent of SciPy: compare with the closed-form digital Butterworth gain.

    For a filter made with the bilinear transform and frequency prewarping,
    |H(f)|^2 = 1 / (1 + (tan(pi f / fs) / tan(pi fc / fs)) ** (2 * order)).
    """
    fs, fc = 1000.0, 40.0
    design = butterworth_lowpass(order, fc, fs)
    header, runtime = generate_header(design, "f"), runtime_header()
    n = np.arange(4000)
    for f in (10.0, 40.0, 80.0, 150.0):
        x = np.sin(2 * np.pi * f * n / fs).astype(np.float32)
        y = run_c_filter(header, runtime, "f", x)
        measured = np.max(np.abs(y[2000:]))  # skip the start-up transient
        expected = 1 / np.sqrt(1 + (np.tan(np.pi * f / fs) / np.tan(np.pi * fc / fs)) ** (2 * order))
        assert measured == pytest.approx(expected, rel=0.01), f


def test_missing_compiler_is_reported():
    design = butterworth_lowpass(4, 40, 1000)
    with pytest.raises(VerificationError):
        run_c_filter(generate_header(design, "f"), runtime_header(), "f",
                     np.zeros(4, dtype=np.float32), compiler="no-such-compiler-xyz")


def test_a_compile_error_is_reported():
    if find_compiler() is None:
        pytest.skip("no C compiler available")
    design = butterworth_lowpass(4, 40, 1000)
    with pytest.raises(VerificationError):
        run_c_filter("this is not C\n", runtime_header(), "f", np.zeros(4, dtype=np.float32))


def test_runtime_copies_are_identical():
    """The Arduino library and the Python package must ship the same filter2c.h."""
    arduino = (ROOT / "src" / "filter2c.h").read_bytes()
    python_copy = (ROOT / "python" / "src" / "filter2c" / "runtime" / "filter2c.h").read_bytes()
    assert arduino == python_copy
    assert (ROOT / "LICENSE").read_bytes() == (ROOT / "python" / "LICENSE").read_bytes()


def test_generated_header_compiles_as_cpp():
    gpp = shutil.which("g++") or shutil.which("clang++")
    if gpp is None:
        pytest.skip("no C++ compiler available")
    import subprocess
    import tempfile

    design = butterworth_lowpass(4, 40, 1000)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "lp40.h").write_text(generate_header(design, "lp40"), newline="\n")
        (folder / "filter2c.h").write_text(runtime_header(), newline="\n")
        (folder / "main.cpp").write_text(
            '#include "lp40.h"\nint main() { filter2c_reset(&lp40); '
            "return filter2c_process(&lp40, 1.0f) > 1e9f; }\n", newline="\n")
        build = subprocess.run(
            [gpp, "-std=c++11", "-Wall", "-Wextra", "-pedantic", "-Werror",
             "-fsyntax-only", "-I", str(folder), str(folder / "main.cpp")],
            capture_output=True, text=True)
    assert build.returncode == 0, build.stderr


def test_example_header_is_up_to_date():
    """examples/Butterworth40Hz/lp40.h must equal what the tool generates today."""
    expected = generate_header(butterworth_lowpass(4, 40, 1000), "lp40")
    on_disk = (ROOT / "examples" / "Butterworth40Hz" / "lp40.h").read_text(encoding="utf-8")
    assert on_disk.replace("\r\n", "\n") == expected
