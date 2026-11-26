"""Checks that catch release mistakes: version numbers that disagree, missing files."""
import re
from pathlib import Path

import filter2c

ROOT = Path(__file__).resolve().parents[2]


def _first_group(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.MULTILINE)
    assert match, f"pattern {pattern!r} not found"
    return match.group(1)


def versions() -> dict:
    return {
        "python/pyproject.toml": _first_group(
            r'^version\s*=\s*"([^"]+)"', (ROOT / "python" / "pyproject.toml").read_text(encoding="utf-8")),
        "filter2c.__version__": filter2c.__version__,
        "library.properties": _first_group(
            r"^version=(\S+)", (ROOT / "library.properties").read_text(encoding="utf-8")),
        "src/filter2c.h": _first_group(
            r'#define FILTER2C_VERSION "([^"]+)"', (ROOT / "src" / "filter2c.h").read_text(encoding="utf-8")),
    }


def test_all_version_numbers_agree():
    found = versions()
    assert len(set(found.values())) == 1, found


def test_the_changelog_has_a_section_for_this_version():
    version = next(iter(versions().values()))
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(rf"^## {re.escape(version)}\b", changelog, re.MULTILINE)


def test_arduino_library_metadata_is_complete():
    text = (ROOT / "library.properties").read_text(encoding="utf-8")
    fields = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
    for key in ("name", "version", "author", "maintainer", "sentence", "paragraph",
                "category", "url", "architectures", "includes"):
        assert fields.get(key, "").strip(), key
    assert fields["name"] == "filter2c"
    assert fields["includes"] == "filter2c.h"
    assert (ROOT / "src" / fields["includes"]).exists()
    assert fields["url"].startswith("https://github.com/")


def test_the_python_package_ships_the_runtime_header_and_the_licence():
    package_dir = Path(filter2c.__file__).parent
    assert (package_dir / "runtime" / "filter2c.h").exists()
    assert (ROOT / "python" / "LICENSE").exists()
    assert "Abhishek Vijay Potekar" in (ROOT / "LICENSE").read_text(encoding="utf-8")
