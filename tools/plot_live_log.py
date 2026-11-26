"""Draw the figure for the README from a real live-check log.

Usage (from the repository root, needs matplotlib, which is not a dependency of the package):

    python tools/plot_live_log.py results/esp32-s3-live-log.txt examples/LiveCheck40Hz docs/images/live-check-40hz.png
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal

from filter2c.live import parse_live_log
from filter2c.target import META_FILE, _design_from_meta

# Colours: categorical slots 1 and 2 of a palette that passes the colour-blind checks
# (blue and orange, CVD separation 24.7). Text and the prediction line use neutral ink.
SURFACE, INK, INK2, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0", "#c9c8c2"
BLUE, ORANGE = "#2a78d6", "#eb6834"


def rise_time_ms(t_ms, y, low=0.1, high=0.9):
    """10 to 90 % rise time of a step from 0 to 4095, with linear interpolation."""
    t10 = np.interp(low * 4095, y, t_ms)
    t90 = np.interp(high * 4095, y, t_ms)
    return float(t90 - t10)


def main(log_path: str, sketch_dir: str, out_path: str) -> None:
    meta = json.loads((Path(sketch_dir) / META_FILE).read_text(encoding="utf-8"))
    design = _design_from_meta(meta)
    t_us, raw, board = parse_live_log(Path(log_path).read_text(encoding="utf-8"), int(meta["samples"]))
    t = (t_us - t_us[0]) / 1000.0
    scipy_out = signal.sosfilt(design.sos, raw)

    # one clean rising edge, away from the start-up transient
    rising = np.where((raw[1:] > 2000) & (raw[:-1] < 500))[0] + 1
    edge = int(rising[rising > 300][0])
    lo, hi = edge - 15, edge + 45
    seg = slice(lo, hi)

    # rise time from the monotonic part of the board output right after the edge
    after = slice(edge, edge + 30)
    board_rise = rise_time_ms(t[after], board[after])
    scipy_rise = rise_time_ms(t[after], scipy_out[after])
    print(f"10-90 % rise time: board {board_rise:.2f} ms, SciPy {scipy_rise:.2f} ms")

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    fig, (a, b) = plt.subplots(2, 1, figsize=(9.0, 6.6), facecolor=SURFACE,
                               gridspec_kw={"height_ratios": [1, 1.15], "hspace": 0.55})
    for ax in (a, b):
        ax.set_facecolor(SURFACE)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(AXIS)
        ax.tick_params(colors=INK2, labelsize=9, length=3)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_ylabel("ADC counts", color=INK2)
        ax.set_xlabel("time (ms)", color=INK2)
        ax.set_ylim(-800, 5000)

    a.axvspan(t[lo], t[hi], color=GRID, alpha=0.9, linewidth=0)
    a.plot(t, raw, color=BLUE, linewidth=1.3, solid_joinstyle="round")
    a.plot(t, board, color=ORANGE, linewidth=1.6)
    a.set_xlim(0, t[-1])
    a.set_title("5 Hz square wave read by the ADC, then filtered",
                loc="left", color=INK, fontsize=11, fontweight="bold", pad=22)
    a.legend(handles=[plt.Line2D([], [], color=BLUE, linewidth=2, label="raw ADC readings"),
                      plt.Line2D([], [], color=ORANGE, linewidth=2, label="filtered output")],
             loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=2, frameon=False,
             fontsize=9, labelcolor=INK, borderaxespad=0.2)
    a.text(t[(lo + hi) // 2], 4750, "zoomed below", color=INK2, fontsize=8.5, ha="center", va="center")

    b.plot(t[seg], raw[seg], color=BLUE, linewidth=1.5, marker="o", markersize=3.2)
    b.plot(t[seg], board[seg], color=ORANGE, linewidth=2.6)
    b.plot(t[seg], scipy_out[seg], color=INK, linewidth=1.2, linestyle=(0, (3, 4)))
    b.set_xlim(t[lo], t[hi])
    b.set_title("One rising edge in detail: the board's output follows SciPy's prediction",
                loc="left", color=INK, fontsize=11, fontweight="bold", pad=10)

    handles = [
        plt.Line2D([], [], color=BLUE, linewidth=2, label="raw ADC readings"),
        plt.Line2D([], [], color=ORANGE, linewidth=2, label="filtered output from the board"),
        plt.Line2D([], [], color=INK, linewidth=1.5, linestyle=(0, (4, 3)),
                   label="SciPy prediction from the same readings"),
    ]
    leg = b.legend(handles=handles, loc="lower right", frameon=False, fontsize=9, labelcolor=INK)
    b.text(t[lo] + 0.62 * (t[hi] - t[lo]), 3000,
           f"10 to 90 % rise time\nboard {board_rise:.1f} ms, SciPy {scipy_rise:.1f} ms",
           color=INK, fontsize=9, va="top")

    fig.text(0.01, 0.005,
             "Real ESP32-S3 run, GPIO2 wired to GPIO1, 4th-order Butterworth low-pass, 40 Hz, 1000 Hz sampling.",
             color=INK2, fontsize=8.5, ha="left", va="bottom")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=190, facecolor=SURFACE)
    print("wrote", out_path)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
