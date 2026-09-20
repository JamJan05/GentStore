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
    python tools/release.py ebuild X.Y.Z      write that release's ebuild

Four files say what version this is, and before this script they said it in four
independent edits: 1.1.0 shipped with the README still announcing 1.0.0, which is
exactly the failure a release is least likely to notice. They are now written
together or not at all, and ``check`` is what the release workflow runs against a
tag before it will publish anything.

The ebuild states no version of its own — ``SRC_URI`` is built from ``${PV}`` and
the file name supplies that — so it is not in the rewriting above. It is written
here all the same, by ``ebuild``, because one part of it cannot be inherited from
the last release: what the package needs installed. See .github/workflows/release.yml.
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ATOM = ROOT / "packaging" / "app-portage" / "gentstore"
LIVE_EBUILD = ATOM / "gentstore-9999.ebuild"

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

#: ``gentstore-1.3.5.ebuild``, and a revision bump of one, which sorts after it.
EBUILD_NAME = re.compile(r"^gentstore-(\d+)\.(\d+)\.(\d+)(?:-r(\d+))?$")

#: The variables a release ebuild has to state exactly as the live one does.
#: Everything else about the two is meant to differ — one clones where the other
#: fetches — but what the package needs installed is not a property of how its
#: source arrived, and a release ebuild that is only ever copied from the last
#: release inherits the dependency list of whatever shipped before it and never
#: anything newer. dev-qt/qtsvg is how that was found: added to the live ebuild,
#: it would have reached no release ebuild ever.
DEPENDENCIES = ("DEPEND", "RDEPEND", "BDEPEND", "PDEPEND", "IDEPEND")


def fail(message: str) -> None:
    print(f"release: {message}", file=sys.stderr)
    raise SystemExit(1)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def stated(path: Path) -> list[list[str]]:
    """Every version *path* claims, grouped by the pattern that found it.

    Every match a pattern makes, not its first. A pattern here stands for a
    *known form* of the version, and nothing stops a file from using one form
    twice — a second install transcript, a translated section, a quoted example.
    Reading only the first and rewriting only the first is how the second copy
    goes stale with no check able to see it, which is precisely the failure this
    module exists to stop.

    An empty list is a form that has gone from the file altogether.
    """
    body = read(path)
    return [[m.group(1) for m in pattern.finditer(body)] for pattern in VERSION_IN[path]]


def current() -> str:
    """pyproject.toml is the one that the build back end reads, so it decides."""
    found = stated(PYPROJECT)[0]
    if not found:
        fail(f"no version line in {PYPROJECT.name}")
    return found[0]


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
        for number, found in enumerate(stated(path), start=1):
            where = f"{path.relative_to(ROOT)}"
            if len(VERSION_IN[path]) > 1:
                where += f" (mention {number})"
            if not found:
                wrong.append(f"{where}: the version line is gone")
                continue
            for occurrence, says in enumerate(found, start=1):
                if says == expected:
                    continue
                place = where if len(found) == 1 else f"{where}, occurrence {occurrence}"
                wrong.append(f"{place}: says {says}, expected {expected}")

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


def dependency_block(name: str) -> re.Pattern[str]:
    """``NAME="…"``, and the comment lines written directly above it.

    The comments come with it on purpose: in these ebuilds they are where the
    reason a dependency exists is written down, and a dependency carried into a
    release without its reason is one nobody can later decide to remove.

    A dependency string holds no quote of its own, so ``[^"]*`` is exactly the
    assignment and there is nothing here that needs a shell parser.
    """
    return re.compile(rf'(?:^#[^\n]*\n)*^{name}="[^"]*"$', re.M)


def with_live_dependencies(previous: str, live: str) -> str:
    """*previous* — the last release's ebuild — with *live*'s dependency blocks.

    Everything else in *previous* is what makes it a release ebuild and is kept:
    ``SRC_URI``, ``KEYWORDS``, the inherits, the install phases. Only what the
    package needs is replaced, because that is the one thing the last release
    cannot be a source of truth for.

    A block that is in one ebuild and not the other is refused rather than
    guessed at. Where a new variable belongs in a file is a decision, and a
    release is not the moment to have a script make it.
    """
    for name in DEPENDENCIES:
        pattern = dependency_block(name)
        theirs = list(pattern.finditer(live))
        ours = list(pattern.finditer(previous))
        if len(theirs) > 1 or len(ours) > 1:
            fail(f"{name} is stated more than once; which one counts is not for this to decide")
        if bool(theirs) != bool(ours):
            missing = "the last release's" if theirs else LIVE_EBUILD.name
            holds = LIVE_EBUILD.name if theirs else "the last release's"
            fail(
                f"{holds} ebuild states {name} and {missing} ebuild does not.\n"
                f"  Put it in both by hand once, then this can carry it every time."
            )
        if not theirs:
            continue
        here = ours[0]
        previous = previous[: here.start()] + theirs[0].group(0) + previous[here.end() :]
    return previous


