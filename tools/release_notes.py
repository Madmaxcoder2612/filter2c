"""Check that a release tag is consistent and print its changelog section.

Usage:

    python tools/release_notes.py v0.1.0

It stops with an error if the tag does not match the version in python/pyproject.toml, or if
CHANGELOG.md has no section for that version. Otherwise it prints the section, which the
release workflow uses as the text of the GitHub release.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package_version() -> str:
    text = (ROOT / "python" / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit("error: no version found in python/pyproject.toml")
    return match.group(1)


def notes_for(version: str) -> str:
    """The changelog text under the heading '## <version>', without the heading."""
    lines = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^## {re.escape(version)}\b", line):
            start = i + 1
            break
    if start is None:
        raise SystemExit(f"error: CHANGELOG.md has no section '## {version}'")
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    notes = "\n".join(lines[start:end]).strip()
    if not notes:
        raise SystemExit(f"error: the changelog section for {version} is empty")
    return notes


def main(tag: str) -> str:
    if not re.fullmatch(r"v\d+\.\d+\.\d+([.-]?[A-Za-z0-9]+)*", tag):
        raise SystemExit(f"error: {tag!r} is not a version tag like v0.1.0")
    version = tag[1:]
    if version != package_version():
        raise SystemExit(
            f"error: the tag {tag} does not match the package version {package_version()}"
        )
    return notes_for(version)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print(main(sys.argv[1]))
