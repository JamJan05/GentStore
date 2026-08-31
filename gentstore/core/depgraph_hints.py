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

"""What a USE flag actually pulls in.

The point of the "Search & install" screen's flag panel is to answer a question
the handbook cannot: *if I tick this box, what changes?* Two things do.

**Extra packages.** ``vulkan? ( media-libs/vulkan-loader )`` in ``DEPEND`` means
turning ``vulkan`` on adds that package to the merge. Turning it off removes it
— and a ``!flag? ( … )`` group works the other way round.

**Flags forced on other packages.** ``>=media-libs/libplacebo-7.349.0[vulkan?]``
means "if I have ``vulkan``, libplacebo must have it too". Nothing is added to
the list, but something already installed may have to be rebuilt, which is the
usual explanation for an update that suddenly wants to recompile half a desktop.

The dependency strings are read with Portage's own ``paren_reduce``, which keeps
the ``flag?`` markers instead of resolving them the way ``use_reduce`` would.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .portage_env import PortageEnv
from .portage_env import env as _default_env

log = logging.getLogger(__name__)

#: In the order they matter to somebody reading the list.
DEPEND_KEYS = ("RDEPEND", "DEPEND", "BDEPEND", "PDEPEND", "IDEPEND")

#: ``[vulkan?]``, ``[vulkan=]``, ``[!vulkan?]`` inside an atom's bracket group.
_USE_DEP = re.compile(r"\[([^\]]*)\]")


@dataclass(frozen=True, slots=True)
class PulledAtom:
    """One dependency brought in by a flag."""

    atom: str
    #: Which dependency variable it came from — ``RDEPEND`` and friends.
    kind: str
    #: Other conditions that also have to hold. ``drm? ( egl? ( mesa ) )``
    #: gives ``mesa`` under ``egl`` with ``("drm",)`` still outstanding.
    also_needs: tuple[str, ...] = ()

    @property
    def is_unconditional(self) -> bool:
        return not self.also_needs


@dataclass(frozen=True, slots=True)
class FlagEffect:
    """Everything one flag changes about the dependency list."""

    flag: str
    #: Pulled in when the flag is on.
    pulls_in: tuple[PulledAtom, ...] = ()
    #: Pulled in when the flag is *off* — from ``!flag? ( … )``.
    pulls_in_when_off: tuple[PulledAtom, ...] = ()
    #: Atoms that must carry the same flag, from ``[flag?]`` / ``[flag=]``.
    propagates_to: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.pulls_in or self.pulls_in_when_off or self.propagates_to)


@dataclass
class _Collector:
    pulls: dict[str, list[PulledAtom]] = field(default_factory=dict)
    pulls_off: dict[str, list[PulledAtom]] = field(default_factory=dict)
    propagates: dict[str, list[str]] = field(default_factory=dict)

    def add_atom(self, atom: str, kind: str, conditions: tuple[str, ...]) -> None:
        for index, condition in enumerate(conditions):
            others = tuple(c for position, c in enumerate(conditions) if position != index)
            entry = PulledAtom(atom=atom, kind=kind, also_needs=others)
            target = self.pulls_off if condition.startswith("!") else self.pulls
            target.setdefault(condition.lstrip("!"), []).append(entry)

        for flag in _use_dependency_flags(atom):
            entries = self.propagates.setdefault(flag, [])
            if atom not in entries:
                entries.append(atom)


def _use_dependency_flags(atom: str) -> tuple[str, ...]:
    """Flags of *this* package that an atom's ``[…]`` group refers back to."""
    match = _USE_DEP.search(atom)
    if match is None:
        return ()
    flags = []
    for token in match.group(1).split(","):
        token = token.strip()
        # `vulkan?` and `vulkan=` mirror our flag; `vulkan` and `-vulkan` are
        # fixed demands that have nothing to do with how ours is set.
        if token.endswith(("?", "=")):
            flags.append(token[:-1].lstrip("!-"))
    return tuple(flags)


def _walk(tree: list, kind: str, conditions: tuple[str, ...], out: _Collector) -> None:
    position = 0
    while position < len(tree):
        token = tree[position]

        if isinstance(token, list):
            _walk(token, kind, conditions, out)
            position += 1
            continue

        if isinstance(token, str) and token.endswith("?"):
            body = tree[position + 1] if position + 1 < len(tree) else []
            if isinstance(body, list):
                _walk(body, kind, (*conditions, token[:-1]), out)
            position += 2
            continue

        if token in ("||", "^^", "??"):
            body = tree[position + 1] if position + 1 < len(tree) else []
            if isinstance(body, list):
                # An any-of group adds no condition of its own: every atom in it
                # is still reachable under the conditions already in force.
                _walk(body, kind, conditions, out)
            position += 2
            continue

        out.add_atom(str(token), kind, conditions)
        position += 1


def effects(cpv: str, repo: str = "", env: PortageEnv | None = None) -> dict[str, FlagEffect]:
    """Map every flag that changes something to what it changes."""
    from portage.dep import paren_reduce  # noqa: PLC0415 — slow import, deferred

    env = env or _default_env()
    collector = _Collector()

    try:
        values = env.portdb.aux_get(cpv, list(DEPEND_KEYS), myrepo=repo or None)
    except Exception:  # pragma: no cover - unreadable ebuild
        log.warning("Could not read the dependencies of %s", cpv, exc_info=True)
        return {}

    for kind, raw in zip(DEPEND_KEYS, values, strict=True):
        if not raw.strip():
            continue
        try:
            _walk(paren_reduce(raw), kind, (), collector)
        except Exception:  # pragma: no cover - a malformed dependency string
            log.warning("Could not parse %s of %s", kind, cpv, exc_info=True)

    names = set(collector.pulls) | set(collector.pulls_off) | set(collector.propagates)
    return {
        name: FlagEffect(
            flag=name,
            pulls_in=tuple(_unique(collector.pulls.get(name, ()))),
            pulls_in_when_off=tuple(_unique(collector.pulls_off.get(name, ()))),
            propagates_to=tuple(collector.propagates.get(name, ())),
        )
        for name in sorted(names)
    }


def _unique(entries) -> list[PulledAtom]:  # noqa: ANN001 - iterable of PulledAtom
    """Drop repeats: the same atom usually appears in DEPEND and RDEPEND both."""
    seen: dict[str, PulledAtom] = {}
    for entry in entries:
        if entry.atom not in seen:
            seen[entry.atom] = entry
    return list(seen.values())
