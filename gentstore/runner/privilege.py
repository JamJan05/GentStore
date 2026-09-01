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

"""Deciding how to become root, and where the two privileged programs live.

Order of preference is ``pkexec`` and then ``sudo``. ``pkexec`` is the one the
project is built around: it puts up a graphical authentication dialog that names
the action (see ``data/org.gentoo.gentstore.policy``), it does not depend on the
user being in a particular group, and it leaves an audit trail.

``sudo`` is the fallback for systems without polkit. It needs either a terminal
or ``SUDO_ASKPASS``, and when neither is there the application says so instead
of appearing to do nothing.
"""

from __future__ import annotations

import logging
import os
import shutil
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

#: Where ``make install`` puts the two privileged programs.
INSTALL_DIR = Path("/usr/libexec/gentstore")
HELPER_NAME = "gentstore-helper"
LAUNCHER_NAME = "gentstore-launcher"

#: The same two programs inside a source checkout, for running from the tree.
_SOURCE_DIR = Path(__file__).resolve().parent.parent / "helper"
_SOURCE_HELPER = _SOURCE_DIR / "gentstore_helper.py"
_SOURCE_LAUNCHER = _SOURCE_DIR / "gentstore_launcher.py"


@dataclass(frozen=True, slots=True)
class Escalation:
    """How this system raises privileges."""

    #: ``pkexec``, ``sudo``, ``direct`` (already root) or ``none``.
    kind: str
    program: str | None
    #: Why it will not work, when it will not; ``None`` when it will.
    problem: str | None = None

    @property
    def is_available(self) -> bool:
        if self.problem is not None:
            return False
        return self.kind == "direct" or self.program is not None

    def wrap(self, argv: tuple[str, ...]) -> tuple[str, ...]:
        """Put *argv* behind whatever this system uses to become root."""
        if self.kind == "direct" or self.program is None:
            return argv
        if self.kind == "sudo":
            # --non-interactive would fail rather than prompt; -A uses
            # SUDO_ASKPASS, which is the only way to ask from a GUI.
            flags = ("-A",) if os.environ.get("SUDO_ASKPASS") else ()
            return (self.program, *flags, *argv)
        return (self.program, *argv)


def _sudo_problem() -> str | None:
    if os.environ.get("SUDO_ASKPASS"):
        return None
    if sys.stdin is not None and sys.stdin.isatty():
        return None
    return (
        "sudo has no way to ask for the password: there is no terminal and "
        "SUDO_ASKPASS is not set. Install polkit (sys-auth/polkit) or set "
        "SUDO_ASKPASS to a password prompt program."
    )


#: Set once at start-up from the user's preference. A module-level value rather
#: than a parameter because every caller of detect() would otherwise have to
#: thread a setting through code that has no other reason to know about it.
preferred: str = "auto"


def detect() -> Escalation:
    """Work out how to become root on this machine.

    Honours :data:`preferred`, but never invents a program that is not there:
    asking for ``sudo`` on a system without it still reports that nothing is
    available rather than failing later with a confusing message.
    """
    if os.geteuid() == 0:
        # Running the whole application as root is a bad idea and Gentstore
        # says so at start-up, but if somebody does it anyway the privileged
        # operations should simply work rather than ask for a password that
        # would change nothing.
        return Escalation("direct", None)

    pkexec = shutil.which("pkexec")
    sudo = shutil.which("sudo")

    if preferred == "sudo" and sudo:
        return Escalation("sudo", sudo, _sudo_problem())
    if preferred == "pkexec" and pkexec:
        return Escalation("pkexec", pkexec)

    if pkexec:
        return Escalation("pkexec", pkexec)
    if sudo:
        return Escalation("sudo", sudo, _sudo_problem())

    return Escalation(
        "none",
        None,
        "neither pkexec nor sudo is installed, so nothing can be run as root",
    )


@dataclass(frozen=True, slots=True)
class PrivilegedProgram:
    """One of the two installed programs, and how to invoke it."""

    argv: tuple[str, ...]
    installed: bool

    @property
    def is_development_copy(self) -> bool:
        """Running from the source tree rather than from ``/usr/libexec``.

        Everything still works, but polkit has no action registered for the
        path, so the authentication dialog shows the generic "run a program as
        another user" wording instead of naming what is about to happen.
        """
        return not self.installed


#: Set to ``1`` to allow the copies in the source tree to be run as root.
#:
#: Off by default, and the default is the security-relevant part. In a checkout
#: the two privileged programs are files the ordinary user can write, and the
#: fallback hands one of them to ``pkexec`` as an argument to ``python3``.
#: pkexec checks that *python3* belongs to root; about the script it is given it
#: has nothing to say. So anything able to write into the checkout — a second
#: account with access, an editor plugin, a dependency installed with ``-e`` —
#: would be one authentication away from root, and the dialog the user sees
#: would be the generic "run a program as another user" one, because polkit has
#: no action registered for that path either.
#:
#: ``sudo make install-system`` is a one-off and is what the documentation has
#: always told people to run. This variable is for the inner development loop,
#: where the risk is understood and the alternative is reinstalling after every
#: edit.
DEV_VARIABLE = "GENTSTORE_DEV_HELPER"


