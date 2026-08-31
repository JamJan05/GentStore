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

"""Diagnostic front end for the ``core`` layer.

Every screen of Gentstore is built on the functions in this package, and being
able to call them without starting Qt makes the difference between "the list is
empty, why?" and "the list is empty because ``cp_all`` returns nothing for that
overlay". It is a developer tool, so its output is English only and deliberately
plain — the translated, designed presentation is the graphical interface's job.

::

    python -m gentstore.core.cli info
    python -m gentstore.core.cli search mpv
    python -m gentstore.core.cli show media-video/mpv
    python -m gentstore.core.cli repos
    python -m gentstore.core.cli world
    python -m gentstore.core.cli index --json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys
import time
from datetime import datetime
from typing import Any

from . import packages as pkgs
from . import repos as repos_mod
from . import worldset
from .portage_env import PortageUnavailableError
from .portage_env import env as _env

_SIZE_UNITS = ("B", "KiB", "MiB", "GiB", "TiB")


def human_size(size: int | None) -> str:
    if size is None:
        return "?"
    value = float(size)
    for unit in _SIZE_UNITS:
        if value < 1024 or unit == _SIZE_UNITS[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} {_SIZE_UNITS[-1]}"  # pragma: no cover - unreachable


def _stamp(moment: datetime | None) -> str:
    return moment.strftime("%Y-%m-%d %H:%M") if moment else "never"


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    return str(value)


def _note(text: str) -> None:
    """A summary line on stderr, so piping stdout stays clean.

    stdout is flushed first: the two streams are buffered differently, and
    without this the summary would surface above the results it counts.
    """
    sys.stdout.flush()
    print(f"\n{text}", file=sys.stderr)


def _emit(payload: Any) -> None:
    print(json.dumps(payload, indent=2, default=_json_default, ensure_ascii=False))


def _as_dict(value: Any) -> Any:
    return dataclasses.asdict(value) if dataclasses.is_dataclass(value) else value


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------


def cmd_info(args: argparse.Namespace) -> int:
    env = _env()
    import portage  # noqa: PLC0415

    data = {
        "portage_version": getattr(portage, "VERSION", None),
        "python": sys.version.split()[0],
        "root": env.root,
        "eroot": env.eroot,
        "arch": env.arch,
        "accept_keywords": list(env.accept_keywords),
        "main_repo": env.main_repo_name,
        "repositories": list(env.repo_names),
        "makeopts": env.settings.get("MAKEOPTS"),
        "features": (env.settings.get("FEATURES") or "").split(),
        "installed": len(env.vardb.cpv_all()),
        "world": len(worldset.read_world_atoms(env)),
    }
    if args.json:
        _emit(data)
        return 0
    print(f"Portage      {data['portage_version']}   (python {data['python']})")
    print(f"ROOT         {data['root']}")
    print(f"ARCH         {data['arch']}   ACCEPT_KEYWORDS: {' '.join(data['accept_keywords'])}")
    print(f"MAKEOPTS     {data['makeopts']}")
    print(f"Repositories {', '.join(data['repositories'])}   (main: {data['main_repo']})")
    print(f"Installed    {data['installed']} packages, @world has {data['world']} entries")
    return 0


def cmd_repos(args: argparse.Namespace) -> int:
    entries = repos_mod.list_repositories(count_packages=not args.fast)
    if args.json:
        _emit([_as_dict(entry) for entry in entries])
        return 0
    width = max((len(entry.name) for entry in entries), default=4)
    print(f"{'REPO'.ljust(width + 1)} {'PACKAGES':>8}  {'PRIO':>5}  {'LAST SYNC':16}  LOCATION")
    for entry in entries:
        count = "?" if entry.package_count is None else str(entry.package_count)
        priority = "-" if entry.priority is None else str(entry.priority)
        marker = "*" if entry.is_main else " "
        print(
            f"{entry.name.ljust(width)}{marker} {count:>8}  {priority:>5}  "
            f"{_stamp(entry.last_sync):16}  {entry.location}"
        )
        if args.verbose:
            pad = " " * (width + 2)
            print(f"{pad} sync:    {entry.sync_type or '-'}  {entry.sync_uri or '-'}")
            print(f"{pad} masters: {', '.join(entry.masters) or '-'}")
    return 0


def _index(args: argparse.Namespace) -> pkgs.SearchIndex:
    return pkgs.SearchIndex.build(_env(), _progress if getattr(args, "progress", False) else None)


def _progress(done: int, total: int) -> None:
    print(f"\rindexing {done}/{total}", end="", file=sys.stderr, flush=True)
    if done >= total:
        print(file=sys.stderr)


def cmd_index(args: argparse.Namespace) -> int:
    index = _index(args)
    data = {
        "packages": len(index),
        "repositories": list(index.repos),
        "installed": len(index.installed),
        "build_seconds": round(index.build_seconds, 3),
    }
    if args.json:
        _emit(data)
        return 0
    print(
        f"{data['packages']} packages from {', '.join(data['repositories'])} "
        f"in {data['build_seconds']:.2f} s "
        f"({data['installed']} of them installed)"
    )
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    index = _index(args)
    started = time.monotonic()
    results = index.search(
        args.query,
        repos=tuple(args.repo) if args.repo else None,
        only_installed=args.installed,
        match_description=not args.names_only,
        limit=args.limit,
    )
    elapsed = time.monotonic() - started
    if args.json:
        _emit([_as_dict(item) for item in results])
        return 0
    if not results:
        print(f"No package matches {args.query!r}.")
        return 1
    width = max(len(item.cp) for item in results)
    for item in results:
        mark = "I" if item.installed else " "
        repos = ",".join(item.repos)
        print(f"{mark} {item.cp.ljust(width)}  [{repos}]  {item.description}")
    _note(f"{len(results)} result(s) in {elapsed * 1000:.1f} ms")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    cp = pkgs.resolve_cp(args.atom)
    if cp is None:
        index = _index(args)
        cp = pkgs.resolve_cp(args.atom, index)
        if cp is None:
            candidates = pkgs.matching_cps(args.atom, index)
            if candidates:
                print(f"{args.atom!r} is ambiguous: {', '.join(candidates)}", file=sys.stderr)
            else:
                print(f"{args.atom!r} is neither an atom nor a package name.", file=sys.stderr)
            return 2
    repo = getattr(args, "repo", "") or ""
    try:
        info = pkgs.details(cp, repo=repo)
    except pkgs.UnknownPackageError:
        where = f" in ::{repo}" if repo else ""
        print(f"No such package: {cp}{where}", file=sys.stderr)
        return 1

    if args.json:
        _emit(_as_dict(info))
        return 0

    print(f"{info.cp}")
    print(f"  description  {info.description}")
    print(f"  homepage     {' '.join(info.homepage) or '-'}")
    print(f"  licence      {info.license or '-'}")
    print(f"  repositories {', '.join(info.repos) or '-'}")
    print(f"  download     {human_size(info.download_size)}")
    print(f"  best visible {info.best_visible or '-'}")
    if info.installed:
        print("  installed:")
        for entry in info.installed:
            print(
                f"    {entry.version}  slot {entry.slot}  ::{entry.repo}  "
                f"{human_size(entry.size)}  built {_stamp(entry.build_time)}"
            )
    else:
        print("  installed:   no")
    print("  versions:")
    for version in info.versions:
        flags = []
        if version.installed:
            flags.append("installed")
        if version.masking:
            flags.append("masked: " + ", ".join(version.masking))
        elif not version.masking_known:
            flags.append("masking unknown: Portage would not say")
        suffix = f"   ({'; '.join(flags)})" if flags else ""
        print(
            f"    {version.version:<20} ::{version.repo:<14} slot {version.slot_display:<8} "
            f"{version.keywording.value}{suffix}"
        )
    return 0


def cmd_world(args: argparse.Namespace) -> int:
    env = _env()
    entries = worldset.world_entries(env)
    sets = worldset.read_world_sets(env)
    if args.json:
        _emit({"atoms": [_as_dict(entry) for entry in entries], "sets": list(sets)})
        return 0
    width = max((len(entry.atom) for entry in entries), default=4)
    for entry in entries:
        versions = ", ".join(p.version for p in entry.installed) or "NOT INSTALLED"
        print(f"{entry.atom.ljust(width)}  {versions}")
    if sets:
        print(f"\nsets: {', '.join(sets)}")
    _note(f"{len(entries)} entries")
    return 0


def cmd_installed(args: argparse.Namespace) -> int:
    entries = worldset.installed_packages(_env())
    if args.filter:
        needle = args.filter.lower()
        entries = tuple(e for e in entries if needle in e.cp.lower())
    if args.json:
        _emit([_as_dict(entry) for entry in entries])
        return 0
    width = max((len(entry.cpv) for entry in entries), default=4)
    for entry in entries:
        print(
            f"{entry.cpv.ljust(width)}  ::{entry.repo:<14} slot {entry.slot:<8} "
            f"{human_size(entry.size):>10}"
        )
    total = worldset.total_installed_size(entries)
    _note(f"{len(entries)} packages, {human_size(total)}")
    return 0


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m gentstore.core.cli",
        description="Inspect Gentstore's Portage layer without starting the interface.",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--debug", action="store_true", help="log what the core layer is doing")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("info", help="environment summary").set_defaults(func=cmd_info)

    repos_parser = sub.add_parser("repos", help="configured repositories")
    repos_parser.add_argument("--fast", action="store_true", help="skip counting packages")
    repos_parser.add_argument("-v", "--verbose", action="store_true", help="show sync settings")
    repos_parser.set_defaults(func=cmd_repos)

    index_parser = sub.add_parser("index", help="build the search index and time it")
    index_parser.add_argument("--progress", action="store_true")
    index_parser.set_defaults(func=cmd_index)

    search_parser = sub.add_parser("search", help="search the repositories")
    search_parser.add_argument("query")
    search_parser.add_argument("--repo", action="append", help="limit to a repository (repeatable)")
    search_parser.add_argument("--installed", action="store_true", help="installed packages only")
    search_parser.add_argument(
        "--names-only", action="store_true", help="do not match descriptions"
    )
    search_parser.add_argument("--limit", type=int, default=50)
    search_parser.add_argument("--progress", action="store_true")
    search_parser.set_defaults(func=cmd_search)

    show_parser = sub.add_parser("show", help="everything about one package")
    show_parser.add_argument("atom", help="cat/pkg, a full atom, or a unique package name")
    show_parser.add_argument(
        "--repo", default="", help="answer from this repository alone, ignoring the others"
    )
    show_parser.add_argument("--progress", action="store_true")
    show_parser.set_defaults(func=cmd_show)

    sub.add_parser("world", help="the @world set").set_defaults(func=cmd_world)

    installed_parser = sub.add_parser("installed", help="everything in /var/db/pkg")
    installed_parser.add_argument("--filter", help="substring of cat/pkg")
    installed_parser.set_defaults(func=cmd_installed)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(levelname)-7s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        return args.func(args)
    except PortageUnavailableError as exc:
        print(f"Portage is not usable here: {exc}", file=sys.stderr)
        return 3
    except BrokenPipeError:  # pragma: no cover - piping into head
        return 0
    except KeyboardInterrupt:  # pragma: no cover
        return 130


if __name__ == "__main__":
    sys.exit(main())