def previous_release_ebuild(exclude: Path | None = None) -> Path:
    """The newest ebuild that *fetches*, which is not the same as the newest one.

    ``9999`` sorts above every release there will ever be, so picking by version
    alone picks the live ebuild and produces a release that clones from git.
    *exclude* is the file being written: a re-run over a release that already
    exists must still copy the one before it, not itself.
    """
    fetching = []
    for path in ATOM.glob("gentstore-*.ebuild"):
        if path == exclude or not re.search(r"^SRC_URI=", read(path), re.M):
            continue
        named = EBUILD_NAME.match(path.stem)
        if named:
            fetching.append((tuple(int(part or 0) for part in named.groups()), path))
    if not fetching:
        fail("there is no release ebuild to copy")
    return max(fetching)[1]


def do_ebuild(args: argparse.Namespace) -> None:
    """Write the ebuild for *version*: the last release's, with live dependencies.

    The release workflow used to do this with ``cp`` alone, and that is how a
    dependency added to gentstore-9999.ebuild reached no release: each release
    ebuild was a copy of the one before it, so the chain carried whatever 1.0.0
    happened to need and nothing since. The generated file is otherwise exactly
    what that ``cp`` produced.
    """
    version = args.version.removeprefix("v")
    if not RELEASE_NUMBER.match(version):
        fail(f"{version} is not an X.Y.Z release number")

    target = ATOM / f"gentstore-{version}.ebuild"
    previous = previous_release_ebuild(exclude=target)
    target.write_text(with_live_dependencies(read(previous), read(LIVE_EBUILD)), encoding="utf-8")

    print(f"  {target.relative_to(ROOT)}")
    print(f"copied from {previous.name}, dependencies from {LIVE_EBUILD.name}")


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

    # Worked out in full before a single byte is written. Every refusal above
    # happens before anything is touched, deliberately — a bump that stops
    # halfway leaves the tree stating two different versions at once — and this
    # loop used to be the exception: it wrote each file as it finished it, so a
    # pattern that missed in the *last* file refused after the first three were
    # already rewritten and the changelog already closed. Two files with two
    # patterns each is four chances to find that out the hard way.
    rewritten: dict[Path, str] = {}
    for path, patterns in VERSION_IN.items():
        body = read(path)
        for number, pattern in enumerate(patterns, start=1):
            # Every occurrence of the form, not just the first — see stated().
            body, count = pattern.subn(lambda m: m.group(0).replace(m.group(1), new, 1), body)
            if count == 0:
                where = f"{path.relative_to(ROOT)}"
                if len(patterns) > 1:
                    # Which mention drifted, not merely which file. do_check has
                    # said this since it grew a second README pattern; there is
                    # no reason for the message here to be the vaguer one.
                    where += f" (mention {number})"
                fail(f"{where}: found no version line to rewrite")
        rewritten[path] = body

    CHANGELOG.write_text(text, encoding="utf-8")
    for path, body in rewritten.items():
        path.write_text(body, encoding="utf-8")

    for path in (*VERSION_IN, CHANGELOG):
        print(f"  {path.relative_to(ROOT)}")
    print(f"{previous} -> {new}, dated {date}")


COMMANDS = {
    "current": do_current,
    "check": do_check,
    "notes": do_notes,
    "ebuild": do_ebuild,
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

    writing = sub.add_parser("ebuild", help="write that release's ebuild")
    writing.add_argument("version")

    bumping = sub.add_parser("bump", help="rewrite every place and close [Unreleased]")
    bumping.add_argument("version")
    bumping.add_argument("--date", help="the release date (default: today)")

    args = parser.parse_args(argv)
    COMMANDS[args.command](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
