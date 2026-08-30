"""A handful of facts about the local Portage installation.

Only what the window chrome needs: the strings shown in the menu bar corner, the
toolbar and the status bar. Everything is optional — a missing file or an older
Portage must never stop the application from starting, so each field falls back
to ``None`` and the interface simply omits it.

Importing and initialising ``portage`` takes a noticeable moment, so
:func:`collect` is meant to be called from a worker thread.

Since S2 the Portage handle itself comes from
:mod:`gentstore.core.portage_env`, so the window chrome and the package screens
always describe the same configuration.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

MAKE_PROFILE = Path("/etc/portage/make.profile")


@dataclass(frozen=True, slots=True)
class SystemInfo:
    """Facts about the local Portage setup, all individually optional."""

    portage_version: str | None = None
    arch: str | None = None
    profile: str | None = None
    last_sync: datetime | None = None
    makeopts: str | None = None
    features: str | None = None
    world_count: int | None = None

    def chrome_line(self) -> str:
        """The one-liner shown in the menu bar corner."""
        parts = [
            f"portage {self.portage_version}" if self.portage_version else None,
            self.arch,
            f"profile {self.profile}" if self.profile else None,
        ]
        return " · ".join(p for p in parts if p)


def _read_profile() -> str | None:
    """Return the active profile as e.g. ``default/linux/amd64/23.0/desktop``."""
    try:
        target = os.readlink(MAKE_PROFILE)
    except OSError:
        return None
    resolved = (MAKE_PROFILE.parent / target).resolve(strict=False)
    parts = resolved.parts
    if "profiles" in parts:
        return "/".join(parts[parts.index("profiles") + 1:]) or None
    return resolved.name or None


_cache: SystemInfo | None = None
#: Portage's configuration objects are not built for concurrent initialisation,
#: so the first caller does the work and any others wait for its result.
_lock = threading.Lock()


def collect(refresh: bool = False) -> SystemInfo:
    """Gather everything, cached. Never raises; missing pieces come back ``None``.

    Pass ``refresh=True`` after a sync or a ``make.conf`` edit.
    """
    global _cache
    with _lock:
        if _cache is not None and not refresh:
            return _cache
        _cache = _collect_uncached()
        return _cache


def _collect_uncached() -> SystemInfo:
    version = arch = makeopts = features = None
    last_sync = None
    world_count = None

    try:
        import portage  # noqa: PLC0415 — deliberately deferred, the import is slow

        from .core import repos as core_repos  # noqa: PLC0415 — pulls in portage
        from .core import worldset  # noqa: PLC0415
        from .core.portage_env import env  # noqa: PLC0415

        handle = env()
        version = getattr(portage, "VERSION", None)
        arch = handle.arch or None
        makeopts = handle.settings.get("MAKEOPTS") or None
        features = handle.settings.get("FEATURES") or None
        world_count = len(worldset.read_world_atoms(handle))

        main = handle.main_repo_name
        if main is not None:
            info = core_repos.repository(main, handle)
            last_sync = info.last_sync if info is not None else None
    except Exception:  # pragma: no cover - depends on the host system
        log.exception("Could not read Portage configuration")

    info = SystemInfo(
        portage_version=version,
        arch=arch,
        profile=_read_profile(),
        last_sync=last_sync,
        makeopts=makeopts,
        features=features,
        world_count=world_count,
    )
    log.info("System info: %s", info)
    return info
