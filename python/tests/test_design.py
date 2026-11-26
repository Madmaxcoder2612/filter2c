import numpy as np
import pytest
from scipy import signal

from filter2c import butterworth_lowpass


def test_order_four_gives_two_sections():
    design = butterworth_lowpass(4, 40, 1000)
    assert design.sos.shape == (2, 6)
    assert design.sections == 2


def test_sections_are_normalised():
    design = butterworth_lowpass(4, 40, 1000)
    assert np.all(design.sos[:, 3] == 1.0)


def test_gain_is_minus_3_db_at_cutoff_and_one_at_dc():
    design = butterworth_lowpass(4, 40, 1000)
    _, h = signal.sosfreqz(design.sos, worN=[0.0, 2 * np.pi * 40 / 1000])
    assert abs(h[0]) == pytest.approx(1.0, abs=1e-9)
    assert abs(h[1]) == pytest.approx(1 / np.sqrt(2), abs=1e-6)


@pytest.mark.parametrize("order", [1, 2, 3, 4, 5, 8])
def test_all_poles_inside_unit_circle(order):
    design = butterworth_lowpass(order, 40, 1000)
    for _b0, _b1, _b2, _a0, a1, a2 in design.sos:
        assert np.all(np.abs(np.roots([1.0, a1, a2])) < 1.0)


@pytest.mark.parametrize(
    "order, cutoff, fs",
    [
        (0, 40, 1000),
        (17, 40, 1000),
        (2.5, 40, 1000),
        (True, 40, 1000),
        (4, 0, 1000),
        (4, -5, 1000),
        (4, 500, 1000),
        (4, 600, 1000),
        (4, 40, 0),
        (4, 40, float("nan")),
        (4, float("inf"), 1000),
    ],
)
def test_bad_arguments_are_rejected(order, cutoff, fs):
    with pytest.raises(ValueError):
        butterworth_lowpass(order, cutoff, fs)
