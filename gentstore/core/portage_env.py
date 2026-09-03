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

"""The single shared handle on Portage's configuration and databases.

Building Portage's configuration means reading ``make.conf``, the whole profile
stack and every ``repos.conf`` entry. It is far too expensive to repeat per
query, so it happens once and the result is shared. Anything that invalidates it
— a sync, a ``make.conf`` edit, enabling an overlay — calls :func:`reload`
explicitly; nothing here ever refreshes itself behind the caller's back, because
a silently changing package list is impossible to reason about in a GUI.

Portage's own module-level ``portage.settings`` / ``portage.db`` globals are
deliberately *not* used. They are built at import time, they cannot be rebuilt,
and mutating them would leak Gentstore's state into every other consumer in the
process. :func:`portage.create_trees` gives us a private set instead.
"""

from __future__ import annotations

import logging
import os
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime
    from collections.abc import Iterator

log = logging.getLogger(__name__)

#: The metadata keys ``config.setcpv()`` reads out of whatever it is given.
#:
#: Portage keeps the same list twice, as ``config._setcpv_aux_keys`` and as
#: ``portdbapi._aux_cache_keys``, and both are private. Both are read at runtime
#: when they are there — a key added to Portage is then picked up without an
#: edit here — and this copy is the answer when they are not.
#:
#: There is a public list, ``portage.auxdbkeys``, and it is not the same thing:
#: it does not contain ``repository``. That is the one key this whole
#: arrangement exists for, so the public name would be a stabler source for an
#: answer that no longer works. The private ones stay, with a contract test on
#: the copy below and a warning when the fallback is what answers.
#:
#: ``repository`` is the one that does the work. ``setcpv()`` pops it and uses it
#: to pick the repository-level ``package.use``, ``use.stable`` and
#: ``make.defaults`` that apply, which is the whole reason for handing over
#: metadata instead of the database.
_AUX_KEYS = (
    "BDEPEND",
    "DEFINED_PHASES",
    "DEPEND",
    "EAPI",
    "IDEPEND",
    "INHERITED",
    "IUSE",
    "KEYWORDS",
    "LICENSE",
    "PDEPEND",
    "PROPERTIES",
    "RDEPEND",
    "REQUIRED_USE",
    "RESTRICT",
    "SLOT",
    "repository",
)

#: How many per-repository metadata mappings one environment keeps. See
#: :meth:`PortageEnv._metadata` for why they are kept at all.
_METADATA_CACHE_MAX = 256

#: What has already been said about this Portage not being shaped as expected.
#:
#: Once per process, not once per package: it is a fact about the installation,
#: and the questions below are asked every time somebody clicks a package.
_WARNED: set[str] = set()


def _warn_once(subject: str, message: str) -> None:
    if subject in _WARNED:
        return
    _WARNED.add(subject)
    log.warning(message)


class PortageUnavailableError(RuntimeError):
    """Raised when the ``portage`` module cannot be imported or configured.

    Carries the original exception so the interface can show the real reason
    ("no module named portage") rather than a generic failure.
    """


