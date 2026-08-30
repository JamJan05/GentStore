#!/usr/bin/env python3
"""Update and compile the translation catalogues.

    python tools/i18n.py update    # rescan the sources, refresh the .ts files
    python tools/i18n.py compile   # build the .qm files the application loads
    python tools/i18n.py all       # both

``.ts`` files are tracked in git; ``.qm`` files are generated and ignored.
See Docs/03-i18n.md for the conventions the catalogues follow.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "gentstore"
I18N_DIR = SOURCE_DIR / "i18n"
LANGUAGES = ("pl", "en")

#: Qt installs its tools outside PATH on several distributions, Gentoo included.
EXTRA_TOOL_DIRS = (
    Path("/usr/lib64/qt6/bin"),
    Path("/usr/lib/qt6/bin"),
    Path("/usr/lib/x86_64-linux-gnu/qt6/bin"),
)


def find_tool(*names: str) -> Path | None:
    """Locate the first of *names* in PATH or in a known Qt tool directory."""
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found)
        for directory in EXTRA_TOOL_DIRS:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def sources() -> list[str]:
    return sorted(str(p) for p in SOURCE_DIR.rglob("*.py"))


#: The extractor, pinned rather than "whichever is installed".
#:
#: pylupdate6 and lupdate disagree about details — most visibly, lupdate reads
#: ``#:`` comments as translator notes and pylupdate6 does not — so a catalogue
#: written by one and then refreshed by the other ends up with every message
#: twice: the old one marked ``vanished``, a fresh one marked ``unfinished``.
#: That happened here once, the day dev-python/pyqt6 was installed and
#: pylupdate6 appeared in PATH mid-project.
#:
#: pylupdate6 wins because it ships with PyQt6, which the application needs
#: anyway; lupdate would mean also installing dev-qt/qttools.
EXTRACTOR = "pylupdate6"


def update() -> int:
    tool = find_tool(EXTRACTOR)
    if tool is None:
        print(
            f"error: {EXTRACTOR} was not found. It comes with dev-python/pyqt6.\n"
            "Refusing to fall back to lupdate: the two tools write incompatible "
            "catalogues and mixing them duplicates every message.",
            file=sys.stderr,
        )
        return 1

    failures = 0
    for language in LANGUAGES:
        target = I18N_DIR / f"gentstore_{language}.ts"
        command = [str(tool), *sources(), "-ts", str(target)]
        print("→", tool.name, "…", target.name)
        failures += subprocess.run(command, check=False).returncode != 0
    return 1 if failures else 0


def compile_catalogues() -> int:
    tool = find_tool("lrelease", "lrelease-qt6", "pylrelease6")
    if tool is None:
        print("error: lrelease (dev-qt/qttools[linguist]) was not found", file=sys.stderr)
        return 1

    failures = 0
    for language in LANGUAGES:
        source = I18N_DIR / f"gentstore_{language}.ts"
        if not source.is_file():
            print(f"skipping {source.name}: not present")
            continue
        target = source.with_suffix(".qm")
        print("→", tool.name, source.name, "→", target.name)
        failures += subprocess.run(
            [str(tool), str(source), "-qm", str(target)], check=False
        ).returncode != 0
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "all"
    if command == "update":
        return update()
    if command == "compile":
        return compile_catalogues()
    if command == "all":
        return update() or compile_catalogues()
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
