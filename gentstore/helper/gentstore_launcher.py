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

"""Run one Portage command as root, stream it back, and be able to stop it.

    gentstore-launcher emerge --verbose --oneshot =app-misc/hello-2.12

Three things this does that plain ``pkexec emerge …`` does not.

**It bounds what can be run.** Not just *which program* — which command. Only
the handful of programs Gentstore drives, looked up in a fixed list of
directories rather than through ``PATH`` (under ``sudo`` the caller controls
part of the environment), and then only the command lines Gentstore actually
builds: a table of whole commands, with arguments that have to look like
package atoms, repository names or advisory numbers.

A table rather than a set of permitted options, because a set permits every
combination of its members. ``--unmerge`` and ``@world`` were both on the old
list and neither was wrong on its own; together they are a command that removes
the system.

That second half is the point. ``emerge`` with arbitrary options is root by
another name — ``--config`` runs a package's own configuration script,
``--root`` moves the whole operation somewhere else — and the authentication
dialog promised "install and update packages". Anything running as the user can
reach this program, and a dialog says only as much as the action it names, so
what is found here has to be worth no more than what the dialog said.

**It can be stopped.** The interface runs unprivileged, so it cannot signal a
root process at all. Instead it writes ``abort`` on this program's standard
input; the signal is then sent from in here, where it is allowed:
``SIGINT`` first — the same thing Ctrl+C does in a terminal, which lets
``emerge`` unwind cleanly — and ``SIGTERM`` ten seconds later if that was
ignored. Never ``SIGKILL``: killing ``emerge`` mid-merge can leave the package
database inconsistent.

**It keeps the child out of the control channel.** The child gets
``/dev/null`` on standard input, so it can neither eat the abort message nor
sit waiting for an answer nobody can give it.

Standard library only, no imports from the rest of Gentstore.
"""

from __future__ import annotations

import contextlib
import os
import pwd
import re
import signal
import subprocess
import sys
import threading
from pathlib import Path

#: The only programs this may start.
#:
#: ``dispatch-conf`` and ``etc-update`` are deliberately not here: they are
#: interactive, they spawn an editor, and Gentstore resolves ``._cfg`` files
#: through the helper's ``cfg_apply`` instead. Nothing in the interface asks for
#: them, so allowing them would only widen what this program can be talked into.
ALLOWED = frozenset({"emerge", "emaint", "eselect", "glsa-check"})

#: Where to look for them. Not ``PATH``: under the ``sudo`` fallback the caller
#: has a say in the environment, and ``PATH`` is the obvious thing to bend.
SEARCH_PATH = (Path("/usr/bin"), Path("/bin"), Path("/usr/sbin"), Path("/sbin"))

#: How long a polite SIGINT is given before SIGTERM follows.
GRACE_SECONDS = 10

ABORT_WORD = "abort"


class LauncherError(Exception):
    """Refusal to start something."""


def resolve(program: str) -> Path:
    """Find *program* in the fixed search path, or refuse."""
    if "/" in program:
        raise LauncherError(f"expected a program name, not a path: {program!r}")
    if program not in ALLOWED:
        raise LauncherError(
            f"{program!r} is not one of the programs Gentstore runs "
            f"({', '.join(sorted(ALLOWED))})"
        )
    for directory in SEARCH_PATH:
        candidate = directory / program
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise LauncherError(f"{program} is not installed")


# ---------------------------------------------------------------------------
# what each program may be asked to do
# ---------------------------------------------------------------------------
#
# Every command line below appears in gentstore/runner/emerge.py or
# gentstore/runner/eselect.py. Adding a command to the interface means adding it
# here too, on purpose: this file is the list of what one authentication buys.

#: ``media-video/mpv``, ``=media-video/mpv-0.41.0-r2``, ``media-video/*``.
#:
#: Not a full Portage atom parser — this file stays standard-library only and
#: readable in one sitting. It is a shape check, and the shape is what matters:
#: a category, a slash, a package, and nothing that could be read as an option
#: or as a path to something on disk.
_ATOM = re.compile(
    r"^(?:!!?)?"  # blocker
    r"(?:[<>]=?|=|~)?"  # version operator
    r"(?:\*|[A-Za-z0-9][A-Za-z0-9+_.-]*)"  # category
    r"/"
    r"(?:\*|[A-Za-z0-9][A-Za-z0-9+_.-]*)"  # package, version and revision
    r"\*?"  # =cat/pkg-1.2*
    r"(?::[A-Za-z0-9+_.*/-]+)?"  # :slot, :slot/sub, :*
    r"(?:::[A-Za-z0-9][A-Za-z0-9+_.-]*)?"  # ::repository
    r"(?:\[[A-Za-z0-9+_@,=!?*-]+\])?"  # [use,flags]
    r"$"
)

