"""Tests for the maintenance scripts in tools/ (release notes, version bump)."""
import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_notes_for_the_current_version():
    notes = load("release_notes")
    text = notes.main("v" + notes.package_version())
    assert "First public version" in text or len(text) > 50
    assert "## " not in text.splitlines()[0]  # the heading itself is not part of the notes


@pytest.mark.parametrize("tag", ["0.1.0", "v1", "release", "v0.1.0 ", "v9.9.9"])
def test_release_notes_refuses_bad_or_mismatched_tags(tag):
    notes = load("release_notes")
    with pytest.raises(SystemExit):
        notes.main(tag)


def test_release_notes_refuses_a_version_without_a_changelog_section():
    notes = load("release_notes")
    with pytest.raises(SystemExit):
        notes.notes_for("9.9.9")


def test_bump_version_edits_exactly_the_four_places(tmp_path, monkeypatch):
    bump = load("bump_version")
    files = ["python/pyproject.toml", "python/src/filter2c/__init__.py", "library.properties",
             "src/filter2c.h"]
    for relative in files:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    (tmp_path / "python" / "src" / "filter2c" / "runtime").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(bump, "ROOT", tmp_path)
    monkeypatch.setattr(bump.subprocess, "run", lambda *a, **k: None)  # do not regenerate here
    bump.main("9.8.7")

    for relative in files:
        text = (tmp_path / relative).read_text(encoding="utf-8")
        assert "9.8.7" in text, relative
        assert "0.1.0" not in text, relative
    copied = (tmp_path / "python/src/filter2c/runtime/filter2c.h").read_text(encoding="utf-8")
    assert '#define FILTER2C_VERSION "9.8.7"' in copied
    # only the version line of each file changed
    for relative in files:
        old = (ROOT / relative).read_text(encoding="utf-8").splitlines()
        new = (tmp_path / relative).read_text(encoding="utf-8").splitlines()
        assert len(old) == len(new)
        assert sum(a != b for a, b in zip(old, new)) == 1, relative


@pytest.mark.parametrize("version", ["1.0", "v1.0.0", "1.0.0-rc1", ""])
def test_bump_version_refuses_a_bad_version(version):
    with pytest.raises(SystemExit):
        load("bump_version").main(version)
