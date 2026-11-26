"""Filter design: a small, validated layer on top of SciPy.

A filter is stored as second-order sections (biquads), which stay numerically
well behaved at higher orders. A single high-order polynomial does not.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import signal

MAX_ORDER = 16
MIN_Q = 0.5
MAX_Q = 100.0


@dataclass(frozen=True)
class FilterDesign:
    """A designed filter.

    ``sos`` has one row per biquad section: ``[b0, b1, b2, a0, a1, a2]``,
    normalised so that ``a0 == 1``.

    ``cutoff_hz`` is the -3 dB frequency of a low-pass filter, or the centre
    frequency of a notch filter. ``q`` is only set for a notch.
    """

    kind: str
    order: int
    fs_hz: float
    cutoff_hz: float
    sos: np.ndarray
    q: float | None = None

    @property
    def sections(self) -> int:
        return int(self.sos.shape[0])

    def describe(self) -> str:
        if self.q is not None:
            return (
                f"{self.kind}, frequency {self.cutoff_hz:g} Hz, Q {self.q:g}, "
                f"sampling {self.fs_hz:g} Hz"
            )
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


def notch(freq_hz: float, q: float, fs_hz: float) -> FilterDesign:
    """Design a digital notch filter that removes one frequency, such as 50 Hz mains hum.

    A notch passes everything except a narrow band around ``freq_hz``. The
    higher the quality factor ``q``, the narrower the band that is removed
    (its width at -3 dB is about ``freq_hz / q``).

    Args:
        freq_hz: centre frequency to remove. Must lie between 0 and fs_hz / 2.
        q: quality factor, 0.5 to 100.
        fs_hz: sampling rate in Hz.
    """
    if not np.isfinite(fs_hz) or fs_hz <= 0:
        raise ValueError(f"fs_hz must be a positive number, got {fs_hz!r}")
    if not np.isfinite(freq_hz) or not 0 < freq_hz < fs_hz / 2:
        raise ValueError(
            f"freq_hz must be between 0 and fs_hz / 2 = {fs_hz / 2:g}, got {freq_hz!r}"
        )
    if not np.isfinite(q) or not MIN_Q <= q <= MAX_Q:
        raise ValueError(f"q must be between {MIN_Q:g} and {MAX_Q:g}, got {q!r}")

    b, a = signal.iirnotch(freq_hz, q, fs=fs_hz)
    sos = signal.tf2sos(b, a)
    return FilterDesign(
        kind="Notch",
        order=2,
        fs_hz=float(fs_hz),
        cutoff_hz=float(freq_hz),
        sos=np.asarray(sos, dtype=np.float64),
        q=float(q),
    )
