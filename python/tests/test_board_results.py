"""Guards for the real ESP32-S3 results kept in results/.

The README quotes these runs. If the code or a sketch changes so that a saved log no
longer passes, or a committed example no longer matches what the tool generates, a
test fails and the README has to be looked at again.
"""
from pathlib import Path

import pytest

from filter2c import butterworth_bandpass, butterworth_highpass, notch
from filter2c.target import check_board_log, create_sketch

ROOT = Path(__file__).resolve().parents[2]

# folder in examples/, saved log in results/, design, filter name, cycles per sample on the board
RUNS = [
    ("ESP32SelfTestEcg", "esp32-s3-ecg-bandpass-board-log.txt",
     butterworth_bandpass(2, 0.5, 40, 250), "ecg", 46.0),
    ("ESP32SelfTestHighpass", "esp32-s3-highpass-board-log.txt",
     butterworth_highpass(2, 0.5, 250), "hp", 29.0),
    ("ESP32SelfTestNotch", "esp32-s3-notch-board-log.txt",
     notch(50, 30, 1000), "notch50", 26.0),
]
IDS = [run[0] for run in RUNS]


@pytest.mark.parametrize("folder, log, design, name, cycles", RUNS, ids=IDS)
def test_saved_board_log_passes(folder, log, design, name, cycles):
    text = (ROOT / "results" / log).read_text(encoding="utf-8")
    report = check_board_log(ROOT / "examples" / folder, text)
    assert report.passed
    assert report.cpu_mhz == 240
    assert report.cycles_per_sample == pytest.approx(cycles, abs=1.0)


@pytest.mark.parametrize("folder, log, design, name, cycles", RUNS, ids=IDS)
def test_committed_example_matches_the_tool(tmp_path, folder, log, design, name, cycles):
    fresh = tmp_path / folder
    create_sketch(design, name, fresh)
    committed = ROOT / "examples" / folder
    assert sorted(p.name for p in committed.iterdir()) == sorted(p.name for p in fresh.iterdir())
    for path in fresh.iterdir():
        assert (committed / path.name).read_bytes() == path.read_bytes(), path.name
    assert (committed / "filter2c.h").read_bytes() == (ROOT / "src" / "filter2c.h").read_bytes()
