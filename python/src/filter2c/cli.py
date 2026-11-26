"""Command line interface: ``filter2c butter-lowpass ...`` and the board self-test commands."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .codegen import check_name, generate_header, runtime_header
from .design import butterworth_lowpass
from .target import check_board_log, create_sketch
from .verify import (
    DEFAULT_TOLERANCE,
    VerificationError,
    check_stability,
    compare_with_scipy,
)

_FLOAT_HINT = (
    "hint: 32-bit float loses precision when the cutoff is a very small fraction "
    "of the sampling rate. Lower the sampling rate (filter fewer samples per "
    "second), raise the cutoff, or accept a larger --tolerance if your "
    "application allows it."
)


def _add_design_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--order", type=int, required=True, help="filter order (1 to 16)")
    parser.add_argument("--cutoff", type=float, required=True, help="-3 dB frequency in Hz")
    parser.add_argument("--fs", type=float, required=True, help="sampling rate in Hz")
    parser.add_argument("--name", default="filter", help="C name of the filter (default: filter)")


def _add_tolerance_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--tolerance", type=float, default=DEFAULT_TOLERANCE,
        help=f"allowed error as a fraction of the output peak (default: {DEFAULT_TOLERANCE:g})",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="filter2c",
        description="Design a digital filter with SciPy and generate C code for it.",
    )
    parser.add_argument("--version", action="version", version=f"filter2c {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    low = sub.add_parser("butter-lowpass", help="Butterworth low-pass filter")
    _add_design_arguments(low)
    low.add_argument("-o", "--output", type=Path, required=True, help="header file to write")
    low.add_argument(
        "--write-runtime", action="store_true",
        help="also write filter2c.h next to the output file",
    )
    low.add_argument(
        "--verify", action="store_true",
        help="compile the result and compare it with SciPy (needs a C compiler)",
    )
    _add_tolerance_argument(low)

    sketch = sub.add_parser(
        "target-sketch",
        help="write an ESP32 sketch that runs the filter on the board and prints the result",
    )
    _add_design_arguments(sketch)
    sketch.add_argument(
        "-o", "--output", type=Path, required=True,
        help="sketch folder to create (its name becomes the sketch name)",
    )

    log = sub.add_parser(
        "check-board-log",
        help="compare the text the board printed with SciPy and the PC build",
    )
    log.add_argument("sketch", type=Path, help="the sketch folder made by target-sketch")
    log.add_argument("log", type=Path, help="text file with the copied serial output")
    _add_tolerance_argument(log)
    return parser


def _run_butter_lowpass(args: argparse.Namespace) -> int:
    check_name(args.name)
    design = butterworth_lowpass(args.order, args.cutoff, args.fs)

    header = generate_header(design, args.name)
    runtime = runtime_header()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(header, encoding="utf-8", newline="\n")
    print(f"Wrote {args.output} ({design.describe()}, {design.sections} section(s))")

    if args.write_runtime:
        target = args.output.parent / "filter2c.h"
        target.write_text(runtime, encoding="utf-8", newline="\n")
        print(f"Wrote {target}")

    stability = check_stability(design)
    verdict = "stable" if stability.stable else "UNSTABLE"
    print(
        f"Stability after rounding to float: {verdict} "
        f"(largest pole radius {stability.max_pole_radius:.9f})"
    )
    if not stability.stable:
        return 1

    if args.verify:
        result = compare_with_scipy(design, header, runtime, args.name, args.tolerance)
        status = "PASS" if result.passed else "FAIL"
        print(
            f"C code against SciPy: {status} "
            f"(max error {result.max_abs_error:.2e} = {result.relative_error:.2e} of the peak, "
            f"tolerance {result.tolerance:.0e}, {result.samples} samples)"
        )
        if not result.passed:
            print(_FLOAT_HINT, file=sys.stderr)
            return 1
    return 0


def _run_target_sketch(args: argparse.Namespace) -> int:
    design = butterworth_lowpass(args.order, args.cutoff, args.fs)
    files = create_sketch(design, args.name, args.output)
    print(f"Wrote sketch folder {args.output} ({design.describe()}):")
    for path in files:
        print(f"  {path.name}")
    print(
        f"Next: open {args.output / (args.output.name + '.ino')} in the Arduino IDE, select your "
        "ESP32 board, upload, open the Serial Monitor at 115200 baud, then copy all of its text "
        f"into a file and run: filter2c check-board-log {args.output} <that file>"
    )
    return 0


def _run_check_board_log(args: argparse.Namespace) -> int:
    report = check_board_log(args.sketch, args.log.read_text(encoding="utf-8", errors="replace"),
                             args.tolerance)
    status = "PASS" if report.passed else "FAIL"
    print(
        f"Board output against SciPy: {status} "
        f"(max error {report.max_abs_error:.2e} = {report.relative_error:.2e} of the peak, "
        f"tolerance {report.tolerance:.0e}, {report.samples} samples)"
    )
    if report.identical_to_pc_build is None:
        print("Board against the PC build: not compared (no C compiler found)")
    elif report.identical_to_pc_build:
        print("Board against the PC build: identical, every sample matches exactly")
    else:
        print(
            "Board against the PC build: tiny differences, "
            f"largest {report.max_diff_to_pc_build:.2e} (different compilers round differently)"
        )
    print(
        f"Speed: {report.cpu_mhz:g} MHz, {report.cycles_per_sample:.1f} cycles per sample = "
        f"{report.microseconds_per_sample:.2f} us per sample "
        f"(this filter alone could keep up with up to {report.max_sample_rate_hz / 1000:.0f} kHz)"
    )
    if not report.passed:
        print(_FLOAT_HINT, file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "butter-lowpass":
            return _run_butter_lowpass(args)
        if args.command == "target-sketch":
            return _run_target_sketch(args)
        return _run_check_board_log(args)
    except (ValueError, VerificationError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
