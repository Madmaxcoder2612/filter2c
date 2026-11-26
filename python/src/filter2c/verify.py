"""Checks that the generated C code does what the design says.

Two independent checks:

* ``check_stability``: after rounding the coefficients to float32, are all
  poles still inside the unit circle?
* ``compare_with_scipy``: compile the generated header with a C compiler, run a
  test signal through it, and compare with SciPy's float64 reference filter.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import signal

from .design import FilterDesign

DEFAULT_TOLERANCE = 1e-4  # largest allowed error, as a fraction of the output peak


class VerificationError(RuntimeError):
    """Raised when the verification could not be run (for example no compiler)."""


@dataclass(frozen=True)
class Stability:
    max_pole_radius: float
    margin: float  # 1 - max_pole_radius
    stable: bool


@dataclass(frozen=True)
class Comparison:
    samples: int
    max_abs_error: float
    peak_output: float
    relative_error: float
    tolerance: float
    passed: bool


def find_compiler() -> str | None:
    """Return the path of a C compiler on this machine, or None."""
    for candidate in ("gcc", "clang", "cc"):
        path = shutil.which(candidate)
        if path:
            return path
    return None


def check_stability(design: FilterDesign) -> Stability:
    """Check that the float32-rounded filter is still stable."""
    radius = 0.0
    for _b0, _b1, _b2, _a0, a1, a2 in design.sos:
        rounded = [1.0, float(np.float32(a1)), float(np.float32(a2))]
        radius = max(radius, float(np.max(np.abs(np.roots(rounded)))))
    return Stability(max_pole_radius=radius, margin=1.0 - radius, stable=radius < 1.0)


def make_test_signal(fs_hz: float, samples: int = 4096, seed: int = 20261125) -> np.ndarray:
    """Three sine waves plus noise, as float32. Frequencies scale with the sampling rate."""
    t = np.arange(samples) / fs_hz
    rng = np.random.default_rng(seed)
    x = (
        np.sin(2 * np.pi * 0.005 * fs_hz * t)
        + 0.5 * np.sin(2 * np.pi * 0.04 * fs_hz * t)
        + 0.25 * np.sin(2 * np.pi * 0.2 * fs_hz * t)
        + 0.1 * rng.standard_normal(samples)
    )
    return x.astype(np.float32)


_HARNESS = """#include <stdio.h>
#include "{name}.h"

int main(int argc, char **argv)
{{
    FILE *in;
    float x;
    if (argc != 2) return 2;
    in = fopen(argv[1], "r");
    if (!in) return 3;
    filter2c_reset(&{name});
    while (fscanf(in, "%f", &x) == 1) {{
        printf("%.9g\\n", filter2c_process(&{name}, x));
    }}
    fclose(in);
    return 0;
}}
"""


def run_c_filter(
    header: str, runtime: str, name: str, x: np.ndarray, compiler: str | None = None
) -> np.ndarray:
    """Compile the generated header into a tiny program and filter ``x`` with it.

    The input is passed as text with 9 significant digits, so the C program
    reads back exactly the same float32 values that Python holds.
    """
    compiler = compiler or find_compiler()
    if compiler is None:
        raise VerificationError("no C compiler found (looked for gcc, clang, cc)")

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / f"{name}.h").write_text(header, encoding="utf-8", newline="\n")
        (folder / "filter2c.h").write_text(runtime, encoding="utf-8", newline="\n")
        (folder / "main.c").write_text(_HARNESS.format(name=name), encoding="utf-8", newline="\n")
        (folder / "input.txt").write_text(
            "\n".join(f"{float(v):.9g}" for v in x), encoding="utf-8", newline="\n"
        )
        exe = folder / "run.exe"
        try:
            build = subprocess.run(
                [compiler, "-std=c99", "-O2", "-Wall", "-Wextra", "-pedantic", "-Werror",
                 "-I", str(folder), str(folder / "main.c"), "-o", str(exe)],
                capture_output=True, text=True, timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise VerificationError(f"could not run the C compiler {compiler!r}: {error}") from error
        if build.returncode != 0:
            raise VerificationError(f"the generated code did not compile:\n{build.stderr}")
        run = subprocess.run(
            [str(exe), str(folder / "input.txt")], capture_output=True, text=True, timeout=60
        )
        if run.returncode != 0:
            raise VerificationError(f"the test program failed with code {run.returncode}")
    return np.array([float(line) for line in run.stdout.split()], dtype=np.float64)


def compare_with_scipy(
    design: FilterDesign,
    header: str,
    runtime: str,
    name: str,
    tolerance: float = DEFAULT_TOLERANCE,
    compiler: str | None = None,
) -> Comparison:
    """Run the test signal through the C code and through SciPy and compare."""
    x = make_test_signal(design.fs_hz)
    from_c = run_c_filter(header, runtime, name, x, compiler)
    reference = signal.sosfilt(design.sos, x.astype(np.float64))
    if from_c.shape != reference.shape:
        raise VerificationError(
            f"the C program returned {from_c.size} samples, expected {reference.size}"
        )
    max_abs = float(np.max(np.abs(from_c - reference)))
    peak = float(np.max(np.abs(reference)))
    relative = max_abs / peak
    return Comparison(
        samples=int(x.size),
        max_abs_error=max_abs,
        peak_output=peak,
        relative_error=relative,
        tolerance=tolerance,
        passed=bool(relative <= tolerance),
    )
