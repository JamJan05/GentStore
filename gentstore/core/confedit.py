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

"""Working out what to write to ``/etc/portage``, before anything is written.

Nothing here touches the filesystem beyond reading it. The output is a
:class:`WritePlan`: the operation, the exact file, the exact line. The interface
shows that plan to the user, and only if they agree does it go to the privileged
helper, which does its own checking again.

Two decisions live here.

**Which file.** ``/etc/portage/package.use`` may be a single file or a directory
of them, and both are normal (Docs/01-architecture.md §7). If it is a directory,
an entry for the package may already be sitting in any file in it — so the whole
directory is searched, and an existing entry is amended where it is rather than
duplicated somewhere else.

**Which flags.** Only the ones that differ from what the profile, ``make.conf``
and the ebuild would give on their own. Writing out a flag the profile already
sets looks harmless and is not: profiles change, and a year later that line is
silently pinning a value nobody chose.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .portage_env import PortageEnv
from .useflags import UseState

log = logging.getLogger(__name__)

CONFIG_ROOT = Path("/etc/portage")


class TargetKind(StrEnum):
    """How the target file was arrived at — the interface explains which."""

    #: ``package.use`` is a directory; the entry goes in a file named after the
    #: package.
    DIRECTORY = "directory"
    #: An entry for this package already exists in this file.
    EXISTING = "existing"
    #: ``package.use`` is a single file and the line is appended to it.
    SINGLE_FILE = "single-file"
    #: Neither exists yet. Gentoo recommends the directory form, so that is what
    #: gets created.
    NEW_DIRECTORY = "new-directory"


@dataclass(frozen=True, slots=True)
class WritePlan:
    """Exactly what is about to happen to one file."""

    #: The helper operation: ``append_line``, ``replace_line`` or ``remove_line``.
    op: str
    path: Path
    line: str
    kind: TargetKind
    #: The line being replaced or removed, when there is one.
    previous: str | None = None
    #: Pattern the helper uses to find that line. Only for ``replace_line``.
    match: str | None = None

    @property
    def is_noop(self) -> bool:
        return self.op == "none"

    @property
    def creates_file(self) -> bool:
        return self.kind in (TargetKind.DIRECTORY, TargetKind.NEW_DIRECTORY)

    def as_request(self) -> dict[str, object]:
        """The helper request this plan corresponds to."""
        request: dict[str, object] = {"path": str(self.path), "line": self.line}
        if self.match is not None:
            request["match"] = self.match
        return request


# ---------------------------------------------------------------------------
# finding the file
# ---------------------------------------------------------------------------


def _config_dir(env: PortageEnv | None, override: Path | None = None) -> Path:
    """``/etc/portage``, or wherever this Portage keeps it.

    *override* exists for the tests and for a future "show me what this would
    do against that other root" mode. Unlike the helper's own constant it is no
    kind of security boundary — nothing here writes, and the helper re-checks
    every path it is handed regardless of where the plan came from.
    """
    if override is not None:
        return override
    if env is None:
        return CONFIG_ROOT
    return Path(env.settings.get("PORTAGE_CONFIGROOT", "/")) / "etc" / "portage"


def _entry_pattern(cp: str) -> re.Pattern[str]:
    """Matches a line whose first token is exactly *cp*.

    Exactly: ``>=media-video/mpv-0.40`` is a different, version-restricted entry
    that somebody wrote on purpose, and quietly rewriting it would be the sort
    of surprise this project exists to avoid.
    """
    return re.compile(rf"^\s*{re.escape(cp)}(\s|$)")


def find_entry(path: Path, cp: str) -> str | None:
    """The existing line for *cp* in *path*, if there is one."""
    pattern = _entry_pattern(cp)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        if pattern.match(line):
            return line
    return None


def locate(
    name: str,
    cp: str,
    env: PortageEnv | None = None,
    config_dir: Path | None = None,
    entry: str | None = None,
    file_name: str | None = None,
) -> tuple[Path, TargetKind, str | None]:
    """Where an entry for *cp* belongs in ``/etc/portage/<name>``.

    Returns the file, why it was chosen, and the line already there if any.
    *name* is ``package.use``, ``package.accept_keywords`` and so on, so every
    file Gentstore writes gets the same behaviour.

    *cp* names the file inside a directory — that is the Gentoo convention, one
    file per package. *entry* is the first token to look for, which is not the
    same thing: ``package.accept_keywords`` entries are version-specific atoms
    like ``=media-video/mpv-0.41.0-r2``. It defaults to *cp*. *file_name*
    overrides the file name for entries that are not about one package at all —
    ``*/*::guru`` belongs in a file called ``guru``.
    """
    base = _config_dir(env, config_dir) / name
    key = entry if entry is not None else cp
    # ``cp.partition("/")[2]`` is empty for anything that is not a ``cat/pkg``,
    # and an empty name makes ``base / file_name`` the directory itself — a path
    # the helper can only refuse, with a message about the wrong thing. Falling
    # back to the whole string keeps it a file.
    file_name = file_name or cp.partition("/")[2] or cp

    if base.is_dir():
        for candidate in sorted(base.iterdir()):
            if not candidate.is_file():
                continue
            existing = find_entry(candidate, key)
            if existing is not None:
                return candidate, TargetKind.EXISTING, existing
        return base / file_name, TargetKind.DIRECTORY, None

    if base.is_file():
        return base, TargetKind.SINGLE_FILE, find_entry(base, key)

    return base / file_name, TargetKind.NEW_DIRECTORY, None


# ---------------------------------------------------------------------------
# package.use
# ---------------------------------------------------------------------------


def use_line(cp: str, changes: dict[str, bool]) -> str:
    """``media-video/mpv vulkan -jack`` — or just the atom when nothing changed.

    Sorted by flag name so that the same choice always produces the same line,
    whatever order the boxes were clicked in.
    """
    tokens = [name if enabled else f"-{name}" for name, enabled in sorted(changes.items())]
    return " ".join([cp, *tokens])


def changed_flags(state: UseState, desired: dict[str, bool]) -> dict[str, bool]:
    """The subset of *desired* that differs from the un-overridden default.

    Locked flags are dropped: ``use.force`` and ``use.mask`` win over
    ``package.use``, so writing them out would produce a line that does nothing
    and looks like it does something.
    """
    result: dict[str, bool] = {}
    for name, enabled in desired.items():
        flag = state.flag(name)
        if flag is None or flag.is_locked:
            continue
        if flag.baseline != enabled:
            result[name] = enabled
    return result


def plan_package_use(
    state: UseState,
    desired: dict[str, bool],
    env: PortageEnv | None = None,
    config_dir: Path | None = None,
) -> WritePlan:
    """Work out the single line that expresses *desired*, and where it goes."""
    changes = changed_flags(state, desired)
    path, kind, existing = locate("package.use", state.cp, env, config_dir)
    line = use_line(state.cp, changes)

    if not changes:
        # Everything is back to the default. The right change is then to take
        # the old line out, not to leave a bare atom behind.
        if existing is None:
            return WritePlan("none", path, "", kind)
        return WritePlan(
            "remove_line", path, existing, TargetKind.EXISTING, previous=existing
        )

    if existing is None:
        return WritePlan("append_line", path, line, kind)
    if existing.strip() == line:
        return WritePlan("none", path, line, TargetKind.EXISTING, previous=existing)
    return WritePlan(
        "replace_line",
        path,
        line,
        TargetKind.EXISTING,
        previous=existing,
        match=_entry_pattern(state.cp).pattern,
    )


# ---------------------------------------------------------------------------
# the other /etc/portage files
# ---------------------------------------------------------------------------


def plan_entry(
    file_name: str,
    cp: str,
    atom: str,
    tokens: tuple[str, ...] = (),
    env: PortageEnv | None = None,
    config_dir: Path | None = None,
    target_name: str | None = None,
) -> WritePlan:
    """Plan one line in ``package.accept_keywords``, ``package.unmask`` or
    ``package.license``.

    The same three outcomes as :func:`plan_package_use` — add, replace, or
    nothing to do — because from the user's side these files behave identically:
    one line per atom, everything else in the file left alone.
    """
    path, kind, existing = locate(
        file_name, cp, env, config_dir, entry=atom, file_name=target_name
    )
    line = " ".join([atom, *tokens])

    if existing is None:
        return WritePlan("append_line", path, line, kind)
    if existing.strip() == line:
        return WritePlan("none", path, line, TargetKind.EXISTING, previous=existing)
    return WritePlan(
        "replace_line",
        path,
        line,
        TargetKind.EXISTING,
        previous=existing,
        match=_entry_pattern(atom).pattern,
    )


def plan_removal(
    file_name: str,
    cp: str,
    atom: str,
    env: PortageEnv | None = None,
    config_dir: Path | None = None,
    target_name: str | None = None,
) -> WritePlan:
    """Plan taking an entry back out — the "I changed my mind" direction."""
    path, kind, existing = locate(
        file_name, cp, env, config_dir, entry=atom, file_name=target_name
    )
    if existing is None:
        return WritePlan("none", path, "", kind)
    return WritePlan("remove_line", path, existing, TargetKind.EXISTING, previous=existing)


def cp_from_atom(atom: str) -> str:
    """``>=media-video/mpv-0.40`` → ``media-video/mpv``.

    Falls back to the atom itself, which is fine for the one thing the result is
    used for: naming a file inside a ``package.*`` directory.
    """
    from portage.dep import dep_getkey  # noqa: PLC0415 — slow import, deferred

    try:
        return dep_getkey(atom) or atom
    except Exception:
        return atom.lstrip("=<>!~").rpartition("-")[0] or atom


def read_entries(
    file_name: str, env: PortageEnv | None = None, config_dir: Path | None = None
) -> tuple[tuple[Path, str], ...]:
    """Every non-comment line in ``/etc/portage/<file_name>``, with its file.

    Used by the masks screen to show what the user has already accepted —
    the list that ``/etc/portage`` accumulates and nobody ever reads back.
    """
    base = _config_dir(env, config_dir) / file_name
    files = []
    if base.is_dir():
        files = [item for item in sorted(base.iterdir()) if item.is_file()]
    elif base.is_file():
        files = [base]

    entries = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                entries.append((path, stripped))
    return tuple(entries)