#: ``emerge`` reads an argument ending in one of these as a file to merge, which
#: would be a way to hand it something the user never chose.
_PACKAGE_SUFFIXES = (".ebuild", ".tbz2", ".xpak", ".gpkg", ".gpkg.tar")

#: The same convention ``gentstore/core/overlays.py`` validates against.
_REPOSITORY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_+.-]*$")

#: Sync backends ``eselect repository add`` understands.
_SYNC_TYPES = frozenset({"git", "rsync", "svn", "mercurial", "cvs", "bzr", "darcs"})

#: A URL with a scheme we are willing to hand to git, or ``user@host:path``.
#:
#: The scheme is checked against a list rather than for the presence of "://",
#: because git reads ``ext::sh -c '…'`` as "run this command" — and that string
#: contains "://" quite happily if you put one at the end of it.
#:
#: The same list as ``_SCHEME`` in gentstore/core/overlays.py, and it has to
#: stay that way: the "Add overlay" dialog validates against that one and this
#: file decides whether the command it built may run. When ``svn`` was in the
#: first list and not in this one, the dialog enabled its OK button for an
#: svn:// overlay and the launcher then refused the command it had just
#: promised — an error nobody could act on.
_URI = re.compile(r"^(?:https?|git|ssh|rsync|svn|file)://[^\s]+$")
_SCP_URI = re.compile(r"^[A-Za-z0-9._-]+@[A-Za-z0-9._-]+:[^\s:]+$")

#: ``202501-15``, or the word ``affected``.
_ADVISORY = re.compile(r"^\d{6,8}-\d{2}$")

#: ``eselect profile set 7``.
_INDEX = re.compile(r"^\d{1,4}$")


def _is_everything(token: str) -> bool:
    """``*/*`` — every package there is — however it is dressed up.

    The atom shape above allows a wildcard in either half, and both at once is
    still a valid atom, so ``emerge --unmerge --color=n '*/*'`` used to pass
    every other check in this file. That is the whole system, and the dialog
    said "install, update or remove packages", and anything running as the user
    can ask this program for a command. Nothing here needs it — the one place
    Gentstore
    writes ``*/*`` is ``*/*::<overlay>`` into ``package.mask``, and that goes
    to the helper and never reaches this program.

    Kept as its own check even though :data:`EMERGE_COMMANDS` now decides which
    commands exist at all: every row that ends in atoms would otherwise take
    this one.

    Matched on the package name alone, so an operator, a slot, a repository or
    a USE list cannot smuggle it past.
    """
    body = token.lstrip("!<>=~")
    body = body.partition("::")[0].partition("[")[0].partition(":")[0]
    return body == "*/*"


def _is_package_atom(token: str) -> bool:
    """One package, and never a set.

    ``@world`` and ``@preserved-rebuild`` are literals in the two rows of
    :data:`EMERGE_COMMANDS` that take one, so they arrive here only where they
    were never meant to — as the thing to unmerge, most of all. ``emerge
    --unmerge @world`` is a command that removes the system, and the interface
    has no button for it.
    """
    if token.endswith(_PACKAGE_SUFFIXES) or _is_everything(token):
        return False
    return bool(_ATOM.match(token))


def _is_repository(token: str) -> bool:
    return bool(_REPOSITORY.match(token))


def _is_sync_type(token: str) -> bool:
    return token in _SYNC_TYPES


def _is_uri(token: str) -> bool:
    return bool(_URI.match(token) or _SCP_URI.match(token))


def _is_index(token: str) -> bool:
    return bool(_INDEX.match(token))


#: Placeholders in the tables below. Strings, so that a table reads as the
#: command it stands for; angle brackets, so they cannot collide with a literal.
REPOSITORY, SYNC_TYPE, URI, INDEX = "<repository>", "<sync-type>", "<uri>", "<index>"

#: One or more package atoms, and only ever at the end of a row.
ATOMS = "<atoms>"

_VALIDATORS = {
    REPOSITORY: _is_repository,
    SYNC_TYPE: _is_sync_type,
    URI: _is_uri,
    INDEX: _is_index,
}

