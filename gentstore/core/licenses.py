"""Licences: which ones this system accepts, and what they actually say.

Gentoo's ``ACCEPT_LICENSE`` is usually a group — ``@FREE`` on a default install
— so "this package is blocked by its licence" nearly always means *one* licence
name inside a much longer list is not in that group. The point of this module is
to name that one, put its text in front of the user, and let them accept it for
the single package they are looking at rather than widening ``ACCEPT_LICENSE``
for everything they will ever install.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .portage_env import PortageEnv
from .portage_env import env as _default_env

log = logging.getLogger(__name__)

#: Licence texts are big; a handful is plenty to keep around.
_TEXT_CACHE: dict[tuple[str, str], str] = {}


@dataclass(frozen=True, slots=True)
class Licence:
    """One licence, and where it sits in Gentoo's grouping."""

    name: str
    #: Groups it belongs to, without the ``@``: ``FREE``, ``OSI-APPROVED`` …
    groups: tuple[str, ...]
    #: File holding the full text, when the repository ships one.
    path: Path | None

    @property
    def is_free(self) -> bool:
        """In ``@FREE`` — the group a default Gentoo accepts."""
        return "FREE" in self.groups

    @property
    def has_text(self) -> bool:
        return self.path is not None


def clear_caches() -> None:
    _TEXT_CACHE.clear()


def accept_license(env: PortageEnv | None = None) -> str:
    """The raw ``ACCEPT_LICENSE`` value, e.g. ``@FREE``."""
    env = env or _default_env()
    return env.settings.get("ACCEPT_LICENSE", "") or ""


def groups(env: PortageEnv | None = None) -> dict[str, tuple[str, ...]]:
    """Every licence group defined by the repositories, without the ``@``."""
    env = env or _default_env()
    try:
        raw = env.settings._license_manager._license_groups
    except AttributeError:  # pragma: no cover - a Portage that moved it
        log.warning("This Portage does not expose its licence groups")
        return {}
    return {name: tuple(sorted(members)) for name, members in raw.items()}


def groups_of(name: str, env: PortageEnv | None = None) -> tuple[str, ...]:
    """Which groups a licence belongs to.

    Groups nest — ``@FREE`` is built from ``@FSF-APPROVED`` and friends — so
    membership is resolved by expanding each group rather than reading the file
    literally.
    """
    env = env or _default_env()
    manager = getattr(env.settings, "_license_manager", None)
    if manager is None:  # pragma: no cover
        return ()
    found = []
    for group in groups(env):
        try:
            members = manager.expandLicenseTokens([f"@{group}"])
        except Exception:  # pragma: no cover - a group referring to itself
            continue
        if name in members:
            found.append(group)
    return tuple(sorted(found))


def missing_for(
    cpv: str, repo: str = "", env: PortageEnv | None = None
) -> tuple[str, ...]:
    """Licences of *cpv* that this system does not accept.

    Delegated to Portage: ``LICENSE`` is a dependency-style expression with
    ``||`` groups and USE conditionals, and re-implementing its evaluation would
    be a second opinion nobody asked for.

    Those USE conditionals are why the flags come from
    :meth:`PortageEnv.configured` and not from the shared configuration. The
    shared object describes the system, which has no ``PORTAGE_USE`` at all —
    that value only exists once ``setcpv()`` has resolved USE for one package.
    Passing the empty string instead drops every conditional branch, so a
    package like ``LICENSE="MIT cuda? ( NVIDIA-CUDA )"`` would report only
    ``MIT`` as missing, the user would accept it, and ``emerge`` would still
    refuse over a licence Gentstore never named.
    """
    env = env or _default_env()
    manager = getattr(env.settings, "_license_manager", None)
    if manager is None:  # pragma: no cover
        return ()
    try:
        licence, slot, repository = env.portdb.aux_get(
            cpv, ["LICENSE", "SLOT", "repository"], myrepo=repo or None
        )
        with env.configured(cpv) as settings:
            use = settings.get("PORTAGE_USE", "")
        missing = manager.getMissingLicenses(
            cpv, use, licence, slot.partition("/")[0], repo or repository
        )
    except Exception:  # pragma: no cover - unreadable ebuild
        log.warning("Could not check the licences of %s", cpv, exc_info=True)
        return ()
    return tuple(missing)


def declared_for(cpv: str, repo: str = "", env: PortageEnv | None = None) -> str:
    """The package's raw ``LICENSE`` string, as the ebuild wrote it."""
    env = env or _default_env()
    try:
        return env.portdb.aux_get(cpv, ["LICENSE"], myrepo=repo or None)[0]
    except Exception:  # pragma: no cover
        return ""


def _text_path(name: str, env: PortageEnv) -> Path | None:
    """Search every repository, main one last.

    An overlay may ship a licence the main tree has never heard of, and that is
    exactly the case where the user most wants to read the text before agreeing
    to it.
    """
    for repo in reversed(list(env.repos())):
        location = getattr(repo, "location", None)
        if not location:
            continue
        candidate = Path(location) / "licenses" / name
        if candidate.is_file():
            return candidate
    return None


def describe(name: str, env: PortageEnv | None = None) -> Licence:
    env = env or _default_env()
    return Licence(name=name, groups=groups_of(name, env), path=_text_path(name, env))


def text(name: str, env: PortageEnv | None = None) -> str | None:
    """The full licence text, or ``None`` when no repository ships one."""
    env = env or _default_env()
    key = (env.eroot, name)
    if key in _TEXT_CACHE:
        return _TEXT_CACHE[key]

    path = _text_path(name, env)
    if path is None:
        return None
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:  # pragma: no cover - a licence file we cannot read
        return None
    _TEXT_CACHE[key] = content
    return content
