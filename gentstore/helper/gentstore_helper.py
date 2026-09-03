#!/usr/bin/env python3
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

"""Write to ``/etc/portage`` on behalf of the interface. Runs as root.

One JSON request on stdin, one JSON response on stdout, then exit. The set of
operations is closed and every one of them re-checks its own arguments: the
caller is a program the user is running, but this process is root, and the two
facts together mean nothing arriving on stdin may be taken on trust.

    $ echo '{"op": "append_line", "path": "/etc/portage/package.use/mpv",
             "line": "media-video/mpv vulkan"}' | gentstore-helper
    {"ok": true, "op": "append_line", "changed": true, ...}

What it may touch is narrower than ``/etc/portage``: whole-file writes reach
:data:`OWNED_SUBTREES` and line edits reach :data:`LINE_EDITABLE`, which between
them are the files Gentstore itself produces. Everything else under there —
``bashrc``, ``package.env``, ``env/``, ``postsync.d`` — is refused, and refused
by not being on a list rather than by being on one.

Standard library only, single file, no imports from the rest of Gentstore — so
that reading it is a matter of reading one file.
"""

from __future__ import annotations

import grp
import json
import os
import pwd
import re
import shutil
import stat
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

#: Everything this program may touch lives under here.
#:
#: A constant, deliberately: not an argument, not an environment variable. The
#: caller chooses the argv and (under ``sudo``) part of the environment, so
#: anything it could set would be a way to point the write somewhere else. The
#: tests replace this attribute after importing the module, which the installed
#: program has no way to do.
CONFIG_ROOT = Path("/etc/portage")

#: The files ``append_line``, ``replace_line`` and ``remove_line`` may touch,
#: and nothing else under :data:`CONFIG_ROOT`.
#:
#: A list of what Gentstore writes, not a list of what looks dangerous. Half of
#: ``/etc/portage`` is code by another name — ``bashrc`` is sourced during every
#: merge, ``package.env`` names files in ``env/`` that set any variable a build
#: sees, ``postsync.d`` holds programs run after a sync — and none of them is a
#: file this application has ever needed to write a line to. Naming what is
#: allowed keeps out the ones nobody has thought of yet, which a list of
#: forbidden names cannot do.
#:
#: Every entry here is produced by gentstore/core/confedit.py or
#: gentstore/core/makeconf.py; adding a file to this tuple means the interface
#: has learned to write one, and is a decision to make on purpose.
LINE_EDITABLE = (
    "package.use",
    "package.accept_keywords",
    "package.license",
    "package.unmask",
    "package.mask",
    "make.conf",
)

#: How deep under :data:`CONFIG_ROOT` each of those may go.
#:
#: A ``package.*`` name is either a file or a directory holding one file per
#: package, which is as far as Gentstore ever looks or writes; Portage would
#: read a deeper tree, but nothing here builds a path into one. ``make.conf`` is
#: a file and only a file.
LINE_EDITABLE_DEPTH = 2
MAKE_CONF_DEPTH = 1

#: ``write_file`` and ``delete_file`` are limited to these subtrees — the only
#: files Gentstore creates whole rather than adding a line to. Both hold one
#: INI section per repository and are written by ``eselect`` or by us, never
#: hand-edited into something we would be destroying.
OWNED_SUBTREES = ("repos.conf", "binrepos.conf")

#: Files that tell us which directories Portage protects, in the order Portage
#: itself reads them. All of them are owned by root — though see
#: :data:`PROTECT_CEILINGS` for why that is not the whole answer.
CONFIG_PROTECT_SOURCES = (
    Path("/usr/share/portage/config/make.globals"),
    Path("/etc/portage/make.conf"),
)
ENV_D = Path("/etc/env.d")

#: Used when none of those can be read. The defaults Gentoo has shipped for
#: twenty years; a system with a stranger CONFIG_PROTECT keeps dispatch-conf.
DEFAULT_PROTECTED = ("/etc", "/usr/share/config")