class PortageEnv:
    """One consistent view of the local Portage installation.

    Attribute access is read-only on purpose: a :class:`PortageEnv` describes the
    system at one moment in time, and the way to get a newer view is to build a
    new instance via :func:`reload`.
    """

    __slots__ = (
        "_bindb",
        "_clone",
        "_clone_depth",
        "_clone_lock",
        "_metadata_cache",
        "_portdb",
        "_root",
        "_settings",
        "_trees",
        "_vardb",
    )

    def __init__(self, trees: dict[str, Any], root: str) -> None:
        self._trees = trees
        self._root = root
        node = trees[root]
        self._settings = node["vartree"].settings
        self._portdb = node["porttree"].dbapi
        self._vardb = node["vartree"].dbapi
        self._bindb = node["bintree"].dbapi
        self._clone: Any = None
        self._clone_lock = threading.RLock()
        self._clone_depth = 0
        self._metadata_cache: dict[tuple[str, str], dict[str, str]] = {}

    # -- handles -----------------------------------------------------------

    @property
    def settings(self) -> Any:
        """``portage.config`` — make.conf, profile and everything derived."""
        return self._settings

    @property
    def portdb(self) -> Any:
        """The ebuild repositories (``portdbapi``): what can be installed."""
        return self._portdb

    @property
    def vardb(self) -> Any:
        """``/var/db/pkg`` (``vardbapi``): what *is* installed."""
        return self._vardb

    @property
    def bindb(self) -> Any:
        """Binary packages (``bindbapi``): ``$PKGDIR`` plus configured binhosts."""
        return self._bindb

    # -- the per-package view ----------------------------------------------

    def _aux_keys(self) -> list[str]:
        """The keys to ask for: what ``setcpv()`` reads, that the cache can answer.

        Portage intersects the two itself in the branch that takes a database,
        and asking a repository cache for a key it does not carry is an error
        rather than an empty string, so the same intersection is done here.
        """
        import portage  # noqa: PLC0415 — slow import, deferred

        asked_for = getattr(portage.config, "_setcpv_aux_keys", None)
        if asked_for is None:
            # Worth saying out loud. The failure this produces is not a crash:
            # a key Portage has added since and this file has not would simply
            # be absent from the mapping, and the package would be described
            # with a piece missing rather than wrongly. That is the kind of
            # thing nobody notices without being told.
            _warn_once(
                "setcpv_aux_keys",
                "This Portage does not expose config._setcpv_aux_keys. Falling back to "
                "Gentstore's own copy of the list (gentstore/core/portage_env.py, "
                "_AUX_KEYS); if Portage has added a metadata key since, the per-package "
                "view will not carry it.",
            )
            asked_for = _AUX_KEYS

        wanted = set(asked_for)
        available = getattr(self._portdb, "_aux_cache_keys", None)
        if available:
            wanted &= set(available)
        else:
            _warn_once(
                "aux_cache_keys",
                "This Portage does not expose portdbapi._aux_cache_keys. Asking the "
                "repository cache for every key Gentstore knows about, which it may "
                "refuse rather than answer.",
            )
        return sorted(wanted)

    def _metadata(self, cpv: str, repo: str) -> dict[str, str]:
        """*cpv*'s metadata as *repo* carries it, for :meth:`configured`.

        Kept rather than rebuilt, and the reason is not speed. ``setcpv()``
        remembers the last call as ``(cpv, id(mydb))`` and returns early when the
        next one matches. A mapping built fresh each time is freed as soon as the
        block ends, and CPython hands the next one of the same size the address
        it just released — so asking for the same package in a second repository
        could produce the same pair, and the answer for the first repository
        would be returned for the second. Handing back the same object for the
        same question makes that pair mean what it says.
        """
        key = (cpv, repo)
        found = self._metadata_cache.get(key)
        if found is not None:
            return found

        keys = self._aux_keys()
        values = self._portdb.aux_get(cpv, keys, myrepo=repo)
        metadata = dict(zip(keys, values, strict=True))

        if len(self._metadata_cache) >= _METADATA_CACHE_MAX:
            # Oldest first, which for a dict is insertion order. The cache exists
            # for identity, not for hit rate, so a plain bound is enough.
            del self._metadata_cache[next(iter(self._metadata_cache))]
        self._metadata_cache[key] = metadata
        return metadata

    def _describe(self, cpv: str, repo: str) -> Any:
        """What to hand ``setcpv()``: one repository's metadata, or the database."""
        return self._metadata(cpv, repo) if repo else self._portdb

    @contextmanager
    def configured(self, cpv: str, repo: str = "") -> Iterator[Any]:
        """The configuration as it looks *for one package*, borrowed under a lock.

        Several of Portage's own entry points call ``config.setcpv()`` on
        whatever settings object they are handed — ``getmaskingstatus()`` does
        it for any package whose ``LICENSE`` carries a USE conditional, because
        until USE is resolved there is no telling which licences even apply.
        :attr:`settings` is locked exactly so that nothing rewrites the
        system-wide view underneath its readers, so passing it to those entry
        points raises ``Configuration is locked.``. A clone is what they want.

        Yielded rather than returned, and deliberately so. ``setcpv()`` leaves
        the last package's ``PORTAGE_USE`` and ``configdict["pkg"]`` behind in
        the object it was called on, which makes the clone a description of one
        package rather than of the system; code that mistook it for
        :attr:`settings` would read one package's answers for another's. Inside
        the ``with`` block it is also the caller's alone, so hold it for the
        read and no longer. Re-entrant, because these questions nest naturally
        — one package's blocks are also a question about its licences — and a
        plain lock would turn that into a deadlock rather than an answer.

        *repo* is which repository's copy of *cpv* to describe, and matters
        whenever two repositories carry the same version. Handed the database,
        ``setcpv()`` calls ``aux_get()`` without a repository hint and Portage
        answers from whichever repository it ranks higher — so the metadata a
        caller had already fetched with ``myrepo=`` and the configuration
        described here could be two different packages with one name. It is not
        only ``IUSE`` that diverges: ``setcpv()`` pops ``repository`` out of the
        metadata and uses it to pick the repository-level ``package.use``,
        ``use.stable`` and ``make.defaults`` that apply, so the repository
        decides the answer twice over.

        So when *repo* is given, the metadata is fetched with ``myrepo=`` and
        handed over as a mapping. Portage's own ``setcpv()`` has a branch for
        that — it takes each key it wants straight out of the mapping instead of
        querying a database — and it is the branch ``Package`` objects go
        through, so this is the supported way to say which one is meant rather
        than a way round the question.

        Left empty, the old behaviour: the database, and whichever repository
        Portage ranks higher. That is right for the callers that have no
        repository in hand and would otherwise have to invent one.
        """
        import portage  # noqa: PLC0415 — slow import, deferred

        with self._clone_lock:
            if self._clone_depth:
                # A nested question, which the paragraph above says is a normal
                # thing to ask. The block outside this one is holding the shared
                # clone and still expects it to describe *its* package; calling
                # setcpv() on that object would repoint it, and when this block
                # ended the outer reader would carry on reading one package's
                # answers for another's — quietly, and only for the questions
                # asked after the nested one returned. Rare enough to pay for a
                # clone of its own.
                nested = portage.config(clone=self._settings)
                nested.setcpv(cpv, mydb=self._describe(cpv, repo))
                yield nested
                return
            if self._clone is None:
                # Built on demand and kept: cloning is cheap next to reading the
                # profile stack, but not free, and this runs per selected
                # package. It never needs invalidating, because the only way to
                # get a newer configuration is a new PortageEnv.
                self._clone = portage.config(clone=self._settings)
            self._clone_depth += 1
            try:
                self._clone.setcpv(cpv, mydb=self._describe(cpv, repo))
                yield self._clone
            finally:
                self._clone_depth -= 1

    # -- frequently needed scalars ----------------------------------------

    @property
    def root(self) -> str:
        return self._root

    @property
    def eroot(self) -> str:
        return self._settings["EROOT"]

    @property
    def arch(self) -> str:
        """The profile's ``ARCH``, e.g. ``amd64``. Empty string if unset."""
        return self._settings.get("ARCH") or ""

    @property
    def accept_keywords(self) -> tuple[str, ...]:
        return tuple((self._settings.get("ACCEPT_KEYWORDS") or "").split())

    @property
    def repo_names(self) -> tuple[str, ...]:
        """Repository names in Portage's own priority order (lowest first).

        ``prepos_order`` is the order Portage itself resolves duplicates in, so
        using it keeps Gentstore's idea of "which repo wins" identical to
        ``emerge``'s.
        """
        return tuple(self._settings.repositories.prepos_order)

    @property
    def main_repo_name(self) -> str | None:
        repo = self._settings.repositories.mainRepo()
        return repo.name if repo is not None else None

    def repo(self, name: str) -> Any | None:
        """The ``RepoConfig`` for *name*, or ``None`` if there is no such repo."""
        try:
            return self._settings.repositories[name]
        except KeyError:
            return None

    def repo_location(self, name: str) -> str | None:
        repo = self.repo(name)
        return getattr(repo, "location", None) if repo is not None else None

    def repos(self) -> Iterator[Any]:
        """Every configured ``RepoConfig``, in priority order."""
        for name in self.repo_names:
            repo = self.repo(name)
            if repo is not None:
                yield repo


