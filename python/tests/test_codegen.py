import re

import numpy as np
import pytest

from filter2c import butterworth_lowpass, generate_header
from filter2c.codegen import check_name, float32_literal


@pytest.mark.parametrize("name", ["lp40", "_x", "Filter_1"])
def test_good_names(name):
    assert check_name(name) == name


@pytest.mark.parametrize("name", ["", "1abc", "a-b", "a b", "int", "class", "x;y", "a\nb"])
def test_bad_names(name):
    with pytest.raises(ValueError):
        check_name(name)


def test_float_literal_round_trips_exactly():
    rng = np.random.default_rng(1)
    values = np.concatenate([rng.standard_normal(500), [0.0, 1.0, -2.0, 1e-30, 3e5]])
    for v in values:
        text = float32_literal(float(v))
        assert text.endswith("f")
        assert np.float32(text[:-1]) == np.float32(v)


def test_float_literal_rejects_values_too_large_for_float():
    with pytest.raises(ValueError):
        float32_literal(1e300)


def test_header_structure():
    design = butterworth_lowpass(4, 40, 1000)
    header = generate_header(design, "lp40")
    assert "#ifndef FILTER2C_GENERATED_LP40_H" in header
    assert "#define LP40_SECTIONS 2u" in header
    assert '#include "filter2c.h"' in header
    assert header.endswith("\n")


def test_header_coefficients_equal_the_design_in_float32():
    design = butterworth_lowpass(4, 40, 1000)
    header = generate_header(design, "lp40")
    body = header.split("lp40_sections[LP40_SECTIONS] = {")[1].split("};")[0]
    numbers = [np.float32(n) for n in re.findall(r"-?\d[\d.e+-]*(?=f)", body)]
    expected = design.sos[:, [0, 1, 2, 4, 5]].astype(np.float32).ravel()
    assert np.array_equal(np.array(numbers), expected)


def test_header_for_other_orders():
    for order in (1, 2, 3, 5):
        header = generate_header(butterworth_lowpass(order, 40, 1000), "f")
        assert f"#define F_SECTIONS {(order + 1) // 2}u" in header