def _tampering_risk(path: Path) -> str | None:
    """Why *path* is not safe to run as root, or ``None`` when it is.

    Group- or world-writable anywhere from the file up to ``/`` means somebody
    other than its owner can decide what root ends up executing. A directory is
    enough: whoever can write one can replace the file inside it.

    Except a sticky one. ``/tmp`` is writable by everybody and always has been;
    the sticky bit is what stops one user from renaming another user's file out
    of the way, which is exactly the move this is looking for. The file itself
    still has to be the owner's alone.
    """
    try:
        mode = path.stat().st_mode
    except OSError as exc:  # pragma: no cover - it vanished mid-check
        return f"{path} cannot be read: {exc}"
    if mode & (stat.S_IWGRP | stat.S_IWOTH):
        return f"{path} is writable by users other than its owner"

    for parent in path.parents:
        try:
            mode = parent.stat().st_mode
        except OSError as exc:  # pragma: no cover
            return f"{parent} cannot be read: {exc}"
        if mode & (stat.S_IWGRP | stat.S_IWOTH) and not mode & stat.S_ISVTX:
            return f"{parent} is writable by users other than its owner"
    return None


def _locate(installed_name: str, source: Path) -> PrivilegedProgram | None:
    installed = INSTALL_DIR / installed_name
    if installed.is_file() and os.access(installed, os.X_OK):
        return PrivilegedProgram((str(installed),), installed=True)
    if not source.is_file():
        return None

    if os.environ.get(DEV_VARIABLE) != "1":
        log.warning(
            "%s is not installed in %s. Run `sudo make install-system`. "
            "(Setting %s=1 runs the copy in the source tree as root instead, "
            "which is only sensible on a machine you are developing on.)",
            installed_name,
            INSTALL_DIR,
            DEV_VARIABLE,
        )
        return None

    risk = _tampering_risk(source)
    if risk is not None:
        log.error("Refusing to run %s as root: %s", source, risk)
        return None

    log.warning(
        "%s is set: running the in-tree %s as root. Not a thing to leave on.",
        DEV_VARIABLE,
        installed_name,
    )
    return PrivilegedProgram((sys.executable, str(source)), installed=False)


@dataclass(frozen=True, slots=True)
class InstalledStatus:
    """Whether an installed privileged program matches the one in the tree."""

    name: str
    installed: bool
    #: ``True`` when the installed copy is byte-for-byte the source's.
    current: bool
    path: Path | None = None

    @property
    def is_stale(self) -> bool:
        """Installed, but from an older version of Gentstore.

        Worth knowing about because the two halves are versioned together: an
        interface that offers an operation the installed helper has never heard
        of produces a refusal that makes no sense to read.
        """
        return self.installed and not self.current


_INSTALLED: dict[str, InstalledStatus] = {}
#: What the installed file was when its status was worked out, so that the
#: memo above can tell it has since been replaced.
_STAMPS: dict[str, tuple[int, int, int, int] | None] = {}

_PROGRAMS = {HELPER_NAME: _SOURCE_HELPER, LAUNCHER_NAME: _SOURCE_LAUNCHER}


def _stamp(path: Path) -> tuple[int, int, int, int] | None:
    """Enough of *path* to notice it being replaced, without reading it.

    The device and inode because ``install`` puts a new file there rather than
    editing the old one; the timestamp and the size because a file can be
    replaced in place too, and neither of those survives it.
    """
    try:
        info = path.stat()
    except OSError:
        return None
    return (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size)


def installed_status(name: str, *, refresh: bool = False) -> InstalledStatus:
    """Compare the installed copy of *name* with the source it came from.

    The answer is remembered, but only for as long as the file it describes has
    not moved. Without that the memo outlived its subject, and in the one way
    that mattered: the interface said "the installed helper is from an older
    version, run `sudo make install-system`", somebody ran it, and every refusal
    for the rest of the session went on telling them to. A stat per call is
    what buys the difference, against a full read of both files on a miss.
    """
    source = _PROGRAMS.get(name)
    installed = INSTALL_DIR / name
    stamp = _stamp(installed)
    if not refresh and name in _INSTALLED and _STAMPS.get(name) == stamp:
        return _INSTALLED[name]

    status = InstalledStatus(name=name, installed=installed.is_file(), current=True)

    if status.installed and source is not None:
        try:
            same = installed.read_bytes() == source.read_bytes()
        except OSError:  # pragma: no cover - unreadable while being replaced
            same = True
        status = InstalledStatus(
            name=name, installed=True, current=same, path=installed
        )

    _INSTALLED[name] = status
    _STAMPS[name] = stamp
    return status


def stale_programs(*, refresh: bool = False) -> tuple[InstalledStatus, ...]:
    """Installed programs that no longer match this version of Gentstore."""
    return tuple(
        status
        for status in (installed_status(name, refresh=refresh) for name in _PROGRAMS)
        if status.is_stale
    )


def helper_command() -> PrivilegedProgram | None:
    """The configuration-writing helper, or ``None`` if it is not there."""
    return _locate(HELPER_NAME, _SOURCE_HELPER)


def launcher_command() -> PrivilegedProgram | None:
    """The command launcher, or ``None`` if it is not there."""
    return _locate(LAUNCHER_NAME, _SOURCE_LAUNCHER)
