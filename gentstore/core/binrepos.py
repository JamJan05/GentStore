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

"""Binary packages: where they come from and whether to use them.

Gentoo builds from source, and that is the point of it — but not every package
is worth eight minutes of a laptop's afternoon. Since 2023 Gentoo publishes
official binary packages, and ``--getbinpkg`` will fetch one instead of
compiling whenever the binary matches what the system asked for.

"Matches" is the part worth knowing: a binary is only used when its USE flags,
its dependencies and its ABI all line up with this machine's configuration.
Turning the option on therefore changes *nothing* about what gets installed —
only how it arrives. The update preview marks each row accordingly, which is
where the difference actually shows up.

``binrepos.conf`` is the same shape as ``repos.conf``: one INI section per
source, either as one file or as a directory of them.
"""

from __future__ import annotations

import configparser
import logging
from dataclasses import dataclass
from pathlib import Path

from .confedit import WritePlan
from .portage_env import PortageEnv
from .portage_env import env as _default_env

log = logging.getLogger(__name__)

CONFIG_NAME = "binrepos.conf"

#: Gentoo's own binary host, the one worth offering by name.
OFFICIAL_NAME = "gentoo-binhost"
OFFICIAL_URI = "https://distfiles.gentoo.org/releases/amd64/binpackages/23.0/x86-64"


@dataclass(frozen=True, slots=True)
class BinaryRepo:
    """One binary package source."""

    name: str
    sync_uri: str
    priority: int | None = None
    #: The file the section lives in.
    path: Path | None = None

    @property
    def is_local(self) -> bool:
        return self.sync_uri.startswith("/") or self.sync_uri.startswith("file://")


def _config_dir(env: PortageEnv | None, override: Path | None) -> Path:
    if override is not None:
        return override
    root = Path(env.settings.get("PORTAGE_CONFIGROOT", "/")) if env else Path("/")
    return root / "etc" / "portage"


def config_files(
    env: PortageEnv | None = None, config_dir: Path | None = None
) -> tuple[Path, ...]:
    base = _config_dir(env, config_dir) / CONFIG_NAME
    if base.is_dir():
        return tuple(sorted(item for item in base.iterdir() if item.is_file()))
    if base.is_file():
        return (base,)
    return ()


def read(
    env: PortageEnv | None = None, config_dir: Path | None = None
) -> tuple[BinaryRepo, ...]:
    """Every configured binary host. An empty answer is the common one."""
    found: list[BinaryRepo] = []
    for path in config_files(env, config_dir):
        parser = configparser.ConfigParser()
        try:
            parser.read_string(path.read_text(encoding="utf-8"), source=str(path))
        except (OSError, configparser.Error) as exc:
            log.warning("Could not read %s: %s", path, exc)
            continue
        for name in parser.sections():
            section = parser[name]
            priority = section.get("priority")
            found.append(
                BinaryRepo(
                    name=name,
                    sync_uri=section.get("sync-uri", ""),
                    priority=int(priority) if priority and priority.isdigit() else None,
                    path=path,
                )
            )
    return tuple(found)


def package_dir(env: PortageEnv | None = None) -> Path:
    """``PKGDIR`` — where binary packages this machine built itself are kept."""
    env = env or _default_env()
    return Path(env.settings.get("PKGDIR", "/var/cache/binpkgs"))


def local_count(env: PortageEnv | None = None) -> int:
    """How many binary packages are already on disk.

    Counted rather than parsed: the point is "is there anything here", and
    reading the whole index to answer that would be work for its own sake.
    """
    directory = package_dir(env)
    if not directory.is_dir():
        return 0
    return sum(1 for item in directory.rglob("*") if item.suffix in (".gpkg", ".tbz2", ".xpak"))


def builds_binaries(env: PortageEnv | None = None) -> bool:
    """Whether ``FEATURES`` tells Portage to keep a binary of everything it builds."""
    env = env or _default_env()
    return "buildpkg" in (env.settings.get("FEATURES") or "").split()


def section_text(name: str, uri: str, priority: int | None = None) -> str:
    lines = [f"[{name}]", f"sync-uri = {uri}"]
    if priority is not None:
        lines.append(f"priority = {priority}")
    return "\n".join(lines) + "\n"


def plan_add(
    name: str,
    uri: str,
    priority: int | None = None,
    env: PortageEnv | None = None,
    config_dir: Path | None = None,
) -> WritePlan:
    """Add a binary host as a file of its own inside ``binrepos.conf``.

    A whole file rather than a line, because that is the shape of the format —
    and the helper only writes whole files where Gentstore made them, which is
    exactly here and in ``repos.conf``.
    """
    base = _config_dir(env, config_dir) / CONFIG_NAME
    target = base / f"{name}.conf"
    return WritePlan(
        op="write_file",
        path=target,
        line=section_text(name, uri, priority),
        kind=_kind(base),
    )


def plan_remove(
    name: str, env: PortageEnv | None = None, config_dir: Path | None = None
) -> WritePlan:
    base = _config_dir(env, config_dir) / CONFIG_NAME
    target = base / f"{name}.conf"
    return WritePlan(op="delete_file", path=target, line="", kind=_kind(base))


def _kind(base: Path):  # noqa: ANN202 - TargetKind, imported lazily
    from .confedit import TargetKind  # noqa: PLC0415 — avoids a cycle

    return TargetKind.DIRECTORY if base.is_dir() else TargetKind.NEW_DIRECTORY
