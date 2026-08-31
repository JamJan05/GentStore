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
import re
from dataclasses import dataclass
from pathlib import Path

from .portage_env import PortageEnv
from .portage_env import env as _default_env

log = logging.getLogger(__name__)

#: Licence texts are big; a handful is plenty to keep around.
_TEXT_CACHE: dict[tuple[str, str], str] = {}

#: The conditional-licence scan reads every package in the tree, so its result
#: is kept until something says the configuration changed.
_CONDITIONAL: tuple[ConditionalLicence, ...] | None = None
_CONDITIONAL_FOR: PortageEnv | None = None


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
    global _CONDITIONAL, _CONDITIONAL_FOR
    _TEXT_CACHE.clear()
    _CONDITIONAL = None
    _CONDITIONAL_FOR = None


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


def _cp_of(cpv: str) -> str:
    from portage.versions import cpv_getkey  # noqa: PLC0415 — slow import, deferred

    try:
        return cpv_getkey(cpv) or cpv
    except Exception:  # pragma: no cover - a cpv Portage cannot split
        return cpv


# ---------------------------------------------------------------------------
# licences that depend on how the package is built
# ---------------------------------------------------------------------------

#: ``cuda?``, ``!bindist?``, ``l10n_de?`` — a USE condition in a ``LICENSE``.
_CONDITION = re.compile(r"(!?[A-Za-z0-9][\w+@-]*)\?")


@dataclass(frozen=True, slots=True)
class LicenceCondition:
    """One USE flag, and the licences that come with agreeing to it."""

    #: The flag as ``LICENSE`` wrote it, ``!`` and all.
    token: str
    #: Licences that appear when the condition holds and are not accepted today.
    licences: tuple[str, ...]

    @property
    def flag(self) -> str:
        return self.token.lstrip("!")

    @property
    def when_enabled(self) -> bool:
        """``True`` when turning the flag *on* is what brings the licences in."""
        return not self.token.startswith("!")


@dataclass(frozen=True, slots=True)
class ConditionalLicence:
    """A package whose licence bill is not fixed until USE is decided."""

    cpv: str
    cp: str
    repo: str
    #: ``LICENSE`` exactly as the ebuild wrote it.
    expression: str
    #: Not accepted as the package would be built today.
    missing_now: tuple[str, ...]
    #: What each flag would add on top of that.
    conditions: tuple[LicenceCondition, ...]


def conditions_for(
    cpv: str, repo: str = "", env: PortageEnv | None = None
) -> ConditionalLicence | None:
    """How *cpv*'s licences depend on its USE flags, or ``None`` if they do not.

    Every answer comes from ``getMissingLicenses``, asked once per condition
    with the flag flipped. Nothing here evaluates ``LICENSE`` itself; the regex
    only picks out *which* flags to ask about, and Portage decides what each
    one means — including the nesting and the ``||`` groups a regex could not
    survive.

    Only licences this system does not already accept are reported. A
    ``handbook? ( FDL-1.3 )`` on a machine whose ``ACCEPT_LICENSE`` covers
    ``@FREE`` changes nothing anybody needs telling about.
    """
    env = env or _default_env()
    manager = getattr(env.settings, "_license_manager", None)
    if manager is None:  # pragma: no cover
        return None
    try:
        expression, slot, repository = env.portdb.aux_get(
            cpv, ["LICENSE", "SLOT", "repository"], myrepo=repo or None
        )
    except Exception:  # pragma: no cover - unreadable ebuild
        return None
    if "?" not in expression:
        return None

    where = repo or repository
    short_slot = slot.partition("/")[0]
    try:
        with env.configured(cpv) as settings:
            use = (settings.get("PORTAGE_USE") or "").split()
        now = tuple(manager.getMissingLicenses(cpv, " ".join(use), expression, short_slot, where))

        conditions = []
        for token in dict.fromkeys(_CONDITION.findall(expression)):
            flag = token.lstrip("!")
            # Satisfy the condition, whichever way round it is written, and ask
            # again. The difference is what agreeing to that flag would cost.
            if token.startswith("!"):
                flipped = [item for item in use if item != flag]
            else:
                flipped = [*use, flag]
            added = tuple(
                name
                for name in manager.getMissingLicenses(
                    cpv, " ".join(flipped), expression, short_slot, where
                )
                if name not in now
            )
            if added:
                conditions.append(LicenceCondition(token, added))
    except Exception:  # pragma: no cover - a LICENSE Portage cannot parse
        log.warning("Could not work out the licence conditions of %s", cpv, exc_info=True)
        return None

    if not conditions:
        return None
    return ConditionalLicence(
        cpv=cpv,
        cp=_cp_of(cpv),
        repo=where,
        expression=expression,
        missing_now=now,
        conditions=tuple(conditions),
    )


def conditional_licences(env: PortageEnv | None = None) -> tuple[ConditionalLicence, ...]:
    """Every package here whose licence bill can grow when a flag is turned on.

    The newest version of each package is the one asked about, because that is
    the one an install would pick up.

    Deliberately not every package with a conditional ``LICENSE`` — there are a
    couple of hundred of those and almost all are ``doc?`` or ``handbook?``
    pulling in a licence the system already accepts. What is worth a screen is
    the shorter list where saying yes to a flag means saying yes to a licence
    nobody has agreed to yet: ``rar? ( unRAR )``, ``x-pack? ( Elastic )``,
    ``cuda? ( NVIDIA-CUDA )``. Those are the ones that stop an install after
    the user thought the licence question was settled.

    Cached: the scan reads ``LICENSE`` for every package in every repository,
    which is seconds rather than milliseconds. :func:`clear_caches` drops it.
    """
    global _CONDITIONAL, _CONDITIONAL_FOR
    env = env or _default_env()
    if _CONDITIONAL is not None and _CONDITIONAL_FOR is env:
        return _CONDITIONAL

    found: list[ConditionalLicence] = []
    for cp in env.portdb.cp_all():
        versions = env.portdb.cp_list(cp)
        if not versions:
            continue
        cpv = versions[-1]
        entry = conditions_for(str(cpv), getattr(cpv, "repo", "") or "", env)
        if entry is not None:
            found.append(entry)

    _CONDITIONAL = tuple(found)
    _CONDITIONAL_FOR = env
    return _CONDITIONAL


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
