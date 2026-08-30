"""Backups of ``/etc/portage`` — finding them, naming them, deciding when.

Making and restoring one needs root and happens in the helper. This module is
the unprivileged half: ``/etc`` is world-readable, so listing what exists needs
no privileges at all, and neither does deciding whether this run of the
application has taken its backup yet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

#: Kept in step with ``gentstore/helper/gentstore_helper.py``. Duplicated rather
#: than imported: the helper is deliberately standalone, and a constant either
#: side of the privilege boundary is cheaper than coupling them.
BACKUP_PARENT = Path("/etc")
BACKUP_PREFIX = "portage.bak-"
BACKUP_KEEP = 10

_NAME = re.compile(r"^portage\.bak-(\d{4}-\d{2}-\d{2}T\d{2}\d{2})(?:-(\d+))?$")


@dataclass(frozen=True, slots=True)
class BackupInfo:
    """One copy of ``/etc/portage``."""

    name: str
    path: Path
    created: datetime | None

    @property
    def label(self) -> str:
        """What the sidebar shows: the timestamp, without the fixed prefix."""
        return self.name[len(BACKUP_PREFIX):]


def _parse(name: str) -> datetime | None:
    match = _NAME.match(name)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%dT%H%M")
    except ValueError:  # pragma: no cover - a directory named to look like one
        return None


def list_backups(parent: Path | None = None) -> tuple[BackupInfo, ...]:
    """Every backup, newest first. Never raises; an unreadable ``/etc`` is empty."""
    root = parent or BACKUP_PARENT
    try:
        entries = list(root.iterdir())
    except OSError:
        return ()

    found = []
    for entry in entries:
        if not entry.is_dir():
            continue
        created = _parse(entry.name)
        if created is None:
            continue
        found.append(BackupInfo(name=entry.name, path=entry, created=created))
    # By name, not by mtime: the name is the moment the copy was taken, and the
    # mtime of a directory changes for reasons that have nothing to do with it.
    return tuple(sorted(found, key=lambda item: item.name, reverse=True))


def latest(parent: Path | None = None) -> BackupInfo | None:
    backups = list_backups(parent)
    return backups[0] if backups else None


class BackupTracker:
    """Whether this run of the application has taken its backup yet.

    One copy per run, not per change: a session that edits six USE flags would
    otherwise leave six near-identical copies of ``/etc/portage`` behind, and
    the ten that are kept would all be from the same afternoon.

    The tracker only decides *when to ask*; the copy itself is made by the
    helper, inside the same privileged call as the change it protects, so a
    change can never land without one.
    """

    def __init__(self) -> None:
        self._taken: str | None = None

    @property
    def taken(self) -> str | None:
        """Path of this run's backup, once there is one."""
        return self._taken

    def needs_backup(self) -> bool:
        return self._taken is None

    def note(self, path: str | None) -> None:
        """Record the backup the helper reported making."""
        if path:
            self._taken = path

    def reset(self) -> None:
        """Forget it — used by the tests, and after a restore."""
        self._taken = None


# ---------------------------------------------------------------------------
# comparing a backup with the present
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Change:
    """One difference between a backup and ``/etc/portage`` as it stands."""

    #: ``added`` (only in the backup), ``removed`` (only now), ``changed``.
    kind: str
    #: Path relative to the configuration root.
    relative: str

    @property
    def restores_to(self) -> str:
        """What restoring would do to this file, in one word."""
        return {"added": "restored", "removed": "deleted", "changed": "replaced"}[self.kind]


def _tree(root: Path) -> dict[str, bytes]:
    """Every regular file under *root*, keyed by relative path.

    ``/etc/portage`` is small — a few dozen files — so reading it whole to
    compare is cheaper than being clever, and the answer is exact.
    """
    files: dict[str, bytes] = {}
    if not root.is_dir():
        return files
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            files[str(path.relative_to(root))] = path.read_bytes()
        except OSError:  # pragma: no cover - unreadable mid-scan
            continue
    return files


def compare(backup: Path, current: Path) -> tuple[Change, ...]:
    """What restoring *backup* over *current* would change.

    Docs/04-privileges.md §5: restoring is a change to the system like any
    other, so it gets the same treatment — shown before it happens. Naming the
    files is the honest minimum; the diff of any one of them follows on demand.
    """
    old, new = _tree(backup), _tree(current)
    changes = []
    for name in sorted(set(old) | set(new)):
        if name not in new:
            changes.append(Change("added", name))
        elif name not in old:
            changes.append(Change("removed", name))
        elif old[name] != new[name]:
            changes.append(Change("changed", name))
    return tuple(changes)


def file_diff(backup: Path, current: Path, relative: str):  # noqa: ANN201 - DiffLine tuple
    """The difference for one file inside a backup."""
    from .cfgfiles import unified  # noqa: PLC0415 — avoids a cycle at import

    def read(root: Path) -> list[str]:
        path = root / relative
        try:
            return path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        except OSError:
            return []

    return unified(read(current), read(backup), f"now: {relative}", f"backup: {relative}")
