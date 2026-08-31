#!/usr/bin/env python3
# GentStore — graphical frontend for Portage
# Copyright (C) 2026  JamJan05
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""The version number, in every place that states it.

    python tools/release.py current           print the version the tree claims
    python tools/release.py check [X.Y.Z]     verify every place agrees
    python tools/release.py bump X.Y.Z        rewrite every place, close the changelog
    python tools/release.py notes X.Y.Z       print that release's changelog section

Four files say what version this is, and before this script they said it in four
independent edits: 1.1.0 shipped with the README still announcing 1.0.0, which is
exactly the failure a release is least likely to notice. They are now written
together or not at all, and ``check`` is what the release workflow runs against a
tag before it will publish anything.

The ebuild is deliberately not on the list. A release ebuild carries no version —
``SRC_URI`` is built from ``${PV}`` and the file name supplies that — so there is
nothing in it to substitute. See .github/workflows/release.yml.
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PYPROJECT = ROOT / "pyproject.toml"
INIT = ROOT / "gentstore" / "__init__.py"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"

#: The patterns that find the number, each with it as their only group. Written
#: so that a substitution can reuse the same expression: group 1 is what changes,
#: and the surrounding text is matched literally, so a near-miss fails rather
#: than rewriting the wrong line. A file may state the version more than once —
#: the README does, once as a claim and once inside the installer transcript it
#: quotes — and every one of them has to move together or the file contradicts
#: itself in public.
VERSION_IN = {
    PYPROJECT: [re.compile(r'^version = "(\d+\.\d+\.\d+)"$', re.M)],
    INIT: [re.compile(r'^__version__ = "(\d+\.\d+\.\d+)"$', re.M)],
    README: [
        re.compile(r"^> \*\*Version (\d+\.\d+\.\d+)\.\*\*", re.M),
        # The transcript of what the installer prints, which offers the release
        # by number. Quoting a version nobody can install any more is exactly as
        # wrong as the claim above being stale.
        re.compile(r"^  1\) (\d+\.\d+\.\d+) — the release\.", re.M),
    ],
}

#: ``## [1.1.0] — 2026-08-31``, ``## [Unreleased]`` with no date, and a
#: withdrawn release, which Keep a Changelog marks in the heading rather than
#: deleting: ``## [1.1.1] — 2026-08-31 [YANKED]``. The marker has to be matched
#: here rather than ignored — an unrecognised heading is not a section boundary,
#: so a yanked release's notes would silently become part of the release above.
HEADING = re.compile(
    r"^## \[([^\]]+)\](?: — (\d{4}-\d{2}-\d{2}))?(?P<yanked> \[YANKED\])?$", re.M
)

#: ``[Unreleased]: https://…/compare/v1.1.0...HEAD``
UNRELEASED_LINK = re.compile(
    r"^\[Unreleased\]: (?P<base>https://\S+/compare/)"
    r"v(?P<previous>[^.\s]+(?:\.[^.\s]+)*)\.\.\.HEAD$",
    re.M,
)

RELEASE_NUMBER = re.compile(r"^\d+\.\d+\.\d+$")


