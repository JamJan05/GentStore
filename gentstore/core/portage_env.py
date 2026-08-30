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
        "_clone_lock",
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

    @contextmanager
    def configured(self, cpv: str) -> Iterator[Any]:
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

        *cpv* alone identifies the package: ``setcpv()`` reads its metadata
        through ``dbapi.aux_get()``, which takes no repository hint, so a
        package carried by two repositories is described by whichever of them
        Portage ranks higher. Callers that need a specific repository pass it
        to the query itself, not here.
        """
        import portage  # noqa: PLC0415 — slow import, deferred

        with self._clone_lock:
            if self._clone is None:
                # Built on demand and kept: cloning is cheap next to reading the
                # profile stack, but not free, and this runs per selected
                # package. It never needs invalidating, because the only way to
                # get a newer configuration is a new PortageEnv.
                self._clone = portage.config(clone=self._settings)
            self._clone.setcpv(cpv, mydb=self._portdb)
            yield self._clone

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