#: Where backups of CONFIG_ROOT go, and how many are kept.
BACKUP_PARENT = Path("/etc")
BACKUP_PREFIX = "portage.bak-"
BACKUP_KEEP = 10
#: Never keep fewer than this however the request is worded: a backup that is
#: deleted as soon as it is made protects nothing.
BACKUP_KEEP_MIN = 1
BACKUP_KEEP_MAX = 100

#: Superseded configuration files are moved here, the way ``dispatch-conf``
#: does it, instead of being deleted.
CONFIG_ARCHIVE = Path("/etc/config-archive")

PROTOCOL_VERSION = 1

_BACKUP_NAME = re.compile(r"^portage\.bak-\d{4}-\d{2}-\d{2}T\d{4}(-\d+)?$")
_ARCHIVE_NAME = re.compile(r"^portage\.bak-\d{4}-\d{2}-\d{2}T\d{4}(-\d+)?\.tar\.gz$")
_CFG_PREFIX = re.compile(r"^\._cfg\d{4}_")

#: Longest ``match`` pattern ``replace_line`` will compile.
#:
#: A bound, not a cure: nothing in the standard library can time a regular
#: expression out, so a pattern crafted to backtrack for ever would hang this
#: process — as root — until somebody killed it. Every pattern Gentstore itself
#: sends is built with ``re.escape`` around one ``cat/pkg`` (see
#: gentstore/core/confedit.py), so the length limit costs nothing real and
#: takes the easiest version of that away.
PATTERN_MAX = 256


