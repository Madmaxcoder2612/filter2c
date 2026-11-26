import numpy as np
import pytest
from scipy import signal

from filter2c import (
    butterworth_bandpass,
    butterworth_highpass,
    generate_header,
    runtime_header,
)
from filter2c.cli import main
from filter2c.target import _design_from_meta, _design_parameters, check_board_log, create_sketch
from filter2c.verify import find_compiler, measure_attenuation
from test_target import needs_cpp, run_sketch_on_pc

needs_compiler = pytest.mark.skipif(find_compiler() is None, reason="no C compiler available")


def gain(design, frequencies_hz):
    """Gain of the design at some frequencies, from SciPy's frequency response."""
    w = 2 * np.pi * np.asarray(frequencies_hz, dtype=float) / design.fs_hz
    _, h = signal.sosfreqz(design.sos, worN=w)
    return np.abs(h)


# ---------------------------------------------------------------- design

@pytest.mark.parametrize("order, sections", [(1, 1), (2, 1), (3, 2), (4, 2)])
def test_highpass_section_count(order, sections):
    design = butterworth_highpass(order, 0.5, 250)
    assert design.sections == sections
    assert np.all(design.sos[:, 3] == 1.0)
    assert design.high_hz is None and design.q is None


@pytest.mark.parametrize("order", [1, 2, 3, 4])
def test_bandpass_has_one_section_per_order_and_both_edges(order):
    design = butterworth_bandpass(order, 0.5, 40, 250)
    assert design.sections == order
    assert np.all(design.sos[:, 3] == 1.0)
    assert (design.cutoff_hz, design.high_hz) == (0.5, 40)
    assert "0.5 to 40 Hz" in design.describe()


def test_highpass_gain_at_dc_cutoff_and_nyquist():
    design = butterworth_highpass(4, 40, 1000)
    dc, at_cutoff, nyquist = gain(design, [1e-6, 40, 499.999])
    assert dc < 1e-6
    assert at_cutoff == pytest.approx(1 / np.sqrt(2), abs=1e-6)
    assert nyquist == pytest.approx(1.0, abs=1e-6)


def test_bandpass_edges_are_minus_3_db_and_the_middle_passes():
    design = butterworth_bandpass(2, 20, 100, 1000)
    low, high, middle, far_below, far_above = gain(design, [20, 100, 45, 2, 400])
    assert low == pytest.approx(1 / np.sqrt(2), abs=1e-6)
    assert high == pytest.approx(1 / np.sqrt(2), abs=1e-6)
    assert middle > 0.98
    assert far_below < 0.01 and far_above < 0.05


@pytest.mark.parametrize("order", [1, 2, 3, 4, 6])
def test_poles_inside_unit_circle(order):
    for design in (butterworth_highpass(order, 5, 250), butterworth_bandpass(order, 0.5, 40, 250)):
        for _b0, _b1, _b2, _a0, a1, a2 in design.sos:
            assert np.all(np.abs(np.roots([1.0, a1, a2])) < 1.0)


@pytest.mark.parametrize(
    "args",
    [(0, 5, 250), (17, 5, 250), (2.5, 5, 250), (True, 5, 250), (2, 0, 250), (2, 125, 250),
     (2, 300, 250), (2, 5, 0), (2, float("nan"), 250)],
)
def test_bad_highpass_arguments_are_rejected(args):
    with pytest.raises(ValueError):
        butterworth_highpass(*args)


@pytest.mark.parametrize(
    "args",
    [(0, 0.5, 40, 250), (2, 40, 0.5, 250), (2, 40, 40, 250), (2, 0, 40, 250),
     (2, 0.5, 125, 250), (2, 0.5, 200, 250), (2, 0.5, 40, 0), (2, 0.5, float("nan"), 250)],
)
def test_bad_bandpass_arguments_are_rejected(args):
    with pytest.raises(ValueError):
        butterworth_bandpass(*args)


# ------------------------------------------- compiled C code, checked two ways

@needs_compiler
@pytest.mark.parametrize("order", [2, 4])
def test_c_highpass_gain_matches_the_closed_form(order):
    """Independent of SciPy: |H|^2 = 1 / (1 + (tan(pi fc / fs) / tan(pi f / fs)) ** (2 n))."""
    fs, fc = 1000.0, 40.0
    design = butterworth_highpass(order, fc, fs)
    header, runtime = generate_header(design, "f"), runtime_header()
    for f in (10.0, 20.0, 40.0, 80.0, 200.0):
        result = measure_attenuation(design, header, runtime, "f", frequency_hz=f, minimum_db=-100)
        measured = 10 ** (-result.attenuation_db / 20)
        expected = 1 / np.sqrt(1 + (np.tan(np.pi * fc / fs) / np.tan(np.pi * f / fs)) ** (2 * order))
        assert measured == pytest.approx(expected, rel=0.01, abs=1e-4), f


