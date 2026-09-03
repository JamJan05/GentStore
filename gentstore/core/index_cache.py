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

"""Keeping the search index between runs of the application.

Building the index means asking Portage for every ``cat/pkg`` in every enabled
repository and reading a ``DESCRIPTION`` for each of them — twenty-two thousand
of those, and seconds of work even with the tree already in the page cache. The
answer does not change until the tree does, so paying for it once per start is
paying for it too often.

This module writes the finished index out and reads it back, which costs a
fraction of a second. Two things make that safe:

*Where* it is written. ``$XDG_RUNTIME_DIR`` is the per-user tmpfs the system
creates at login and removes when the last session ends, so a cached index
cannot outlive the boot that produced it. Without that variable — a bare TTY, a
container — the file falls back to ``~/.cache``, where it does survive a reboot;
the fingerprint below is what makes that harmless rather than a second rule.

*What is checked before it is used.* :func:`fingerprint` describes the state of
the repositories in a few milliseconds: which ones are configured, where they
are, and when each of their top-level directories was last written. A sync, an
overlay enabled or disabled, an ebuild added to a local repository — each moves
one of those timestamps, and a cache whose fingerprint no longer matches is
ignored and rebuilt. It is a cheap check by design: it runs before every read,
on the path whose whole purpose is to be fast.

The one thing deliberately *not* cached is which packages are installed. It is a
single ``cpv_all()`` and changes after every install, so it is re-read on load
rather than stored — see :meth:`~gentstore.core.packages.SearchIndex.refresh_installed`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path

from .packages import IndexEntry, SearchIndex
from .portage_env import PortageEnv
from .portage_env import env as _default_env
from .worldset import installed_cps

log = logging.getLogger(__name__)

#: Bumped whenever the layout of the file below changes. An older or newer file
#: is not read, it is rebuilt: the cache is worth nothing and costs nothing to
#: throw away, so it never needs a migration.
FORMAT = 1

#: Set to ``0`` to build the index from Portage every time — for measuring what
#: the cache is worth, and for the case where it is suspected of lying.
ENV_VARIABLE = "GENTSTORE_INDEX_CACHE"

#: Refuse to read a file larger than this. Twenty-two thousand packages come to
#: about two megabytes; ten is room to grow and still a bound on the damage a
#: corrupted length field can do.
_SIZE_LIMIT = 10 * 1024 * 1024


def enabled() -> bool:
    """Whether the cache is in use at all. ``GENTSTORE_INDEX_CACHE=0`` turns it off."""
    return os.environ.get(ENV_VARIABLE, "1") != "0"


def directory() -> Path:
    """Where the cache file lives — the runtime directory if there is one.

    ``$XDG_RUNTIME_DIR`` is preferred precisely because it is not permanent:
    the system clears it when the session ends, which is the invalidation rule
    nobody has to write. The fallback is an ordinary cache directory, and the
    fingerprint carries the whole burden there.
    """
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        return Path(runtime) / "gentstore"
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "gentstore"


def path() -> Path:
    """The cache file itself."""
    return directory() / "search-index.json"


# ---------------------------------------------------------------------------
# what the cache is checked against
# ---------------------------------------------------------------------------


def fingerprint(env: PortageEnv | None = None) -> str:
    """A short digest of the repository state the index was built from.

    Everything that can change what the index would contain shows up here: the
    set of repositories, where each one is, and the modification time of every
    directory directly inside it. That last part is what catches a package
    appearing in a local overlay — the category directory is written when a new
    ``cat/pkg`` is added to it — as well as the ordinary case of a sync, which
    rewrites ``metadata/`` and ``profiles/`` and so moves those timestamps too.

    What it does not catch is an ebuild edited in place inside an existing
    package directory, which changes a description without changing any
    directory above it. That is a local-development situation and it has an
    answer already: “Rebuild the index” after a sync throws the file away.
    """
    env = env or _default_env()
    parts: list[str] = [f"format={FORMAT}"]
    for name in env.repo_names:
        location = env.repo_location(name)
        parts.append(f"repo={name}@{location or '-'}")
        if not location:
            continue
        try:
            root = Path(location)
            parts.append(f"mtime={root.stat().st_mtime_ns}")
            for entry in sorted(os.scandir(root), key=lambda item: item.name):
                if entry.is_dir(follow_symlinks=False):
                    parts.append(f"{entry.name}={entry.stat().st_mtime_ns}")
        except OSError as exc:  # a repository listed in repos.conf but not on disk
            parts.append(f"unreadable={exc.errno}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# reading and writing
# ---------------------------------------------------------------------------


def load(env: PortageEnv | None = None) -> SearchIndex | None:
    """The cached index, or ``None`` if there is not a usable one.

    Never raises: an unreadable, truncated or stale file is a cache miss, and a
    cache miss only costs the build that was going to happen anyway.
    """
    if not enabled():
        return None
    env = env or _default_env()
    file = path()
    started = time.monotonic()
    try:
        if file.stat().st_size > _SIZE_LIMIT:
            log.warning("Ignoring the index cache: %s is implausibly large", file)
            return None
        document = json.loads(file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        log.warning("Ignoring the index cache: %s", exc)
        return None

    if not isinstance(document, dict) or document.get("format") != FORMAT:
        return None
    if document.get("fingerprint") != fingerprint(env):
        log.info("The index cache is stale — the repositories changed since it was written")
        return None

    try:
        entries = tuple(_entry(row) for row in document["entries"])
    except (KeyError, TypeError, ValueError) as exc:
        log.warning("Ignoring the index cache: %s", exc)
        return None

    index = SearchIndex(
        entries=entries,
        installed=installed_cps(env),
        repos=tuple(document.get("repos", ())),
        built_at=float(document.get("built_at", 0.0)),
        build_seconds=float(document.get("build_seconds", 0.0)),
    )
    log.info(
        "Search index read from cache: %d packages in %.2f s (built in %.2f s)",
        len(index),
        time.monotonic() - started,
        index.build_seconds,
    )
    return index


def store(index: SearchIndex, env: PortageEnv | None = None) -> bool:
    """Write *index* out for the next start. ``True`` if it was written.

    Written to a neighbouring temporary file and renamed over the target, so a
    second instance reading at the same moment sees either the whole of the old
    file or the whole of the new one, never half of either.
    """
    if not enabled():
        return False
    file = path()
    temporary = file.with_name(f"{file.name}.{os.getpid()}")
    document = {
        "format": FORMAT,
        "fingerprint": fingerprint(env),
        "repos": list(index.repos),
        "built_at": index.built_at,
        "build_seconds": index.build_seconds,
        # Only what cannot be derived on load: the folded fields are lowercase
        # copies and the category is the half of cp before the slash.
        "entries": [[entry.cp, entry.description, list(entry.repos)] for entry in index.entries],
    }
    try:
        # 0o700: the runtime directory is already private, the fallback under
        # ~/.cache is not, and this says what the cache is worth either way.
        file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        temporary.replace(file)
    except OSError as exc:
        log.warning("Could not write the index cache: %s", exc)
        temporary.unlink(missing_ok=True)
        return False
    log.info("Search index cached in %s", file)
    return True


def discard() -> None:
    """Delete the cache. Called when the index is rebuilt on purpose."""
    try:
        path().unlink(missing_ok=True)
    except OSError as exc:  # pragma: no cover - a read-only cache directory
        log.warning("Could not remove the index cache: %s", exc)


def cached_index(env: PortageEnv | None = None, on_progress=None) -> SearchIndex:  # noqa: ANN001
    """The index: from the cache if it is current, otherwise built and cached.

    This is the entry point every caller wants —
    :meth:`~gentstore.core.packages.SearchIndex.build` stays the way to get an
    index that is unquestionably read from Portage right now.
    """
    env = env or _default_env()
    index = load(env)
    if index is not None:
        if on_progress is not None:
            on_progress(len(index), len(index))
        return index
    index = SearchIndex.build(env, on_progress)
    store(index, env)
    return index


def _entry(row: object) -> IndexEntry:
    """One stored row back into an :class:`~gentstore.core.packages.IndexEntry`."""
    cp, description, repos = row  # type: ignore[misc]
    category, _, name = str(cp).partition("/")
    return IndexEntry(
        cp=cp,
        category=category,
        name=name,
        description=description,
        repos=tuple(repos),
        fold_name=name.lower(),
        fold_cp=cp.lower(),
        fold_description=description.lower(),
    )
