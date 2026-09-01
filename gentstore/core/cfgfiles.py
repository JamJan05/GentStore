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

"""The files an update left behind for somebody to decide about.

When a package would overwrite a configuration file that has been edited,
Portage does not overwrite it. It writes the new version alongside, named
``._cfg0000_<name>``, and leaves the two of them there. That is the right
behaviour and it is also why every long-lived Gentoo system accumulates a
handful of these that nobody has looked at.

This module finds them, works out which package put each one there, and produces
the difference between the two versions. Deciding is the interface's job and
carrying the decision out is the helper's; nothing here writes anything.

Where to look comes from Portage's own ``CONFIG_PROTECT``, minus
``CONFIG_PROTECT_MASK`` — the list of places inside a protected directory that
are *not* protected after all, and where Portage therefore overwrites silently.
"""

from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from .portage_env import PortageEnv
from .portage_env import env as _default_env

log = logging.getLogger(__name__)

#: ``._cfg0000_make.conf`` — Portage numbers them when several pile up.
CFG_PREFIX = re.compile(r"^\._cfg(?P<number>\d{4})_(?P<name>.+)$")

#: Directories never worth walking into looking for configuration files.
_SKIP = frozenset({".git", ".svn", "__pycache__"})


class DiffKind(StrEnum):
    CONTEXT = "context"
    ADDED = "added"
    REMOVED = "removed"
    HEADER = "header"


@dataclass(frozen=True, slots=True)
class DiffLine:
    kind: DiffKind
    text: str


@dataclass(frozen=True, slots=True)
class ConfigFile:
    """One pending configuration file, and what it would replace."""

    candidate: Path
    target: Path
    #: Sequence number Portage gave it; several may be waiting for one target.
    number: int
    owner: str = ""
    added: int = 0
    removed: int = 0
    modified: datetime | None = None

    @property
    def name(self) -> str:
        return self.target.name

    @property
    def directory(self) -> Path:
        return self.target.parent

    @property
    def is_new_file(self) -> bool:
        """Nothing to compare against — the package is installing this outright."""
        return not self.target.exists()

    @property
    def changed_lines(self) -> int:
        return self.added + self.removed


# ---------------------------------------------------------------------------
# where to look
# ---------------------------------------------------------------------------


def _paths_from(env: PortageEnv, name: str) -> tuple[Path, ...]:
    value = env.settings.get(name, "") or ""
    return tuple(Path(item) for item in value.split() if item.startswith("/"))


def protected_directories(env: PortageEnv | None = None) -> tuple[Path, ...]:
    """``CONFIG_PROTECT`` — where Portage refuses to overwrite."""
    env = env or _default_env()
    return _paths_from(env, "CONFIG_PROTECT")


def masked_directories(env: PortageEnv | None = None) -> tuple[Path, ...]:
    """``CONFIG_PROTECT_MASK`` — the exceptions inside those.

    Portage overwrites these without asking, so a ``._cfg`` file has no business
    being there; skipping them keeps a stray one from being offered as a
    decision the user never had.
    """
    env = env or _default_env()
    return _paths_from(env, "CONFIG_PROTECT_MASK")


def _is_masked(path: Path, masks: tuple[Path, ...]) -> bool:
    return any(path == mask or mask in path.parents for mask in masks)