#: ``eselect`` is a program with modules; only these three, and only this much
#: of them.
ESELECT_COMMANDS = (
    ("repository", "list"),
    ("repository", "enable", REPOSITORY),
    ("repository", "add", REPOSITORY, SYNC_TYPE, URI),
    ("repository", "disable", REPOSITORY),
    ("repository", "disable", "-f", REPOSITORY),
    ("repository", "remove", REPOSITORY),
    ("repository", "remove", "-f", REPOSITORY),
    ("news", "read"),
    ("profile", "list"),
    ("profile", "set", INDEX),
)

EMAINT_COMMANDS = (
    ("sync", "-a"),
    ("sync", "-r", REPOSITORY),
)

#: The two options on every command ``gentstore/runner/emerge.py`` builds, in
#: the order that file puts them in.
_EMERGE_BASE = ("--color=n", "--nospinner")

#: Every ``emerge`` command line Gentstore builds — one row per function in
#: gentstore/runner/emerge.py, in that file's order.
#:
#: Whole commands, not a set of permitted options. A set permits every
#: combination of its members and the interface builds eleven of them; the ones
#: it does not build include ``--unmerge @world``, ``--depclean`` with a package
#: named beside it, and ``--getbinpkg`` on a removal. ``emerge`` accepts all
#: three, and this program is the boundary that decides what one authentication
#: buys — so it is the one that has to be narrower than ``emerge``.
#:
#: A trailing ``?`` marks an option that may or may not be there: the two the
#: interface decides at the point of use, ``--getbinpkg`` and ``--oneshot``.
#: :data:`ATOMS` stands for one or more package atoms and may only end a row.
#: The two commands that operate on a set name it literally, which is what makes
#: a set unreachable everywhere else.
EMERGE_COMMANDS = (
    # pretend(), which the interface runs unprivileged — a preview changes
    # nothing, and being in this table costs nothing but says what it is.
    (*_EMERGE_BASE, "--pretend", "--verbose", "--oneshot?", ATOMS),
    # install()
    (*_EMERGE_BASE, "--verbose", "--getbinpkg?", "--oneshot?", ATOMS),
    # unmerge_pretend()
    (*_EMERGE_BASE, "--pretend", "--verbose", "--unmerge", ATOMS),
    # unmerge()
    (*_EMERGE_BASE, "--unmerge", ATOMS),
    # deselect()
    (*_EMERGE_BASE, "--deselect", ATOMS),
    # select()
    (*_EMERGE_BASE, "--select", "--noreplace", ATOMS),
    # update_world_pretend()
    (
        *_EMERGE_BASE,
        "--pretend",
        "--verbose",
        "--update",
        "--deep",
        "--newuse",
        "--changed-use",
        "--getbinpkg?",
        "@world",
    ),
    # update_world()
    (
        *_EMERGE_BASE,
        "--verbose",
        "--update",
        "--deep",
        "--newuse",
        "--getbinpkg?",
        "@world",
    ),
    # depclean_pretend()
    (*_EMERGE_BASE, "--pretend", "--depclean"),
    # depclean(): it works out for itself what is orphaned, and is given
    # nothing. A package beside it means something else entirely.
    (*_EMERGE_BASE, "--depclean"),
    # preserved_rebuild()
    (*_EMERGE_BASE, "--verbose", "@preserved-rebuild"),
)


def _matches(template: tuple[str, ...], arguments: list[str]) -> bool:
    """Whether *arguments* is the command *template* describes.

    Three kinds of entry: a literal, which has to be there exactly; a literal
    with a ``?`` after it, which may be skipped; and a placeholder, which is
    checked by shape. :data:`ATOMS` ends a row and takes everything left, which
    has to be at least one package and nothing but packages.
    """
    position = 0
    for item in template:
        if item == ATOMS:
            rest = arguments[position:]
            return bool(rest) and all(_is_package_atom(token) for token in rest)

        optional = item.endswith("?")
        expected = item[:-1] if optional else item
        if position >= len(arguments):
            if optional:
                continue
            return False

        actual = arguments[position]
        validator = _VALIDATORS.get(expected)
        if validator is not None:
            if not validator(actual):
                return False
        elif expected != actual:
            if optional:
                continue
            return False
        position += 1
    return position == len(arguments)


