"""Filter design: a small, validated layer on top of SciPy.

A filter is stored as second-order sections (biquads), which stay numerically
well behaved at higher orders. A single high-order polynomial does not.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import signal

MAX_ORDER = 16


@dataclass(frozen=True)
class FilterDesign:
    """A designed filter.

    ``sos`` has one row per biquad section: ``[b0, b1, b2, a0, a1, a2]``,
    normalised so that ``a0 == 1``.
    """

    kind: str
    order: int
    fs_hz: float
    cutoff_hz: float
    sos: np.ndarray

    @property
    def sections(self) -> int:
        return int(self.sos.shape[0])

    def describe(self) -> str:
        return (
            f"{self.kind}, order {self.order}, cutoff {self.cutoff_hz:g} Hz, "
            f"sampling {self.fs_hz:g} Hz"
        )


def butterworth_lowpass(order: int, cutoff_hz: float, fs_hz: float) -> FilterDesign:
    """Design a digital Butterworth low-pass filter.

    Args:
        order: filter order, 1 to 16.
        cutoff_hz: -3 dB frequency in Hz. Must lie between 0 and fs_hz / 2.
        fs_hz: sampling rate in Hz.
    """
    if isinstance(order, bool) or not isinstance(order, (int, np.integer)):
        raise ValueError(f"order must be an integer, got {order!r}")
    if not 1 <= order <= MAX_ORDER:
        raise ValueError(f"order must be between 1 and {MAX_ORDER}, got {order}")
    if not np.isfinite(fs_hz) or fs_hz <= 0:
        raise ValueError(f"fs_hz must be a positive number, got {fs_hz!r}")
    if not np.isfinite(cutoff_hz) or not 0 < cutoff_hz < fs_hz / 2:
        raise ValueError(
            f"cutoff_hz must be between 0 and fs_hz / 2 = {fs_hz / 2:g}, got {cutoff_hz!r}"
        )

    sos = signal.butter(int(order), cutoff_hz, btype="low", fs=fs_hz, output="sos")
    return FilterDesign(
        kind="Butterworth low-pass",
        order=int(order),
        fs_hz=float(fs_hz),
        cutoff_hz=float(cutoff_hz),
        sos=np.asarray(sos, dtype=np.float64),
    )
