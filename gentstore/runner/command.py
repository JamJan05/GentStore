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

"""Running one system command and streaming its output into the window.

The interesting part is stopping one. Gentstore's process is never root, so it
cannot signal a build running as root — the kernel will not let it. Instead the
privileged runs go through ``gentstore-launcher``, which reads ``abort`` on its
standard input and sends the signal from where it is allowed. Unprivileged runs
are our own children and are signalled directly.

Either way the sequence is the one from Docs/04-privileges.md §7: ``SIGINT``
first, ``SIGTERM`` ten seconds later, ``SIGKILL`` never.
"""

from __future__ import annotations

import logging
import os
import signal
from dataclasses import dataclass, field

from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, pyqtSignal

from . import privilege

log = logging.getLogger(__name__)

#: How long a SIGINT is given before SIGTERM follows, for our own children.
#: The launcher applies the same delay to the privileged ones.
GRACE_MS = 10_000

#: Terminals overwrite the current line on a carriage return; a log widget
#: cannot, so only the text after the last one is kept.
_CARRIAGE_RETURN = "\r"


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """One command to run, and how to describe it to the user."""

    argv: tuple[str, ...]
    #: Whether this has to run as root.
    privileged: bool = False
    #: Short human-readable purpose, e.g. "Installing media-video/mpv".
    description: str = ""
    #: Extra environment for unprivileged runs. Privileged runs get the
    #: launcher's own clean environment instead.
    environment: dict[str, str] = field(default_factory=dict)

    @property
    def display(self) -> str:
        """The command as somebody would type it, for the log header."""
        return " ".join(self.argv)


class CommandError(RuntimeError):
    """The command could not be started at all."""