def _check_against(
    program: str, commands: tuple[tuple[str, ...], ...], arguments: list[str]
) -> None:
    if not any(_matches(template, arguments) for template in commands):
        line = " ".join([program, *arguments])
        raise LauncherError(f"not a command Gentstore runs: {line!r}")


def _check_glsa_check(arguments: list[str]) -> None:
    if not arguments or arguments[0] not in ("-l", "-f"):
        raise LauncherError("glsa-check takes -l or -f")
    rest = arguments[1:]
    if not rest:
        raise LauncherError("glsa-check was given nothing to look at")
    for argument in rest:
        if argument != "affected" and not _ADVISORY.match(argument):
            raise LauncherError(f"not a GLSA identifier: {argument!r}")


_CHECKERS = {
    "emerge": lambda arguments: _check_against("emerge", EMERGE_COMMANDS, arguments),
    "emaint": lambda arguments: _check_against("emaint", EMAINT_COMMANDS, arguments),
    "eselect": lambda arguments: _check_against("eselect", ESELECT_COMMANDS, arguments),
    "glsa-check": _check_glsa_check,
}


def check_arguments(program: str, arguments: list[str]) -> None:
    """Refuse anything but the command lines Gentstore itself builds.

    *program* has already been through :func:`resolve`, so it is one of
    :data:`ALLOWED`; this is the second half of the same question.
    """
    _CHECKERS[program](arguments)


def child_environment() -> dict[str, str]:
    """A clean environment for the child.

    ``PYTHONUNBUFFERED`` matters more than it looks: ``emerge`` is a Python
    program, and writing to a pipe it would otherwise buffer its output in
    kilobyte blocks — the log in the window would sit empty and then jump,
    instead of scrolling the way it does in a terminal.
    """
    environment = {
        "PATH": ":".join(str(directory) for directory in SEARCH_PATH),
        # In production this is always root's home. Reading it rather than
        # writing "/root" keeps the program runnable — and therefore
        # testable — without privileges.
        "HOME": _home(),
        "TERM": "dumb",
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "PYTHONUNBUFFERED": "1",
        "NOCOLOR": "true",
    }
    return environment


def _home() -> str:
    try:
        return pwd.getpwuid(os.geteuid()).pw_dir
    except KeyError:  # pragma: no cover - a system without that passwd entry
        return "/root"


def watch_for_abort(process: subprocess.Popen, stream=None) -> None:  # noqa: ANN001
    """Turn ``abort`` on standard input into signals for the child's group.

    Runs on its own thread for as long as the child does. End of input counts
    as an abort too: if the interface died, the build it started should not
    outlive it unattended.
    """
    stream = stream or sys.stdin
    try:
        for raw in stream:
            if raw.strip().lower() == ABORT_WORD:
                break
        # Falling out of the loop means end of input, which is also a reason
        # to stop — hence no separate branch here.
    except (OSError, ValueError):  # pragma: no cover - stdin closed under us
        pass

    if process.poll() is not None:
        return
    _stop(process)


def _stop(process: subprocess.Popen) -> None:
    try:
        group = os.getpgid(process.pid)
    except OSError:  # pragma: no cover - it exited between the checks
        return

    try:
        os.killpg(group, signal.SIGINT)
    except OSError:  # pragma: no cover
        return

    try:
        process.wait(timeout=GRACE_SECONDS)
        return
    except subprocess.TimeoutExpired:
        pass

    with contextlib.suppress(OSError):  # pragma: no cover - it exited first
        os.killpg(group, signal.SIGTERM)
    # Deliberately no SIGKILL, however long this takes.


def run(argv: list[str]) -> int:
    program = resolve(argv[0])
    check_arguments(argv[0], argv[1:])
    process = subprocess.Popen(  # noqa: S603 - argv is checked above, in full
        [str(program), *argv[1:]],
        stdin=subprocess.DEVNULL,
        env=child_environment(),
        # Its own process group, so the abort reaches the whole build and not
        # just the top-level emerge.
        start_new_session=True,
    )
    watcher = threading.Thread(target=watch_for_abort, args=(process,), daemon=True)
    watcher.start()
    return process.wait()


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        print("usage: gentstore-launcher <program> [arguments…]", file=sys.stderr)
        return 2
    try:
        return run(arguments)
    except LauncherError as exc:
        print(f"gentstore-launcher: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:  # pragma: no cover - the program vanished mid-start
        print(f"gentstore-launcher: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
