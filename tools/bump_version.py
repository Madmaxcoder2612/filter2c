"""Change the version number everywhere it appears, and regenerate the files that contain it.

Usage (from the repository root, with the package installed in editable mode):

    python tools/bump_version.py 0.2.0

It edits python/pyproject.toml, python/src/filter2c/__init__.py, library.properties and
src/filter2c.h, copies the runtime header to the Python package, and regenerates the
examples. You still have to write the changelog section for the new version and run the tests.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# file, pattern with one group for the old version, replacement template
EDITS = (
    ("python/pyproject.toml", r'^(version\s*=\s*")[^"]+(")', r"\g<1>{v}\g<2>"),
    ("python/src/filter2c/__init__.py", r'^(__version__\s*=\s*")[^"]+(")', r"\g<1>{v}\g<2>"),
    ("library.properties", r"^(version=).+$", r"\g<1>{v}"),
    ("src/filter2c.h", r'^(#define FILTER2C_VERSION ")[^"]+(")', r"\g<1>{v}\g<2>"),
)


def main(version: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"error: {version!r} is not a version like 0.2.0")
    for relative, pattern, template in EDITS:
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        new_text, count = re.subn(pattern, template.format(v=version), text, count=1, flags=re.MULTILINE)
        if count != 1:
            raise SystemExit(f"error: no version found in {relative}")
        path.write_text(new_text, encoding="utf-8", newline="\n")
        print("updated", relative)

    shutil.copyfile(ROOT / "src" / "filter2c.h", ROOT / "python" / "src" / "filter2c" / "runtime" / "filter2c.h")
    print("copied src/filter2c.h to python/src/filter2c/runtime/")
    # a fresh interpreter, so that it imports the new version number
    subprocess.run([sys.executable, str(ROOT / "tools" / "regenerate_examples.py")], check=True, cwd=ROOT)
    print(f"\nVersion is now {version}. Next: add a '## {version}' section to CHANGELOG.md, run the tests, commit.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