class Command(QObject):
    """Runs one :class:`CommandSpec` at a time and reports on it.

    One instance can be reused for command after command; starting a second one
    while the first is running is refused rather than queued, because the
    interface should not be able to run two ``emerge`` processes at once.
    """

    #: One complete line of output, control characters already dealt with.
    output = pyqtSignal(str)
    #: The command actually started; the payload is the :class:`CommandSpec`.
    started = pyqtSignal(object)
    #: Exit code. ``finished`` fires for a failed command too — a non-zero
    #: ``emerge`` is a normal outcome the user needs to read, not an error here.
    finished = pyqtSignal(int)
    #: The command could not be started, or died on a signal; the payload is a
    #: message meant for the log.
    failed = pyqtSignal(str)
    #: ``True`` while a command is running.
    running_changed = pyqtSignal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._spec: CommandSpec | None = None
        self._buffer = ""
        self._aborting = False
        self._escalate = QTimer(self)
        self._escalate.setSingleShot(True)
        self._escalate.setInterval(GRACE_MS)
        self._escalate.timeout.connect(self._send_sigterm)

    # -- state -------------------------------------------------------------

    def is_running(self) -> bool:
        return self._process is not None

    @property
    def spec(self) -> CommandSpec | None:
        return self._spec

    # -- starting ----------------------------------------------------------

    def start(self, spec: CommandSpec) -> None:
        """Run *spec*. Raises :class:`CommandError` if it cannot even begin."""
        if self.is_running():
            raise CommandError("another command is still running")

        argv = self._resolve(spec)
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(self._read)
        process.finished.connect(self._on_finished)
        process.errorOccurred.connect(self._on_error)

        if not spec.privileged:
            self._configure_unprivileged(process, spec)

        self._process = process
        self._spec = spec
        self._buffer = ""
        self._aborting = False

        log.info("Running: %s", " ".join(argv))
        process.start(argv[0], list(argv[1:]))
        self.running_changed.emit(True)
        self.started.emit(spec)

    def _resolve(self, spec: CommandSpec) -> tuple[str, ...]:
        if not spec.privileged:
            return spec.argv

        escalation = privilege.detect()
        if not escalation.is_available:
            raise CommandError(escalation.problem or "cannot become root on this system")
        launcher = privilege.launcher_command()
        if launcher is None:
            raise CommandError(
                f"{privilege.LAUNCHER_NAME} is not installed in {privilege.INSTALL_DIR}. "
                f"Run `sudo make install-system`."
            )
        return escalation.wrap((*launcher.argv, *spec.argv))

    def _configure_unprivileged(self, process: QProcess, spec: CommandSpec) -> None:
        # systemEnvironment(), not process.processEnvironment(): a fresh QProcess
        # reports an *empty* environment, and setting that one back would hand
        # the child no PATH at all. Portage notices immediately and starts
        # complaining that bzip2 and zstd are missing.
        environment = QProcessEnvironment.systemEnvironment()
        # emerge is a Python program: writing to a pipe it would buffer its
        # output in blocks, and the log would sit empty and then jump.
        environment.insert("PYTHONUNBUFFERED", "1")
        environment.insert("NOCOLOR", "true")
        for key, value in spec.environment.items():
            environment.insert(key, value)
        process.setProcessEnvironment(environment)

        # Its own session, so an abort reaches the whole process tree rather
        # than just the program we started — and never our own process.
        parameters = QProcess.UnixProcessParameters()
        parameters.flags = QProcess.UnixProcessFlag.CreateNewSession
        process.setUnixProcessParameters(parameters)

    # -- output ------------------------------------------------------------

    def _read(self) -> None:
        if self._process is None:
            return
        chunk = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._buffer += chunk
        *complete, self._buffer = self._buffer.split("\n")
        for line in complete:
            self.output.emit(line.rsplit(_CARRIAGE_RETURN, 1)[-1])

    def _flush(self) -> None:
        if self._buffer:
            self.output.emit(self._buffer.rsplit(_CARRIAGE_RETURN, 1)[-1])
            self._buffer = ""

    # -- stopping ----------------------------------------------------------

    def abort(self) -> None:
        """Ask the command to stop, the way Ctrl+C would."""
        if self._process is None or self._aborting:
            return
        self._aborting = True

        if self._spec is not None and self._spec.privileged:
            # The child runs as root; we may not signal it. The launcher can,
            # and it is listening on its own standard input for exactly this.
            self._process.write(b"abort\n")
            log.info("Asked the launcher to stop the command")
            return

        pid = self._process.processId()
        if pid <= 0:  # pragma: no cover - it exited between the checks
            return
        try:
            os.killpg(os.getpgid(pid), signal.SIGINT)
        except OSError as exc:  # pragma: no cover - it exited between the checks
            log.debug("Could not interrupt %s: %s", pid, exc)
            return
        self._escalate.start()

    def _send_sigterm(self) -> None:
        """SIGINT was ignored. Escalate once — and never to SIGKILL."""
        if self._process is None:
            return
        pid = self._process.processId()
        if pid <= 0:
            return
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            log.warning("The command ignored SIGINT; sent SIGTERM")
        except OSError:  # pragma: no cover
            pass

    def close(self) -> None:
        """Stop whatever is running and let go of it.

        Called when the window closes, and by anything that owns a
        :class:`Command` and is about to go away. Without it the ``QProcess``
        is destroyed with a child still attached and its ``finished`` signal
        arrives at an object that no longer exists — which is not an error Qt
        can report, it is a crash.
        """
        process = self._process
        if process is None:
            return
        self.abort()
        # Long enough for a SIGINT to be noticed, short enough not to hang a
        # window that the user has asked to close.
        process.waitForFinished(3000)
        try:
            process.readyReadStandardOutput.disconnect()
            process.finished.disconnect()
            process.errorOccurred.disconnect()
        except TypeError:  # pragma: no cover - already disconnected
            pass
        # Through _teardown rather than by hand: it also schedules the QProcess
        # for deletion and says that nothing is running any more, and a second
        # copy of that sequence is a second copy to keep in step.
        self._teardown()

    # -- finishing ---------------------------------------------------------

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error != QProcess.ProcessError.FailedToStart:
            # Crashes arrive through finished() as well, with the exit status;
            # reporting them twice would put two errors in the log.
            return
        self._teardown()
        self.failed.emit(self.tr("The command could not be started."))

    def _on_finished(self, code: int, status: QProcess.ExitStatus) -> None:
        self._read()
        self._flush()
        aborted = self._aborting
        self._teardown()

        if aborted:
            self.failed.emit(self.tr("Stopped at your request."))
        elif status == QProcess.ExitStatus.CrashExit:
            self.failed.emit(self.tr("The command was terminated by a signal."))
        else:
            self.finished.emit(code)

    def _teardown(self) -> None:
        self._escalate.stop()
        if self._process is not None:
            self._process.deleteLater()
        self._process = None
        self.running_changed.emit(False)