@needs_compiler
def test_c_bandpass_frequency_response_matches_scipy():
    fs = 1000.0
    design = butterworth_bandpass(2, 20, 100, fs)
    header, runtime = generate_header(design, "f"), runtime_header()
    for f in (5.0, 10.0, 20.0, 45.0, 100.0, 200.0, 300.0):
        result = measure_attenuation(design, header, runtime, "f", frequency_hz=f, minimum_db=-100)
        expected_db = -20 * np.log10(gain(design, [f])[0])
        assert result.attenuation_db == pytest.approx(expected_db, abs=0.3), f


@needs_compiler
def test_ecg_bandpass_at_250_hz_is_accurate_enough_in_float32():
    design = butterworth_bandpass(2, 0.5, 40, 250)
    header, runtime = generate_header(design, "ecg"), runtime_header()
    for f in (1.0, 10.0, 80.0):
        result = measure_attenuation(design, header, runtime, "ecg", frequency_hz=f, minimum_db=-100)
        reference = -20 * np.log10(gain(design, [f])[0])
        assert result.attenuation_db == pytest.approx(reference, abs=0.3), f


# ------------------------------------------------------------------- CLI

@needs_compiler
def test_cli_highpass_and_bandpass_verify(tmp_path, capsys):
    assert main(["butter-highpass", "--order", "2", "--cutoff", "2", "--fs", "250", "--name", "hp",
                 "-o", str(tmp_path / "hp.h"), "--verify"]) == 0
    assert main(["butter-bandpass", "--order", "2", "--low", "0.5", "--high", "40", "--fs", "250",
                 "--name", "ecg", "-o", str(tmp_path / "ecg.h"), "--verify"]) == 0
    out = capsys.readouterr().out
    assert out.count("PASS") == 2
    assert "passband 0.5 to 40 Hz" in out


@needs_compiler
def test_cli_reports_the_float32_limit_for_the_ecg_band_at_1_khz(tmp_path, capsys):
    """At 1 kHz sampling the 0.5 Hz edge is too close to DC for 32-bit float. The tool must say so.

    (Double precision output is planned. When it exists this test should use the default
    float output and keep expecting a failure.)
    """
    code = main(["butter-bandpass", "--order", "2", "--low", "0.5", "--high", "40", "--fs", "1000",
                 "--name", "ecg", "-o", str(tmp_path / "ecg.h"), "--verify"])
    captured = capsys.readouterr()
    assert code == 1
    assert "FAIL" in captured.out and "hint:" in captured.err


@pytest.mark.parametrize(
    "argv",
    [
        ["butter-highpass", "--order", "2", "--cutoff", "300", "--fs", "250"],
        ["butter-highpass", "--order", "0", "--cutoff", "2", "--fs", "250"],
        ["butter-bandpass", "--order", "2", "--low", "40", "--high", "0.5", "--fs", "250"],
        ["butter-bandpass", "--order", "2", "--low", "0.5", "--high", "125", "--fs", "250"],
        ["butter-bandpass", "--order", "2", "--low", "0.5", "--high", "40", "--fs", "250",
         "--name", "int"],
    ],
)
def test_cli_bad_input_returns_error_and_writes_nothing(tmp_path, argv):
    assert main(argv + ["-o", str(tmp_path / "x.h")]) == 2
    assert not (tmp_path / "x.h").exists()


# ---------------------------------------------------- board self-test sketch

@pytest.mark.parametrize(
    "design",
    [butterworth_highpass(2, 2, 250), butterworth_bandpass(2, 2, 40, 250)],
    ids=["highpass", "bandpass"],
)
def test_design_survives_the_metadata_round_trip(design):
    meta = {**_design_parameters(design), "fs_hz": design.fs_hz}
    again = _design_from_meta(meta)
    assert again.kind == design.kind
    assert np.array_equal(again.sos, design.sos)


@needs_cpp
@pytest.mark.parametrize(
    "design",
    [butterworth_highpass(2, 2, 250), butterworth_bandpass(2, 2, 40, 250)],
    ids=["highpass", "bandpass"],
)
def test_sketch_runs_on_the_pc_and_passes_the_board_check(tmp_path, design):
    folder = tmp_path / "Sketch"
    create_sketch(design, "f", folder)
    report = check_board_log(folder, run_sketch_on_pc(folder, tmp_path))
    assert report.passed


def test_cli_target_sketch_for_the_new_filters(tmp_path):
    assert main(["target-sketch", "butter-highpass", "--order", "2", "--cutoff", "2", "--fs", "250",
                 "--name", "hp", "-o", str(tmp_path / "HpSketch")]) == 0
    assert main(["target-sketch", "butter-bandpass", "--order", "2", "--low", "2", "--high", "40",
                 "--fs", "250", "--name", "bp", "-o", str(tmp_path / "BpSketch")]) == 0
    assert (tmp_path / "HpSketch" / "hp.h").exists() and (tmp_path / "BpSketch" / "bp.h").exists()
