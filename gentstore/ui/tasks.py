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

"""Running blocking work off the GUI thread.

The rule from Docs/01-architecture.md: everything under ``gentstore/core`` is
plain synchronous Python that knows nothing about threads. This module is the
single seam where that code gets handed to a worker, so a Portage call can never
freeze the window.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

log = logging.getLogger(__name__)


class _Signals(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(object)


class ProgressReporter(QObject):
    """A progress channel handed *into* a ``core`` function.

    Long reads — building the search index over twenty thousand packages, above
    all — take long enough that the window has to say so. Rather than teaching
    ``core`` about Qt, the caller creates a reporter and passes its
    :meth:`report` as an ordinary callable::

        self._reporter = ProgressReporter()
        self._reporter.progress.connect(self._show_progress)
        run_async(SearchIndex.build, self._loaded, self._failed,
                  None, self._reporter.report)

    :meth:`report` is called from the worker thread; because the reporter itself
    lives in the GUI thread, Qt queues the signal and the slot runs where it is
    safe to touch widgets. Keep a reference to the reporter for as long as the
    task runs — a garbage-collected one silently stops reporting.
    """

    progress = pyqtSignal(int, int)

    def report(self, done: int, total: int) -> None:
        """Emit progress. Safe to call from any thread; never raises."""
        try:
            self.progress.emit(done, total)
        except RuntimeError:  # pragma: no cover - shutdown race
            log.debug("Progress update dropped: the reporter was already destroyed")


#: Tasks that have been started but have not delivered their result yet.
#: Without this, nothing would hold a Python reference to a running task and the
#: garbage collector could destroy its signal object before the queued signal is
#: delivered to the GUI thread — the result would simply never arrive.
_pending: set[Task] = set()


class Task(QRunnable):
    """Run ``fn(*args, **kwargs)`` in the global thread pool.

    Connect to :attr:`finished` for the return value, or :attr:`failed` for the
    exception. Exactly one of the two is emitted, always on the GUI thread.
    """

    def __init__(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._signals = _Signals()
        self.finished = self._signals.finished
        self.failed = self._signals.failed
        # Python owns this object, not the thread pool; see _pending above.
        self.setAutoDelete(False)

    def run(self) -> None:  # noqa: D102 - QRunnable API
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 - reported to the caller
            log.exception("Background task %s failed", getattr(self._fn, "__name__", self._fn))
            self._emit(self._signals.failed, exc)
        else:
            self._emit(self._signals.finished, result)

    def _emit(self, signal: Any, payload: Any) -> None:
        """Emit, tolerating a receiver that went away while we were working.

        During shutdown Qt can tear the signal object down before a still-running
        task reaches this point; that is not an error worth crashing over.

        It is also the one path on which the slot that releases this task from
        :data:`_pending` never runs, because the signal that would have carried
        it is the thing that just failed. So the release happens here instead:
        that set is a lifetime guard rather than a record of anything, and an
        entry nobody will ever take out is a leak for the life of the process.
        """
        try:
            signal.emit(payload)
        except RuntimeError:  # pragma: no cover - shutdown race
            log.debug("Task result dropped: the receiver was already destroyed")
            _pending.discard(self)


def _survivor(callback: Callable[[Any], None]) -> Callable[[Any], None]:
    """Wrap *callback* so a result for a widget that has gone is dropped.

    Background work outlives the thing that asked for it more often than it
    looks: a screen is rebuilt, a window closes, and a second later the answer
    arrives for a widget whose C++ side no longer exists. PyQt reports that as
    a ``RuntimeError`` raised inside a slot — and an unhandled exception in a
    slot aborts the process, which is a hard crash for a result nobody wanted.
    """

    def deliver(payload: Any) -> None:
        try:
            callback(payload)
        except RuntimeError as exc:
            if "has been deleted" not in str(exc):
                raise
            log.debug("Dropping a background result: the receiver is gone")

    return deliver


def run_async(
    fn: Callable[..., Any],
    on_done: Callable[[Any], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
    /,
    *args: Any,
    **kwargs: Any,
) -> Task:
    """Convenience wrapper: build a :class:`Task`, wire it up and start it."""
    task = Task(fn, *args, **kwargs)
    if on_done is not None:
        task.finished.connect(_survivor(on_done))
    if on_error is not None:
        task.failed.connect(_survivor(on_error))

    # Connected last so the caller's handler runs before the task is released.
    task.finished.connect(lambda _result, t=task: _pending.discard(t))
    task.failed.connect(lambda _error, t=task: _pending.discard(t))

    _pending.add(task)
    pool = QThreadPool.globalInstance()
    if pool is None:  # pragma: no cover - Qt always has one
        # Not an assert: those are compiled out under `python -O`, and what
        # follows the assert would then be `None.start(task)`.
        _pending.discard(task)
        raise RuntimeError("there is no global QThreadPool to run this on")
    pool.start(task)
    return task


def wait_for_tasks(timeout_ms: int = 5000) -> bool:
    """Block until running tasks finish. Call this before the process exits.

    Without it, a worker still inside a slow Portage call would keep touching
    Python objects that interpreter shutdown is busy tearing down — which ends
    in a hard abort rather than a clean exit.
    """
    pool = QThreadPool.globalInstance()
    if pool is None:
        return True
    return pool.waitForDone(timeout_ms)
