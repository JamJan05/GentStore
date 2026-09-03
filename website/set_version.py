#!/usr/bin/env python3
"""The application's version and test count, in every place the site states them.

    python set_version.py --check             every place agrees, and with what
    python set_version.py --check 1.3.1       ... and what they agree on is 1.3.1
    python set_version.py 1.3.1               rewrite the version
    python set_version.py 1.3.1 --tests 576   rewrite both
    python set_version.py --tests 576         rewrite only the count

Two JSON files state the version three times between them and the test count
four, and until now every one of those was a hand edit made after the release
rather than as part of it. That is how the page came to announce 1.3.0 while
`emerge` was already installing 1.3.1: nothing about cutting a release touched
this branch, and nothing here could tell that it had been left behind.

`.github/workflows/website-version.yml` on `main` checks this branch out and
runs this, with the version the release it follows has just tagged. `--check` is
the half the test suite runs, so the two language files cannot drift apart from
each other even between releases.

What this deliberately does not touch is `status.changes_title` — the "New in
X" heading over the hand-written list of that release's highlights. Moving it
would relabel 1.3.0's list as 1.3.1's, which is a lie the reader cannot check.
The script says so on its way out instead, and writing the new list stays a
decision a person makes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CONTENT_DIR = Path(__file__).resolve().parent / "content"

#: Every path through a content file that states which release is current. They
#: are addressed by path rather than by a pattern over the raw text, so that the
#: English "Version 1.3.0" and the Polish "Wersja 1.3.0" need no wording in here
#: to be found — a third language would be covered the day it is added.
VERSION_AT: tuple[tuple[str, ...], ...] = (
    ("header", "version"),
    ("status", "title"),
)

#: The same, for the number of tests. ``hero.badges`` is a list, and the entry
#: carrying the count is picked out by the pattern below rather than by index.
COUNT_AT: tuple[tuple[str, ...], ...] = (
    ("hero", "badges"),
    ("status", "caveat", "body"),
)

#: The heading this script reports on and never rewrites. See the module docstring.
NOTES_AT: tuple[str, ...] = ("status", "changes_title")

VERSION_RE = re.compile(r"\d+\.\d+\.\d+")

#: The count leads its sentence in both languages — "572 tests pass", "572 testy
#: przechodzą" — and anchoring to the start is what keeps this out of "amd64" and
#: "Python 3.12+". If a rewording ever moves it, nothing matches and the script
#: stops, which is the point: a silent no-op is the failure it exists to prevent.
COUNT_RE = re.compile(r"^\d+\b")


class Mismatch(Exception):
    """A path that did not hold exactly one number to change."""


def content_files() -> list[Path]:
    files = sorted(CONTENT_DIR.glob("*.json"))
    if not files:
        raise SystemExit(f"no content files in {CONTENT_DIR}")
    return files


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, document: dict) -> None:
    """Write *document* back in the formatting the files are already in.

    ``indent=2`` with ``ensure_ascii=False`` reproduces them byte for byte, so a
    run that changes one number shows one line in the diff rather than the whole
    file re-punctuated.
    """
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def at(document: dict, path: tuple[str, ...]) -> list[str]:
    """The strings *path* leads to — one, or every entry of a list."""
    node: object = document
    for key in path:
        try:
            node = node[key]  # type: ignore[index]
        except (KeyError, TypeError) as error:
            raise Mismatch(f"{'.'.join(path)} is not in this file") from error
    return list(node) if isinstance(node, list) else [node]  # type: ignore[arg-type]


def stated(document: dict, path: tuple[str, ...], pattern: re.Pattern[str]) -> str:
    """The one number *pattern* finds under *path*."""
    found = [match for text in at(document, path) for match in pattern.findall(text)]
    if len(found) != 1:
        raise Mismatch(
            f"{'.'.join(path)} states {len(found)} numbers, not one — "
            "the wording moved and this script would have rewritten nothing"
        )
    return found[0]


def rewrite(document: dict, path: tuple[str, ...], pattern: re.Pattern[str], value: str) -> bool:
    """Put *value* under *path*. True if that changed anything."""
    stated(document, path, pattern)  # raises unless there is exactly one
    node: object = document
    for key in path[:-1]:
        node = node[key]  # type: ignore[index]
    key = path[-1]
    target = node[key]  # type: ignore[index]

    if isinstance(target, list):
        index = next(i for i, entry in enumerate(target) if pattern.search(entry))
        before = target[index]
        target[index] = pattern.sub(value, before, count=1)
        return target[index] != before

    before = target
    node[key] = pattern.sub(value, before, count=1)  # type: ignore[index]
    return node[key] != before  # type: ignore[index]


def notes_lag(document: dict, version: str) -> str | None:
    """The version the "New in X" heading names, when it is not *version*."""
    try:
        named = stated(document, NOTES_AT, VERSION_RE)
    except Mismatch:
        return None
    return named if named != version else None


def do_check(version: str | None, tests: str | None) -> int:
    """Every file states one version and one count, and they all agree."""
    agreed: dict[str, set[str]] = {"version": set(), "tests": set()}
    problems: list[str] = []

    for path in content_files():
        document = load(path)
        for what, places, pattern in (
            ("version", VERSION_AT, VERSION_RE),
            ("tests", COUNT_AT, COUNT_RE),
        ):
            for place in places:
                try:
                    agreed[what].add(stated(document, place, pattern))
                except Mismatch as error:
                    problems.append(f"{path.name}: {error}")

    for what, expected in (("version", version), ("tests", tests)):
        values = agreed[what]
        if len(values) > 1:
            problems.append(f"the {what} is stated as {', '.join(sorted(values))}")
        elif expected is not None and values and expected not in values:
            problems.append(f"the {what} is {values.pop()}, not the {expected} asked for")

    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1

    print(f"version {agreed['version'].pop()}, {agreed['tests'].pop()} tests: every place agrees")
    return 0


def do_set(version: str | None, tests: str | None) -> int:
    changed: list[str] = []

    for path in content_files():
        document = load(path)
        touched = False
        try:
            for value, places, pattern in (
                (version, VERSION_AT, VERSION_RE),
                (tests, COUNT_AT, COUNT_RE),
            ):
                if value is None:
                    continue
                for place in places:
                    touched |= rewrite(document, place, pattern, value)
        except Mismatch as error:
            print(f"error: {path.name}: {error}", file=sys.stderr)
            return 1

        if touched:
            save(path, document)
            changed.append(path.name)

        if version is not None and (lagging := notes_lag(document, version)):
            print(
                f"note: {path.name} still heads its highlights \"New in {lagging}\". "
                f"That list is written by hand, so it is left as it is.",
                file=sys.stderr,
            )

    print(f"changed: {', '.join(changed)}" if changed else "nothing to change")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="State the application's version and test count across the site's content."
    )
    parser.add_argument("version", nargs="?", help="the release, as X.Y.Z")
    parser.add_argument("--tests", metavar="N", help="how many tests pass")
    parser.add_argument(
        "--check", action="store_true", help="verify rather than rewrite, and change nothing"
    )
    args = parser.parse_args(argv)

    if args.version is not None and not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        parser.error(f"'{args.version}' is not an X.Y.Z release number")
    if args.tests is not None and not args.tests.isdigit():
        parser.error(f"'{args.tests}' is not a number of tests")
    if not args.check and args.version is None and args.tests is None:
        parser.error("give a version, --tests, or --check")

    return do_check(args.version, args.tests) if args.check else do_set(args.version, args.tests)


if __name__ == "__main__":
    raise SystemExit(main())
