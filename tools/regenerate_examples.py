"""Regenerate every generated file in examples/ with the current version of the tool.

Usage (from the repository root):

    python tools/regenerate_examples.py

The headers, sketches and metadata files in examples/ are written by filter2c and contain
its version number. After the tool or its version changes, run this script. The tests check
that the committed examples equal what the tool writes today.
"""
from pathlib import Path

from filter2c import (
    butterworth_bandpass,
    butterworth_highpass,
    butterworth_lowpass,
    generate_header,
    notch,
    runtime_header,
)
from filter2c.live import create_live_sketch
from filter2c.target import create_sketch

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", path.relative_to(ROOT))


def main() -> None:
    runtime = runtime_header()

    # Examples with a hand-written sketch: only the generated header and the runtime header.
    for folder, design, name in (
        ("Butterworth40Hz", butterworth_lowpass(4, 40, 1000), "lp40"),
        ("HumNotch50Hz", notch(50, 30, 1000), "notch50"),
    ):
        write(EXAMPLES / folder / f"{name}.h", generate_header(design, name))
        write(EXAMPLES / folder / "filter2c.h", runtime)

    # Examples written entirely by the tool.
    for folder, design, name in (
        ("ESP32SelfTest", butterworth_lowpass(4, 40, 1000), "lp40"),
        ("ESP32SelfTestHighpass", butterworth_highpass(2, 0.5, 250), "hp"),
        ("ESP32SelfTestEcg", butterworth_bandpass(2, 0.5, 40, 250), "ecg"),
        ("ESP32SelfTestNotch", notch(50, 30, 1000), "notch50"),
    ):
        for path in create_sketch(design, name, EXAMPLES / folder):
            print("wrote", path.relative_to(ROOT))
    for path in create_live_sketch(butterworth_lowpass(4, 40, 1000), "lp40", EXAMPLES / "LiveCheck40Hz"):
        print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