class HelperError(Exception):
    """A refusal with a machine-readable reason."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# path handling
# ---------------------------------------------------------------------------


def _root() -> Path:
    """The resolved configuration root. Resolved once, so a symlinked
    ``/etc/portage`` works and a swapped one cannot be raced."""
    try:
        return CONFIG_ROOT.resolve(strict=True)
    except OSError as exc:
        raise HelperError("no_config_root", f"{CONFIG_ROOT} is not readable: {exc}") from exc


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _only_root_can_write(path: Path) -> bool:
    """Whether *path* and every directory above it belong to root alone.

    The one hole in the paragraph on :data:`CONFIG_PROTECT_SOURCES`. Those files
    are root-owned, but ``/etc/portage/make.conf`` is also a file this very
    program appends lines to on request — so a caller can write a CONFIG_PROTECT
    of its own and then ask ``cfg_apply`` to follow it somewhere new.

    What actually matters about "somewhere new" is not where it is. Portage
    users put all sorts of things in CONFIG_PROTECT and a list of blessed
    prefixes would only break the ones nobody thought of. What matters is
    whether an unprivileged user could have planted the ``._cfgNNNN_`` file that
    lands there, and that is a question about ownership. No sticky-bit exception
    here, unlike :func:`gentstore.runner.privilege._tampering_risk`: creating a
    new file is exactly what the sticky bit still allows, and creating one is
    the whole of the trick.

    Asked only when we are root, which is the only time the answer means
    anything — run unprivileged, as the test suite does, every directory in a
    fixture belongs to whoever is running it, and refusing on that would be
    refusing the person asking.
    """
    if os.geteuid() != 0:
        return True
    for candidate in (path, *path.parents):
        try:
            info = candidate.stat()
        except OSError:
            return False
        if info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            return False
    return True


def _config_protect_values(text: str) -> list[str]:
    """Pull ``CONFIG_PROTECT="…"`` out of a shell-ish configuration file.

    Deliberately not a shell parser: only a bare assignment on its own line is
    recognised, quoted or not. Anything cleverer would be a way to talk this
    program into writing somewhere new.
    """
    found = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("CONFIG_PROTECT="):
            continue
        value = stripped[len("CONFIG_PROTECT="):].strip()
        if value[:1] in ("'", '"') and value[-1:] == value[:1]:
            value = value[1:-1]
        found.extend(part for part in value.split() if part.startswith("/"))
    return found


def protected_roots() -> list[Path]:
    """Directories Portage protects, resolved and deduplicated.

    ``._cfg`` files appear anywhere under these, not just in ``/etc/portage``,
    so ``cfg_apply`` is the one operation that may reach outside
    :data:`CONFIG_ROOT`. It is still the narrowest reach possible: the file has
    to be a ``._cfgNNNN_`` file, inside one of these directories, and its target
    has to sit right beside it, and the directory has to be one only root can
    write to — see :func:`_only_root_can_write`.
    """
    values: list[str] = []
    for source in CONFIG_PROTECT_SOURCES:
        try:
            values.extend(_config_protect_values(source.read_text(encoding="utf-8")))
        except OSError:
            continue
    try:
        for entry in sorted(ENV_D.iterdir()):
            if entry.is_file():
                values.extend(_config_protect_values(entry.read_text(encoding="utf-8")))
    except OSError:
        pass

    values.extend(DEFAULT_PROTECTED)

    roots: list[Path] = []
    for value in values:
        try:
            resolved = Path(value).resolve(strict=True)
        except OSError:
            continue
        if not _only_root_can_write(resolved):
            continue
        if resolved.is_dir() and resolved not in roots and resolved != Path("/"):
            roots.append(resolved)
    return roots


def check_path(
    raw: str, *, must_exist: bool = False, roots: list[Path] | None = None
) -> Path:
    """Resolve *raw* and prove it lands inside an allowed directory.

    Resolution happens before the check, so a symlink pointing out of the
    allowed area fails it — including one planted between the interface
    building the request and this process reading it.

    *roots* defaults to :data:`CONFIG_ROOT` alone. Only ``cfg_apply`` widens it,
    to the directories Portage protects, and it reads that list from root-owned
    files rather than from the request.
    """
    if not raw or not raw.startswith("/"):
        raise HelperError("relative_path", f"not an absolute path: {raw!r}")

    allowed = roots if roots is not None else [_root()]
    candidate = Path(raw)

    resolved = candidate.resolve(strict=False)
    if not any(_inside(resolved, root) for root in allowed):
        where = ", ".join(str(root) for root in allowed)
        raise HelperError("outside_root", f"{raw} resolves to {resolved}, outside {where}")

    # The parent has to exist and be inside as well: a new file is created
    # there, and a symlinked parent would put it somewhere else entirely.
    parent = resolved.parent
    if not parent.is_dir():
        raise HelperError("no_directory", f"{parent} is not a directory")
    if not any(_inside(parent.resolve(strict=True), root) for root in allowed):
        raise HelperError("outside_root", f"{parent} leads outside the allowed directories")

    if candidate.is_symlink():
        raise HelperError("symlink", f"{raw} is a symbolic link; refusing to write through it")
    if resolved.exists() and not resolved.is_file():
        raise HelperError("not_a_file", f"{resolved} is not a regular file")
    if must_exist and not resolved.exists():
        raise HelperError("missing", f"{resolved} does not exist")
    return resolved


def _require_line_target(path: Path) -> None:
    """Only the configuration files Gentstore edits one line at a time.

    Runs after :func:`check_path`, so "inside the root" is already settled and
    what is left is which file inside it. The order matters for what a refusal
    says: a symlink out of the tree is reported as a symlink, not as a file that
    happens not to be on this list.
    """
    root = _root()
    try:
        relative = path.relative_to(root)
    except ValueError as exc:  # pragma: no cover - check_path ran first
        raise HelperError("outside_root", str(path)) from exc

    name = relative.parts[0] if relative.parts else ""
    if name not in LINE_EDITABLE:
        allowed = ", ".join(LINE_EDITABLE)
        raise HelperError(
            "not_editable",
            f"line edits are limited to {allowed}; {path} is none of them",
        )

    depth = MAKE_CONF_DEPTH if name == "make.conf" else LINE_EDITABLE_DEPTH
    if len(relative.parts) > depth:
        raise HelperError(
            "not_editable", f"{path} is deeper than anything Gentstore writes"
        )


def _require_owned(path: Path) -> None:
    """Only files Gentstore creates whole may be written or deleted whole."""
    root = _root()
    try:
        relative = path.relative_to(root)
    except ValueError as exc:  # pragma: no cover - check_path ran first
        raise HelperError("outside_root", str(path)) from exc
    if not relative.parts or relative.parts[0] not in OWNED_SUBTREES:
        allowed = ", ".join(str(root / name) for name in OWNED_SUBTREES)
        raise HelperError(
            "not_owned",
            f"whole-file writes are limited to {allowed}; {path} is not there",
        )


# ---------------------------------------------------------------------------
# writing
# ---------------------------------------------------------------------------


def _preserve(path: Path) -> tuple[int, int, int]:
    """Mode, uid and gid to give the replacement of *path*."""
    try:
        info = path.stat()
    except FileNotFoundError:
        return 0o644, 0, 0
    return stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid


def atomic_write(path: Path, content: str) -> None:
    """Replace *path* with *content*, all at once or not at all.

    A temporary file in the same directory, flushed to disk, then renamed over
    the target. An interrupted write leaves the original untouched rather than
    half of a configuration file, which Portage would refuse to parse.
    """
    mode, uid, gid = _preserve(path)
    handle, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    temp_path = Path(temporary)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_path, mode)
        if os.geteuid() == 0:
            os.chown(temp_path, uid, gid)
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise

    # Also flush the directory entry, so the rename itself survives a crash.
    directory = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except OSError as exc:
        raise HelperError("unreadable", f"cannot read {path}: {exc}") from exc


def _lines(text: str) -> list[str]:
    return text.splitlines()


def _joined(lines: list[str]) -> str:
    return "".join(f"{line}\n" for line in lines)


# ---------------------------------------------------------------------------
# backups
# ---------------------------------------------------------------------------


def backup_name(now: datetime | None = None) -> str:
    stamp = (now or datetime.now()).strftime("%Y-%m-%dT%H%M")
    return f"{BACKUP_PREFIX}{stamp}"


def list_backups() -> list[Path]:
    """Existing backups, oldest first. Both forms, so neither gets orphaned."""
    try:
        entries = [
            entry
            for entry in BACKUP_PARENT.iterdir()
            if (entry.is_dir() and _BACKUP_NAME.match(entry.name))
            or (entry.is_file() and _ARCHIVE_NAME.match(entry.name))
        ]
    except OSError:
        return []
    return sorted(entries, key=lambda p: p.name)


def _prune(keep: int) -> list[str]:
    pruned = []
    existing = list_backups()
    for old in existing[: max(0, len(existing) - keep)]:
        try:
            if old.is_dir():
                shutil.rmtree(old)
            else:
                old.unlink()
            pruned.append(old.name)
        except OSError:  # pragma: no cover - a backup someone is holding open
            pass
    return pruned


def make_backup(archive: bool = False, keep: int | None = None) -> tuple[Path, list[str]]:
    """Copy the configuration root aside. Returns the copy and what was pruned.

    *archive* produces one ``.tar.gz`` instead of a directory, for people who
    would rather not have ten copies of ``/etc/portage`` sitting in ``/etc``.
    *keep* is clamped: a count that deletes the backup it just made would be
    worse than having none. ``None`` means :data:`BACKUP_KEEP` — read here and
    not as a default argument, because a module constant used as a default is
    captured when the function is defined and stops being a constant anyone can
    change.
    """
    keep = max(BACKUP_KEEP_MIN, min(BACKUP_KEEP_MAX, int(BACKUP_KEEP if keep is None else keep)))
    root = _root()
    suffix = ""
    counter = 1
    while True:
        stem = f"{backup_name()}{suffix}"
        target = BACKUP_PARENT / (f"{stem}.tar.gz" if archive else stem)
        if not target.exists():
            break
        # Two changes inside one minute; the timestamp alone is not unique.
        suffix = f"-{counter}"
        counter += 1

    try:
        if archive:
            import tarfile  # noqa: PLC0415 — only needed for this form

            with tarfile.open(target, "w:gz") as bundle:
                bundle.add(root, arcname=root.name)
        else:
            shutil.copytree(root, target, symlinks=True)
    except OSError as exc:
        raise HelperError("backup_failed", f"could not copy {root} to {target}: {exc}") from exc

    return target, _prune(keep)


def restore_backup(name: str) -> Path:
    """Put a backup back. The current state is copied aside first."""
    is_archive = bool(_ARCHIVE_NAME.match(name))
    if not is_archive and not _BACKUP_NAME.match(name):
        raise HelperError("bad_backup_name", f"{name!r} is not a Gentstore backup")
    source = BACKUP_PARENT / name
    if not (source.is_file() if is_archive else source.is_dir()):
        raise HelperError("missing", f"{source} does not exist")

    root = _root()
    make_backup()  # so that restoring is itself undoable
    staging = root.parent / f".{root.name}.restoring"
    if staging.exists():
        shutil.rmtree(staging)
    try:
        if is_archive:
            import tarfile  # noqa: PLC0415

            unpacked = root.parent / f".{root.name}.unpacking"
            if unpacked.exists():
                shutil.rmtree(unpacked)
            unpacked.mkdir()
            with tarfile.open(source, "r:gz") as bundle:
                # filter="data" refuses absolute paths, links out of the tree and
                # device nodes — an archive is the one backup form that could
                # have been written by something other than this program.
                bundle.extractall(unpacked, filter="data")
            inner = unpacked / root.name
            shutil.move(str(inner if inner.is_dir() else unpacked), str(staging))
            shutil.rmtree(unpacked, ignore_errors=True)
        else:
            shutil.copytree(source, staging, symlinks=True)
        previous = root.parent / f".{root.name}.replaced"
        if previous.exists():
            shutil.rmtree(previous)
        os.rename(root, previous)
        try:
            os.rename(staging, root)
        except OSError:
            # The one instant in which the configuration root does not exist.
            # Put it back before reporting: a restore that failed is a bad
            # afternoon, and a restore that failed *and* took /etc/portage with
            # it is an unbootable-looking machine.
            os.rename(previous, root)
            raise
        shutil.rmtree(previous)
    except OSError as exc:
        raise HelperError("restore_failed", f"could not restore {source}: {exc}") from exc
    return source


# ---------------------------------------------------------------------------
# operations
# ---------------------------------------------------------------------------


def op_append_line(request: dict[str, Any]) -> dict[str, Any]:
    path = check_path(_string(request, "path"))
    _require_line_target(path)
    line = _string(request, "line").rstrip("\n")
    if "\n" in line:
        raise HelperError("multiline", "append_line takes exactly one line")

    text = _read(path)
    lines = _lines(text)
    if line in lines:
        return {"changed": False, "detail": "the file already contains that line"}

    if text and not text.endswith("\n"):
        text += "\n"
    atomic_write(path, text + line + "\n")
    return {"changed": True, "line": line}


def op_replace_line(request: dict[str, Any]) -> dict[str, Any]:
    path = check_path(_string(request, "path"), must_exist=True)
    _require_line_target(path)
    line = _string(request, "line").rstrip("\n")
    if "\n" in line:
        # One line in, one line out. Otherwise the ``previous`` and ``line``
        # this reports back — which is what the interface shows the user as an
        # account of what happened — would describe one line where several
        # were written.
        raise HelperError("multiline", "replace_line takes exactly one line")
    pattern = _string(request, "match")
    if len(pattern) > PATTERN_MAX:
        raise HelperError(
            "bad_pattern", f"the match pattern is longer than {PATTERN_MAX} characters"
        )
    try:
        matcher = re.compile(pattern)
    except re.error as exc:
        raise HelperError("bad_pattern", f"{pattern!r} is not a valid pattern: {exc}") from exc

    lines = _lines(_read(path))
    hits = [index for index, existing in enumerate(lines) if matcher.search(existing)]
    if not hits:
        raise HelperError("no_match", f"nothing in {path} matches {pattern!r}")
    if len(hits) > 1:
        # Guessing which of several matching lines was meant is exactly the
        # kind of decision that quietly destroys somebody's make.conf.
        raise HelperError(
            "ambiguous", f"{len(hits)} lines in {path} match {pattern!r}; refusing to guess"
        )

    index = hits[0]
    if lines[index] == line:
        return {"changed": False, "detail": "the line already reads exactly that"}
    previous = lines[index]
    lines[index] = line
    atomic_write(path, _joined(lines))
    return {"changed": True, "line": line, "previous": previous, "line_number": index + 1}


def op_remove_line(request: dict[str, Any]) -> dict[str, Any]:
    path = check_path(_string(request, "path"), must_exist=True)
    _require_line_target(path)
    line = _string(request, "line").rstrip("\n")

    lines = _lines(_read(path))
    if line not in lines:
        return {"changed": False, "detail": "the file does not contain that line"}
    remaining = [existing for existing in lines if existing != line]
    atomic_write(path, _joined(remaining))
    return {"changed": True, "removed": len(lines) - len(remaining)}


def op_write_file(request: dict[str, Any]) -> dict[str, Any]:
    path = check_path(_string(request, "path"))
    _require_owned(path)
    content = _string(request, "content")
    _check_expectation(path, request)
    atomic_write(path, content)
    return {"changed": True, "bytes": len(content.encode("utf-8"))}


def op_delete_file(request: dict[str, Any]) -> dict[str, Any]:
    path = check_path(_string(request, "path"), must_exist=True)
    _require_owned(path)
    _check_expectation(path, request)
    path.unlink()
    return {"changed": True}


def op_backup(request: dict[str, Any]) -> dict[str, Any]:
    target, pruned = make_backup(
        archive=bool(request.get("archive")),
        keep=_whole_number(request, "keep"),
    )
    return {"changed": True, "backup": str(target), "pruned": pruned}


def op_restore(request: dict[str, Any]) -> dict[str, Any]:
    source = restore_backup(_string(request, "name"))
    return {"changed": True, "restored_from": str(source)}


def op_cfg_apply(request: dict[str, Any]) -> dict[str, Any]:
    """Resolve one ``._cfg0000_*`` file: take the new version or drop it.

    The only operation that writes outside ``/etc/portage``, because that is
    where Portage leaves these files. The reach is bounded three ways: the name
    must be a ``._cfgNNNN_`` one, the file must be inside a directory Portage
    protects, and the target is derived from the name rather than supplied.
    """
    candidate = check_path(
        _string(request, "path"), must_exist=True, roots=protected_roots()
    )
    if not _CFG_PREFIX.match(candidate.name):
        raise HelperError("not_a_cfg_file", f"{candidate.name} is not a ._cfgNNNN_ file")
    decision = _string(request, "decision")
    if decision not in ("accept", "reject", "merge"):
        raise HelperError("bad_decision", "decision must be 'accept', 'reject' or 'merge'")

    target = candidate.with_name(_CFG_PREFIX.sub("", candidate.name))
    if decision == "reject":
        candidate.unlink()
        return {"changed": True, "decision": decision, "target": str(target)}

    # "merge" is "accept, but with the text the user ended up with". The
    # content is written to the target rather than to the candidate, and the
    # candidate goes, so the outcome is the same shape as an accept.
    content = _string(request, "content") if decision == "merge" else _read(candidate)

    # The caller may say what it expects the target to contain — the text whose
    # diff the user actually looked at. If it does and the file has moved on
    # since, their version wins, exactly as for write_file. Optional rather than
    # required only because an older interface does not send it; a request that
    # carries it gets the stronger guarantee.
    if "expect" in request:
        _check_expectation(target, request)

    archived = _archive(target) if target.exists() else None
    atomic_write(target, content)
    candidate.unlink()
    return {
        "changed": True,
        "decision": decision,
        "target": str(target),
        "archived": str(archived) if archived else None,
        "bytes": len(content.encode("utf-8")),
    }


def _archive(path: Path) -> Path | None:
    """Keep the version being replaced, the way ``dispatch-conf`` does."""
    try:
        relative = path.relative_to("/")
        destination = CONFIG_ARCHIVE / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        kept = destination.with_name(f"{destination.name}.{stamp}")
        shutil.copy2(path, kept)
        return kept
    except OSError:  # pragma: no cover - archiving is a courtesy, not the job
        return None


OPERATIONS = {
    "append_line": op_append_line,
    "replace_line": op_replace_line,
    "remove_line": op_remove_line,
    "write_file": op_write_file,
    "delete_file": op_delete_file,
    "backup": op_backup,
    "restore": op_restore,
    "cfg_apply": op_cfg_apply,
}

#: Operations that change a file and therefore deserve a backup beforehand.
MUTATING = frozenset(
    {"append_line", "replace_line", "remove_line", "write_file", "delete_file", "cfg_apply"}
)


# ---------------------------------------------------------------------------
# request handling
# ---------------------------------------------------------------------------


def _string(request: dict[str, Any], key: str) -> str:
    value = request.get(key)
    if not isinstance(value, str):
        raise HelperError("bad_request", f"{key!r} must be a string")
    return value


def _whole_number(request: dict[str, Any], key: str) -> int | None:
    """*key* as an integer, or ``None`` when it was not sent.

    The one field that used to reach ``int()`` unchecked. A request carrying
    ``"keep": "abc"`` raised ValueError, which :func:`main` does not catch, so
    this program answered a refusal with a traceback on stderr and no JSON at
    all — the caller then had nothing to report but an exit status.
    """
    value = request.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise HelperError("bad_request", f"{key!r} must be a whole number")
    return value


def _check_expectation(path: Path, request: dict[str, Any]) -> None:
    """Refuse if the file is not what the caller thinks it is.

    ``write_file`` and ``delete_file`` replace or remove a file wholesale, so
    the caller has to say what it expects to find: the exact current contents,
    or ``null`` for "this file should not exist yet". Anything else means
    somebody edited the file in the meantime and their version wins.
    """
    if "expect" not in request:
        raise HelperError("bad_request", "'expect' is required for whole-file operations")
    expected = request["expect"]
    actual = _read(path) if path.exists() else None

    if expected is None:
        if actual is not None:
            raise HelperError("exists", f"{path} already exists")
        return
    if not isinstance(expected, str):
        raise HelperError("bad_request", "'expect' must be a string or null")
    if actual != expected:
        raise HelperError("changed_underfoot", f"{path} is not what the request expected")


def handle(request: dict[str, Any]) -> dict[str, Any]:
    """Run one request and return the response body."""
    operation = request.get("op")
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise HelperError("unknown_op", f"unknown operation: {operation!r}")

    result: dict[str, Any] = {}
    if request.get("ensure_backup") and operation in MUTATING:
        target, pruned = make_backup(
            archive=bool(request.get("archive")),
            keep=_whole_number(request, "keep"),
        )
        result["backup"] = str(target)
        if pruned:
            result["pruned"] = pruned

    result.update(OPERATIONS[operation](request))
    result.setdefault("changed", False)
    return {
        "ok": True,
        "version": PROTOCOL_VERSION,
        "op": operation,
        "path": request.get("path"),
        **result,
    }


def _identity() -> dict[str, Any]:
    """Who this process actually is — echoed back so the log can say so."""
    try:
        user = pwd.getpwuid(os.geteuid()).pw_name
        group = grp.getgrgid(os.getegid()).gr_name
    except KeyError:  # pragma: no cover - a system without those entries
        user, group = str(os.geteuid()), str(os.getegid())
    return {"euid": os.geteuid(), "user": user, "group": group}


def main(stdin=None, stdout=None) -> int:  # noqa: ANN001 - streams, injected by tests
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout

    try:
        payload = stdin.read()
    except OSError as exc:  # pragma: no cover
        print(json.dumps({"ok": False, "code": "no_input", "error": str(exc)}), file=stdout)
        return 2

    try:
        request = json.loads(payload)
        if not isinstance(request, dict):
            raise HelperError("bad_request", "the request must be a JSON object")
        response = handle(request)
    except HelperError as exc:
        response = {"ok": False, "code": exc.code, "error": str(exc)}
    except json.JSONDecodeError as exc:
        response = {"ok": False, "code": "bad_json", "error": str(exc)}
    except OSError as exc:
        response = {"ok": False, "code": "os_error", "error": str(exc)}
    except (TypeError, ValueError) as exc:
        # Nothing should reach here — every field is checked above — but this
        # process is root and its whole contract is "one JSON answer, always".
        # A traceback instead of that answer is a worse bug than whatever
        # caused it.
        response = {"ok": False, "code": "bad_request", "error": str(exc)}

    response.setdefault("version", PROTOCOL_VERSION)
    response["identity"] = _identity()
    print(json.dumps(response, ensure_ascii=False), file=stdout)
    stdout.flush()
    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
