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

"""Smoke tests for the application shell.

They run head-less through the ``offscreen`` Qt platform plugin, so they work in
a terminal and in CI:

    QT_QPA_PLATFORM=offscreen pytest
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from gentstore import DESKTOP_ID  # noqa: E402
from gentstore.app import GentstoreApplication  # noqa: E402
from gentstore.ui.main_window import MainWindow  # noqa: E402
from gentstore.ui.pages import PAGES  # noqa: E402
from gentstore.ui.tasks import ProgressReporter, run_async, wait_for_tasks  # noqa: E402
from gentstore.ui.theme.qss import build_qss  # noqa: E402


@pytest.fixture
def window(app: GentstoreApplication, destroy):  # noqa: ANN001, ANN201 - conftest fixture
    """The main window, and then its destruction.

    Five of these are built in a full run and none of them used to be destroyed;
    see :func:`destroy` in tests/conftest.py for why that is not a leak but a
    crash waiting for the right heap layout.
    """
    app.apply_language("en")
    window = MainWindow(app.settings)
    yield window
    wait_for_tasks()
    destroy(window)


def test_the_application_introduces_itself_to_the_desktop(
    app: GentstoreApplication,
) -> None:
    """The two things a panel needs to show a window as Gentstore.

    Without the first, Qt names the Wayland surface after ``/proc/self/exe`` —
    the Python interpreter, for anything started through an entry point. Without
    the second, a session whose compositor cannot find our entry has no icon of
    ours to fall back on.
    """
    assert app.desktopFileName() == DESKTOP_ID
    assert not app.windowIcon().isNull(), "the application has no icon of its own"


def test_stylesheet_builds_at_every_scale() -> None:
    for scale in (1.0, 1.15, 1.3):
        sheet = build_qss(scale)
        assert "QMenuBar" in sheet
        assert "{{" not in sheet, "an f-string brace escaped into the output"


def test_every_page_is_reachable(window: MainWindow) -> None:
    for spec in PAGES:
        window.set_page(spec.page_id)
        assert window.current_page_id() == spec.page_id


def test_unknown_page_is_ignored(window: MainWindow) -> None:
    window.set_page("search")
    window.set_page("does-not-exist")
    assert window.current_page_id() == "search"


def test_page_titles_follow_the_language(app: GentstoreApplication, translations) -> None:
    app.apply_language("en")
    assert PAGES[0].title == "Search & install"

    app.apply_language("pl")
    assert PAGES[0].title == "Szukaj i instaluj"

    app.apply_language("en")


def test_switching_language_retranslates_the_window(
    app: GentstoreApplication, window: MainWindow, translations
) -> None:
    """The whole window must follow a language switch without a restart.

    Nothing here calls ``retranslate_ui`` by hand: installing a translator makes
    Qt deliver a LanguageChange event to every widget, and this asserts that the
    chain from the menu bar down to a hand-painted chip is actually wired up.
    """
    window.show()

    app.apply_language("en")
    QApplication.processEvents()
    assert window._menu_file.title() == "&File"
    assert window.sidebar._heading.text() == "Management"

    app.apply_language("pl")
    QApplication.processEvents()
    assert window._menu_file.title() == "&Plik"
    assert window._act_quit.text() == "Zakończ"
    assert window.sidebar._heading.text() == "Zarządzanie"
    assert window._official._chip._text == "Tylko ::gentoo"

    app.apply_language("en")
    QApplication.processEvents()


def test_official_only_toggle_persists(window: MainWindow) -> None:
    window._on_official_changed(True, "mask")
    assert window.settings.official_only is True
    assert window.settings.official_mode == "mask"

    window._on_official_changed(False, "hide")
    assert window.settings.official_only is False


def test_a_worker_reports_progress_back_to_the_gui_thread(app: GentstoreApplication) -> None:
    """The seam between synchronous ``core`` code and the window.

    ``core`` only ever sees a plain callable; the signal, the thread hop and the
    queued delivery are entirely this layer's business.
    """
    seen: list[tuple[int, int]] = []
    done: list[object] = []
    reporter = ProgressReporter()
    reporter.progress.connect(lambda a, b: seen.append((a, b)))

    def work(report) -> str:  # noqa: ANN001 - stands in for a core function
        for step in (1, 2, 3):
            report(step, 3)
        return "finished"

    run_async(work, done.append, None, reporter.report)
    assert wait_for_tasks(5000)
    # Several rounds: other tests leave tasks in the pool, and each round of
    # processEvents delivers one batch of queued cross-thread signals.
    for _ in range(10):
        app.processEvents()

    assert done == ["finished"]
    assert seen == [(1, 3), (2, 3), (3, 3)]


def test_a_result_arriving_after_shutdown_does_not_abort(app: GentstoreApplication) -> None:
    """A worker finishing while Qt is tearing down must not take the process.

    Closing the window while the package index is still building was enough:
    the index would land a few seconds later, find its signal object already
    destroyed on the C++ side, and raise inside a ``QRunnable`` — which Qt turns
    into an abort. A crash on the way out, for a result nobody was waiting for.

    Deleting the signal object is exactly what ``QApplication`` teardown does to
    it, so this is the real sequence rather than an imitation of it.
    """
    from PyQt6 import sip

    from gentstore.ui.tasks import Task, _pending

    for outcome, work in (("finished", lambda: "a result"), ("failed", _explode)):
        task = Task(work)
        _pending.add(task)
        sip.delete(task._signals)

        task.run()  # must return rather than raise

        assert task not in _pending, f"the {outcome} path leaks its task"


def _explode() -> None:
    raise ValueError("the work itself went wrong")


def test_the_masks_screen_says_it_is_still_working(window: MainWindow) -> None:
    """The conditional-licence section reads every LICENSE in every repository.

    That is seconds, so it runs on a worker and the section has to say so
    rather than sitting there looking empty — an empty section here means
    "nothing to worry about", which is the opposite of "not looked yet".
    """
    from PyQt6.QtWidgets import QLabel

    from gentstore.ui.pages.masks import MasksPage

    window.set_page("mask")
    page = window.stack.currentWidget()
    assert isinstance(page, MasksPage)

    page._conditional = None
    page._rebuild_conditional()
    texts = [label.text() for label in page._conditional_entries.findChildren(QLabel)]
    assert texts and "…" in texts[0]

    # An answer of "none" is a different sentence, and not the waiting one.
    page._conditional = ()
    page._rebuild_conditional()
    settled = [label.text() for label in page._conditional_entries.findChildren(QLabel)]
    assert settled and settled != texts


# -- leaving ----------------------------------------------------------------


def test_the_window_is_destroyed_before_the_application_lets_go(app) -> None:  # noqa: ANN001
    """``main`` builds the application first and the window second, and CPython
    releases a frame's locals in that same order — so without this the
    application went first and ``~QApplication`` deleted a window whose Python
    wrapper was still alive.

    The assertion is on the widget actually being gone, not merely scheduled.
    ``deleteLater`` hands ownership to C++ and posts a ``DeferredDelete`` that
    nothing is left to deliver, so a version of :func:`_release` that stops
    there would leave the window standing and this would catch it.
    """
    from PyQt6 import sip

    from gentstore.app import _release

    window = MainWindow(app.settings)
    _release(app, window)
    assert sip.isdeleted(window), "the window outlived the call that was meant to destroy it"


def test_the_application_exits_without_being_killed(tmp_path) -> None:
    """The whole entry point, in its own process, because that is where it went
    wrong: gentstore segfaulted on every exit, after the window was already
    gone, so nothing on screen ever showed it and only the exit status did.

    A signal is what this is looking for. A non-zero but orderly exit is left
    alone, because a host where the application declines to start is not what
    is being tested here.
    """
    import subprocess
    import sys

    driver = (
        "import os, sys\n"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
        "from PyQt6.QtCore import QTimer\n"
        "from PyQt6.QtWidgets import QApplication\n"
        "import gentstore.app as a\n"
        "show = a.MainWindow.show\n"
        "def leave():\n"
        "    for w in list(QApplication.topLevelWidgets()):\n"
        "        w.close()\n"
        "    QApplication.instance().quit()\n"
        "def patched(self):\n"
        "    show(self)\n"
        "    QTimer.singleShot(100, leave)\n"
        "a.MainWindow.show = patched\n"
        "sys.exit(a.main(['gentstore']))\n"
    )

    environment = dict(os.environ)
    environment.update(
        QT_QPA_PLATFORM="offscreen",
        XDG_CONFIG_HOME=str(tmp_path / "config"),
        XDG_STATE_HOME=str(tmp_path / "state"),
        XDG_RUNTIME_DIR=str(tmp_path / "run"),
        PYTHONPATH=str(Path(__file__).resolve().parent.parent),
    )
    (tmp_path / "run").mkdir(parents=True, exist_ok=True)
    (tmp_path / "run").chmod(0o700)

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", driver], env=environment, capture_output=True, timeout=120
    )
    assert result.returncode >= 0, (
        f"the process was killed by signal {-result.returncode}; "
        f"stderr tail: {result.stderr.decode(errors='replace')[-2000:]}"
    )