def _outermost(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    """*roots*, with the ones that are not directories, duplicates and anything
    nested inside another taken out.

    ``CONFIG_PROTECT`` is assembled from several files — ``make.globals``, then
    ``make.conf``, then every file in ``/etc/env.d`` — and any of them may name
    a directory that is already inside one of the others. Walking both scans the
    inner one twice, and the same ``._cfg`` file then arrives on the screen as
    two identical decisions to make.

    The originals are returned rather than their resolved forms: resolving is
    how the nesting question gets a correct answer, but the paths handed on from
    here end up in front of the user, and those should read the way the
    configuration wrote them.
    """
    seen: dict[Path, Path] = {}
    for root in roots:
        try:
            resolved = root.resolve(strict=True)
        except OSError:
            continue
        if resolved.is_dir() and resolved not in seen:
            seen[resolved] = root
    return tuple(
        original
        for resolved, original in seen.items()
        if not any(other != resolved and other in resolved.parents for other in seen)
    )


# ---------------------------------------------------------------------------
# finding them
# ---------------------------------------------------------------------------


def find(
    env: PortageEnv | None = None,
    roots: tuple[Path, ...] | None = None,
    masks: tuple[Path, ...] | None = None,
) -> tuple[ConfigFile, ...]:
    """Every pending configuration file, oldest number first per target."""
    env = env or _default_env()
    directories = roots if roots is not None else protected_directories(env)
    masked = masks if masks is not None else masked_directories(env)

    found: list[ConfigFile] = []
    for root in _outermost(tuple(directories)):
        found.extend(_scan(root, masked))

    owners = owner_of(tuple(item.target for item in found), env)
    resolved = tuple(
        _with_diffstat(item, owners.get(str(item.target), "")) for item in found
    )
    return tuple(sorted(resolved, key=lambda item: (str(item.target), item.number)))


def _scan(root: Path, masked: tuple[Path, ...]) -> list[ConfigFile]:
    found: list[ConfigFile] = []
    for directory, subdirectories, names in _walk(root):
        if _is_masked(directory, masked):
            subdirectories.clear()
            continue
        subdirectories[:] = [name for name in subdirectories if name not in _SKIP]
        for name in names:
            match = CFG_PREFIX.match(name)
            if match is None:
                continue
            candidate = directory / name
            target = directory / match.group("name")
            if _is_masked(target, masked):
                continue
            try:
                modified = datetime.fromtimestamp(candidate.stat().st_mtime)
            except OSError:  # pragma: no cover - it vanished mid-scan
                continue
            found.append(
                ConfigFile(
                    candidate=candidate,
                    target=target,
                    number=int(match.group("number")),
                    modified=modified,
                )
            )
    return found


def _walk(root: Path):  # noqa: ANN202 - os.walk's tuples
    import os  # noqa: PLC0415 — only needed here

    for directory, subdirectories, names in os.walk(root, followlinks=False):
        yield Path(directory), subdirectories, names


def owner_of(paths: tuple[Path, ...], env: PortageEnv | None = None) -> dict[str, str]:
    """Which installed package owns each path.

    Portage keeps a file-to-package map, so this is a lookup rather than a
    search — and it is worth showing: "dispatch-conf has something for you" is
    much less useful than "the package you just updated changed this file".
    """
    if not paths:
        return {}
    env = env or _default_env()
    try:
        owners = env.vardb._owners.get_owners([str(path) for path in paths])
    except Exception:  # pragma: no cover - a Portage that moved it
        log.warning("Could not work out which packages own these files", exc_info=True)
        return {}

    result: dict[str, str] = {}
    for link, files in owners.items():
        name = str(getattr(link, "mycpv", ""))
        for relative in files:
            result[f"/{str(relative).lstrip('/')}"] = name
    return result


def _read(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    except OSError:
        return []


def _with_diffstat(item: ConfigFile, owner: str) -> ConfigFile:
    added = removed = 0
    for line in difflib.unified_diff(
        _read(item.target), _read(item.candidate), n=0, lineterm=""
    ):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return ConfigFile(
        candidate=item.candidate,
        target=item.target,
        number=item.number,
        owner=owner,
        added=added,
        removed=removed,
        modified=item.modified,
    )


# ---------------------------------------------------------------------------
# the difference
# ---------------------------------------------------------------------------


def unified(
    before: list[str],
    after: list[str],
    from_label: str = "",
    to_label: str = "",
    context: int = 3,
) -> tuple[DiffLine, ...]:
    """Two versions of a file as classified lines, ready to colour.

    Unified rather than side-by-side: configuration files are mostly comments
    and long lines, and two narrow columns of them are harder to read than one
    wide one with the changes marked. Shared with the ``make.conf`` screen,
    which shows the same kind of before-and-after for a single line.
    """
    result = []
    for raw in difflib.unified_diff(
        before, after, fromfile=from_label, tofile=to_label, n=context, lineterm=""
    ):
        text = raw.rstrip("\n")
        if text.startswith(("+++", "---", "@@")):
            kind = DiffKind.HEADER
        elif text.startswith("+"):
            kind = DiffKind.ADDED
        elif text.startswith("-"):
            kind = DiffKind.REMOVED
        else:
            kind = DiffKind.CONTEXT
        result.append(DiffLine(kind=kind, text=text))
    return tuple(result)


def diff(item: ConfigFile, context: int = 3) -> tuple[DiffLine, ...]:
    """The file you have against the version the package brought."""
    return unified(
        _read(item.target),
        _read(item.candidate),
        str(item.target),
        str(item.candidate),
        context,
    )
