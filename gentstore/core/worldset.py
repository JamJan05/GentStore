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

"""What is installed, and what the user asked for.

Two different questions that are easy to confuse, so they live side by side:

* **installed** — everything in ``/var/db/pkg``, dependencies included;
* **@world** — the short list in ``/var/lib/portage/world`` of packages the user
  installed *on purpose*. Removing an entry from it does not uninstall anything;
  it only stops Portage from protecting the package from ``--depclean``.

The distinction is the whole point of the "@world set" screen, so the data model
keeps it explicit rather than merging both into one list.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .portage_env import PortageEnv
from .portage_env import env as _default_env

log = logging.getLogger(__name__)

_WORLD_KEYS = ("SLOT", "repository", "BUILD_TIME", "SIZE", "DESCRIPTION", "USE", "LICENSE")


@dataclass(frozen=True, slots=True)
class InstalledPackage:
    """One entry of ``/var/db/pkg``."""

    cpv: str
    cp: str
    version: str
    slot: str
    repo: str
    size: int | None
    build_time: datetime | None
    description: str
    use_flags: tuple[str, ...]
    license: str

    @property
    def category(self) -> str:
        return self.cp.partition("/")[0]

    @property
    def name(self) -> str:
        return self.cp.partition("/")[2]


@dataclass(frozen=True, slots=True)
class WorldEntry:
    """One line of ``/var/lib/portage/world``, paired with what it resolves to."""

    atom: str
    cp: str
    installed: tuple[InstalledPackage, ...]

    @property
    def is_satisfied(self) -> bool:
        """Whether anything is actually installed for this entry.

        An unsatisfied entry is not an error — it happens when a package was
        removed with ``emerge --unmerge`` instead of ``--deselect`` — but it is
        worth showing, because it makes ``@world`` updates noisy.
        """
        return bool(self.installed)


def world_file(env: PortageEnv | None = None) -> Path:
    env = env or _default_env()
    return Path(env.eroot) / "var/lib/portage/world"


def world_sets_file(env: PortageEnv | None = None) -> Path:
    env = env or _default_env()
    return Path(env.eroot) / "var/lib/portage/world_sets"


def _read_lines(path: Path) -> tuple[str, ...]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        log.warning("Could not read %s: %s", path, exc)
        return ()
    return tuple(
        stripped
        for line in text.splitlines()
        if (stripped := line.strip()) and not stripped.startswith("#")
    )


def read_world_atoms(env: PortageEnv | None = None) -> tuple[str, ...]:
    """The raw atoms of ``@world``, in file order."""
    return _read_lines(world_file(env))


def read_world_sets(env: PortageEnv | None = None) -> tuple[str, ...]:
    """Set names (``@gnome``, ``@kde``…) selected into ``@world``."""
    return _read_lines(world_sets_file(env))


def _split_atom(atom: str) -> str:
    """Reduce an atom to its ``cat/pkg``. Falls back to the atom itself."""
    from portage.dep import dep_getkey  # noqa: PLC0415 — slow import, deferred

    try:
        return dep_getkey(atom) or atom
    except Exception:
        return atom


def _as_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_time(value: str) -> datetime | None:
    stamp = _as_int(value)
    if stamp is None:
        return None
    try:
        return datetime.fromtimestamp(stamp)
    except (OSError, OverflowError, ValueError):  # pragma: no cover - absurd timestamps
        return None


def _make(vardb, cpv) -> InstalledPackage:  # noqa: ANN001 - Portage has no type stubs
    slot, repo, build_time, size, description, use, license_ = vardb.aux_get(cpv, _WORLD_KEYS)
    return InstalledPackage(
        cpv=str(cpv),
        cp=getattr(cpv, "cp", None) or str(cpv).rpartition("-")[0],
        version=getattr(cpv, "version", "") or "",
        slot=slot,
        repo=repo,
        size=_as_int(size),
        build_time=_as_time(build_time),
        description=description,
        use_flags=tuple(use.split()),
        license=license_,
    )


def installed_packages(env: PortageEnv | None = None) -> tuple[InstalledPackage, ...]:
    """Everything in ``/var/db/pkg``, sorted by ``cat/pkg`` then version."""
    env = env or _default_env()
    vardb = env.vardb
    packages = []
    for cpv in vardb.cpv_all():
        try:
            packages.append(_make(vardb, cpv))
        except Exception:  # pragma: no cover - a half-written /var/db/pkg entry
            log.warning("Skipping unreadable installed package %s", cpv, exc_info=True)
    packages.sort(key=lambda p: (p.cp, p.version))
    return tuple(packages)


def installed_for_cp(cp: str, env: PortageEnv | None = None) -> tuple[InstalledPackage, ...]:
    """Installed versions of one ``cat/pkg`` — usually one, more when slotted."""
    env = env or _default_env()
    vardb = env.vardb
    result = []
    for cpv in vardb.cp_list(cp):
        try:
            result.append(_make(vardb, cpv))
        except Exception:  # pragma: no cover
            log.warning("Skipping unreadable installed package %s", cpv, exc_info=True)
    result.sort(key=lambda p: p.version)
    return tuple(result)


def installed_cps(env: PortageEnv | None = None) -> frozenset[str]:
    """Just the ``cat/pkg`` keys — the cheap query the search index needs."""
    env = env or _default_env()
    return frozenset(getattr(cpv, "cp", None) or str(cpv) for cpv in env.vardb.cpv_all())


def world_entries(env: PortageEnv | None = None) -> tuple[WorldEntry, ...]:
    """``@world`` in file order, each entry resolved against what is installed."""
    env = env or _default_env()
    entries = []
    for atom in read_world_atoms(env):
        cp = _split_atom(atom)
        entries.append(WorldEntry(atom=atom, cp=cp, installed=installed_for_cp(cp, env)))
    return tuple(entries)


def total_installed_size(packages: tuple[InstalledPackage, ...]) -> int:
    """Sum of the sizes that are known; unknown ones count as zero."""
    return sum(p.size or 0 for p in packages)