def fail(message: str) -> None:
    print(f"release: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def stated(path: Path) -> list[str | None]:
    """Every version *path* claims — None where the line it should be on is gone."""
    body = read(path)
    return [(m.group(1) if (m := pattern.search(body)) else None) for pattern in VERSION_IN[path]]


def current() -> str:
    """pyproject.toml is the one that the build back end reads, so it decides."""
    version = stated(PYPROJECT)[0]
    if version is None:
        fail(f"no version line in {PYPROJECT.name}")
    return version


def sections(text: str) -> dict[str, tuple[str, str | None]]:
    """Every ``## [x]`` section of the changelog, as name -> (body, date)."""
    found = {}
    matches = list(HEADING.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end]
        # The link definitions live below the last section; they belong to the
        # file rather than to it.
        body = re.sub(r"\n\[[^\]]+\]: \S+$", "", body.rstrip(), flags=re.M)
        found[match.group(1)] = (body.strip("\n"), match.group(2))
    return found


def yanked(text: str) -> set[str]:
    """The releases marked withdrawn, which nothing should offer to install."""
    return {m.group(1) for m in HEADING.finditer(text) if m.group("yanked")}


# -- the subcommands ---------------------------------------------------------


def do_current(_: argparse.Namespace) -> None:
    print(current())


def do_check(args: argparse.Namespace) -> None:
    """Every place that states a version states the same one.

    Takes the expected number as an argument so that the workflow can hand it
    the tag it was triggered by: a tag whose tree still says the old version
    would otherwise publish a tarball whose ``--version`` contradicts its name.
    """
    expected = args.version or current()
    if not RELEASE_NUMBER.match(expected):
        fail(f"{expected} is not an X.Y.Z release number")

    wrong = []
    for path in VERSION_IN:
        for number, says in enumerate(stated(path), start=1):
            where = f"{path.relative_to(ROOT)}"
            if len(VERSION_IN[path]) > 1:
                where += f" (mention {number})"
            if says is None:
                wrong.append(f"{where}: the version line is gone")
            elif says != expected:
                wrong.append(f"{where}: says {says}, expected {expected}")

    found = sections(read(CHANGELOG))
    if expected not in found:
        wrong.append(f"CHANGELOG.md: no section for {expected}")
    elif found[expected][1] is None:
        wrong.append(f"CHANGELOG.md: the {expected} section carries no date")
    elif not found[expected][0]:
        wrong.append(f"CHANGELOG.md: the {expected} section is empty")

    if wrong:
        fail("the version is not stated consistently:\n  " + "\n  ".join(wrong))
    print(f"{expected}: pyproject.toml, gentstore/__init__.py, README.md, CHANGELOG.md agree")


def do_notes(args: argparse.Namespace) -> None:
    """The changelog section, which is what the GitHub release notes are.

    1.1.0 went out saying "No functional changes" over 21 commits, because the
    notes were written from a session's own diff instead of from the record.
    Printing them from the file removes the opportunity.
    """
    found = sections(read(CHANGELOG))
    if args.version not in found:
        fail(f"CHANGELOG.md has no section for {args.version}")
    body = found[args.version][0]
    if not body:
        fail(f"the {args.version} section of CHANGELOG.md is empty")
    print(body)


def do_bump(args: argparse.Namespace) -> None:
    """Write the new number everywhere and close the changelog's Unreleased section."""
    new = args.version.removeprefix("v")
    if not RELEASE_NUMBER.match(new):
        fail(f"{new} is not an X.Y.Z release number")

    previous = current()
    if tuple(map(int, new.split("."))) <= tuple(map(int, previous.split("."))):
        fail(f"{new} does not come after {previous}")

    text = read(CHANGELOG)
    found = sections(text)
    if "Unreleased" not in found:
        fail("CHANGELOG.md has no [Unreleased] section to release")
    if not found["Unreleased"][0]:
        fail(
            "the [Unreleased] section of CHANGELOG.md is empty.\n"
            "  A release whose notes have to be reconstructed afterwards is how\n"
            "  1.1.0 shipped claiming it changed nothing. Write them first."
        )
    if new in found:
        fail(f"CHANGELOG.md already has a section for {new}")

    date = args.date or datetime.date.today().isoformat()

    # The Unreleased heading stays where it is and the new one appears under it,
    # so the section that was Unreleased becomes this release's body untouched.
    text = text.replace("## [Unreleased]\n", f"## [Unreleased]\n\n## [{new}] — {date}\n", 1)

    link = UNRELEASED_LINK.search(text)
    if not link:
        fail("CHANGELOG.md has no [Unreleased]: compare link to move")
    base, before = link.group("base"), link.group("previous")
    text = text[: link.start()] + (
        f"[Unreleased]: {base}v{new}...HEAD\n[{new}]: {base}v{before}...v{new}"
    ) + text[link.end() :]
    CHANGELOG.write_text(text, encoding="utf-8")

    for path, patterns in VERSION_IN.items():
        body = read(path)
        for pattern in patterns:
            body, count = pattern.subn(
                lambda m: m.group(0).replace(m.group(1), new, 1), body, count=1
            )
            if count != 1:
                fail(f"{path.relative_to(ROOT)}: found no version line to rewrite")
        path.write_text(body, encoding="utf-8")

    for path in (*VERSION_IN, CHANGELOG):
        print(f"  {path.relative_to(ROOT)}")
    print(f"{previous} -> {new}, dated {date}")


COMMANDS = {
    "current": do_current,
    "check": do_check,
    "notes": do_notes,
    "bump": do_bump,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("current", help="print the version the tree claims")

    checking = sub.add_parser("check", help="verify every place states the same version")
    checking.add_argument("version", nargs="?", help="the version it should be, e.g. 1.2.0")

    noting = sub.add_parser("notes", help="print a release's changelog section")
    noting.add_argument("version")

    bumping = sub.add_parser("bump", help="rewrite every place and close [Unreleased]")
    bumping.add_argument("version")
    bumping.add_argument("--date", help="the release date (default: today)")

    args = parser.parse_args(argv)
    COMMANDS[args.command](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