_env: PortageEnv | None = None
#: Portage's configuration objects are not safe to build concurrently, so the
#: first caller does the work and everybody else waits for its result.
_lock = threading.RLock()


def _build() -> PortageEnv:
    try:
        import portage  # noqa: PLC0415 — deliberately deferred, the import is slow
    except Exception as exc:  # pragma: no cover - depends on the host system
        raise PortageUnavailableError(str(exc)) from exc

    try:
        trees = portage.create_trees(config_root=None, target_root=None, env=os.environ)
        root = portage.root if portage.root in trees else next(iter(trees))
        env = PortageEnv(trees, root)
    except Exception as exc:  # pragma: no cover - depends on the host system
        raise PortageUnavailableError(str(exc)) from exc

    log.info(
        "Portage configuration loaded: ARCH=%s repositories=%s",
        env.arch,
        ", ".join(env.repo_names),
    )
    return env


def env() -> PortageEnv:
    """Return the shared environment, building it on first use.

    Raises :class:`PortageUnavailableError` if Portage is not usable here.
    """
    global _env
    with _lock:
        if _env is None:
            _env = _build()
        return _env


def reload() -> PortageEnv:
    """Discard the cached environment and read the configuration again.

    Call after a sync, after writing to ``/etc/portage`` and after enabling or
    disabling a repository. Caches derived from the old environment (the search
    index, the repository list) must be rebuilt by their owners — this function
    does not know about them.
    """
    global _env
    with _lock:
        _env = _build()
        return _env


def is_loaded() -> bool:
    """Whether the environment has already been built (used by tests and logs)."""
    with _lock:
        return _env is not None
