import pytest

from filter2c.cli import main
from filter2c.verify import find_compiler


def test_writes_header_and_runtime(tmp_path, capsys):
    out = tmp_path / "out" / "lp.h"
    code = main(["butter-lowpass", "--order", "4", "--cutoff", "40", "--fs", "1000",
                 "--name", "lp", "-o", str(out), "--write-runtime"])
    assert code == 0
    assert "lp_sections" in out.read_text(encoding="utf-8")
    assert (tmp_path / "out" / "filter2c.h").exists()
    assert "stable" in capsys.readouterr().out


@pytest.mark.skipif(find_compiler() is None, reason="no C compiler available")
def test_verify_passes(tmp_path, capsys):
    code = main(["butter-lowpass", "--order", "4", "--cutoff", "40", "--fs", "1000",
                 "--name", "lp", "-o", str(tmp_path / "lp.h"), "--verify"])
    assert code == 0
    assert "PASS" in capsys.readouterr().out


@pytest.mark.skipif(find_compiler() is None, reason="no C compiler available")
def test_impossible_tolerance_fails(tmp_path):
    code = main(["butter-lowpass", "--order", "4", "--cutoff", "40", "--fs", "1000",
                 "--name", "lp", "-o", str(tmp_path / "lp.h"), "--verify", "--tolerance", "1e-12"])
    assert code == 1


@pytest.mark.parametrize("extra", [["--cutoff", "600"], ["--name", "int"], ["--order", "0"]])
def test_bad_input_returns_error_and_writes_nothing(tmp_path, extra):
    args = {"--order": "4", "--cutoff": "40", "--fs": "1000", "--name": "lp"}
    for key, value in zip(extra[::2], extra[1::2]):
        args[key] = value
    argv = ["butter-lowpass"] + [part for kv in args.items() for part in kv]
    argv += ["-o", str(tmp_path / "x.h")]
    assert main(argv) == 2
    assert not (tmp_path / "x.h").exists()
