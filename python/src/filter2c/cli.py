"""Command line interface: ``filter2c butter-lowpass ...``."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .codegen import check_name, generate_header, runtime_header
from .design import butterworth_lowpass
from .verify import (
    DEFAULT_TOLERANCE,
    VerificationError,
    check_stability,
    compare_with_scipy,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="filter2c",
        description="Design a digital filter with SciPy and generate C code for it.",
    )
    parser.add_argument("--version", action="version", version=f"filter2c {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    low = sub.add_parser("butter-lowpass", help="Butterworth low-pass filter")
    low.add_argument("--order", type=int, required=True, help="filter order (1 to 16)")
    low.add_argument("--cutoff", type=float, required=True, help="-3 dB frequency in Hz")
    low.add_argument("--fs", type=float, required=True, help="sampling rate in Hz")
    low.add_argument("--name", default="filter", help="C name of the filter (default: filter)")
    low.add_argument("-o", "--output", type=Path, required=True, help="header file to write")
    low.add_argument(
        "--write-runtime", action="store_true",
        help="also write filter2c.h next to the output file",
    )
    low.add_argument(
        "--verify", action="store_true",
        help="compile the result and compare it with SciPy (needs a C compiler)",
    )
    low.add_argument(
        "--tolerance", type=float, default=DEFAULT_TOLERANCE,
        help=f"allowed error as a fraction of the output peak (default: {DEFAULT_TOLERANCE:g})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        check_name(args.name)
        design = butterworth_lowpass(args.order, args.cutoff, args.fs)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

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
        try:
            result = compare_with_scipy(design, header, runtime, args.name, args.tolerance)
        except VerificationError as error:
            print(f"error: could not verify: {error}", file=sys.stderr)
            return 2
        status = "PASS" if result.passed else "FAIL"
        print(
            f"C code against SciPy: {status} "
            f"(max error {result.max_abs_error:.2e} = {result.relative_error:.2e} of the peak, "
            f"tolerance {result.tolerance:.0e}, {result.samples} samples)"
        )
        if not result.passed:
            print(
                "hint: 32-bit float loses precision when the cutoff is a very small fraction "
                "of the sampling rate. Lower the sampling rate (filter fewer samples per "
                "second), raise the cutoff, or accept a larger --tolerance if your "
                "application allows it.",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
