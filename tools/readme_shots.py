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

"""Re-take the screenshots the README shows.

    python tools/readme_shots.py                 # straight into Docs/screenshots
    python tools/readme_shots.py --out /tmp/s    # somewhere else first

``tools/screenshot.py`` grabs a screen as it opens, which is enough for
reviewing layout. The README needs more than that: a package chosen, a USE flag
unfolded, a repository filter on, a preview table actually computed. Each shot
below therefore drives the window to the state it is meant to show, so that
refreshing the pictures is one command rather than a morning of clicking.

Rendering is off-screen and the window is pointed at a throwaway configuration
directory, so this never disturbs the running application's settings. One step
runs a real command — ``emerge -pvuDN --changed-use @world`` — which only ever
pretends; nothing here writes anything anywhere.
"""

from __future__ import annotations

import argparse
import os
import stat
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

def _private_dir(name: str) -> Path:
    """A directory under ``TMPDIR`` that belongs to this user and nobody else.

    ``/tmp`` is shared and a fixed name in it is a name somebody else can create
    first — as a symbolic link pointing at something of theirs, or of yours.
    Creating it 0700 and then checking that what is actually there is a
    directory, owned by us and not a link, is the whole of the defence. The uid
    is in the name so two people on one machine do not collide over it in the
    first place.
    """
    path = Path(os.environ.get("TMPDIR", "/tmp")) / f"{name}-{os.getuid()}"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise SystemExit(f"{path} is not a directory of yours; refusing to use it")
    path.chmod(0o700)
    return path


_SANDBOX = _private_dir("gentstore-readme-shots")
os.environ["XDG_CONFIG_HOME"] = str(_SANDBOX / "config")
os.environ["XDG_STATE_HOME"] = str(_SANDBOX / "state")

from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

from gentstore.app import GentstoreApplication  # noqa: E402
from gentstore.ui.main_window import MainWindow  # noqa: E402
from gentstore.ui.pages import SearchPage  # noqa: E402
from gentstore.ui.settings_dialog import SettingsDialog  # noqa: E402
from gentstore.ui.tasks import wait_for_tasks  # noqa: E402

#: Every shot the README embeds, in the order it embeds them.
SHOTS = (
    "search-and-install",
    "use-flags",
    "repository-filter",
    "update",
    "repositories",
    "config-files",
    "settings",
)


def settle(rounds: int = 12) -> None:
    """Finish outstanding background work and deliver its queued signals."""
    for _ in range(rounds):
        wait_for_tasks()
        for _ in range(20):
            QApplication.processEvents()


def wait_while_running(window: MainWindow, timeout: float = 300.0) -> None:
    """Pump the event loop until the command the page started has finished."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if not window.context.is_running:
            settle()
            if not window.context.is_running:
                return
        time.sleep(0.02)
    print("  … the command did not finish in time; capturing anyway", file=sys.stderr)


def capture(widget: QWidget, out: Path, name: str) -> None:
    QApplication.processEvents()
    pixmap = widget.grab()
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.png"
    pixmap.save(str(path), "PNG")
    print(f"  {path}  ({pixmap.width()}×{pixmap.height()})")


# -- the shots --------------------------------------------------------------


def search_page(window: MainWindow) -> SearchPage:
    """The search screen, with the index it needs already built."""
    window.set_page("search")
    page = window.stack.currentWidget()
    assert isinstance(page, SearchPage)
    settle()  # the index has to exist before there is anything to search
    return page


def shot_search(window: MainWindow, out: Path) -> None:
    """The first screen doing the ordinary thing: a query and a package."""
    page = search_page(window)
    page.set_query("mpv")
    settle()
    capture(window, out, "search-and-install")


def shot_use_flags(window: MainWindow, out: Path, package: str, flag: str) -> None:
    """One USE flag unfolded, so the "what does this change?" answer shows."""
    page = search_page(window)
    page.set_query(package)
    settle()

    row = page._use_panel._rows.get(flag)
    if row is None:
        print(f"  … {flag} is not a flag of this package", file=sys.stderr)
    else:
        row._flip()
        settle(2)
        # Scrolling to a fraction of the way down would drift every time the
        # package gains a flag; ask the scroll area for the row itself.
        page.detail_scroll.ensureWidgetVisible(row, 0, 260)
    capture(window, out, "use-flags")


def shot_repo_filter(window: MainWindow, out: Path, package: str, repo: str) -> None:
    """A package two repositories both carry, narrowed to one of them.

    The point of the picture is the atom in the top right: with a repository
    chosen it names that repository, so the command that runs is the one on
    screen rather than whatever Portage's repository priority would have picked.
    """
    page = search_page(window)
    page.set_query(package)
    settle()
    if repo in page._repo_pills:
        page._set_repo_filter(repo)
    else:
        print(f"  … no ::{repo} on this system; capturing unfiltered", file=sys.stderr)
    settle()
    capture(window, out, "repository-filter")


def shot_update(window: MainWindow, out: Path) -> None:
    """Step three, with the preview table filled in by a real ``emerge -p``.

    Worth knowing before re-running this: the table only has rows when the
    machine actually has updates waiting. On a system that is up to date the
    honest answer is an empty panel, which is a poor advertisement for the
    screen — take this one when there is something to show.
    """
    page = window.set_page("update") or window.stack.currentWidget()
    settle()
    page.select("preview")
    settle()
    print("  running emerge -pvuDN --changed-use @world …")
    page._preview_button.click()
    wait_while_running(window)
    settle()
    # The log opens by itself while a command runs; the picture is about the
    # step list and the table, so put it away again.
    window.log_dock.setVisible(False)
    settle(2)
    capture(window, out, "update")


def shot_repos(window: MainWindow, out: Path) -> None:
    page = window.set_page("repos") or window.stack.currentWidget()
    settle()
    page._search.setText("kde")
    settle()
    capture(window, out, "repositories")


def shot_cfgfiles(window: MainWindow, out: Path) -> None:
    window.set_page("cfg")
    settle()
    capture(window, out, "config-files")


def shot_settings(window: MainWindow, out: Path) -> None:
    """The dialog on its own — grabbing the window would only show it dimmed."""
    dialog = SettingsDialog(window.settings, window)
    dialog.show()
    settle(4)
    capture(dialog, out, "settings")
    dialog.close()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "Docs" / "screenshots"))
    parser.add_argument("--lang", default="en", choices=("pl", "en"))
    parser.add_argument("--size", default="1520x960", help="window size, e.g. 1280x800")
    parser.add_argument(
        "--tall", default="1520x1000", help="window size for the list-and-table screens"
    )
    parser.add_argument(
        "--flag",
        default="media-video/mpv:vulkan",
        help="the package and USE flag to unfold, as cat/pkg:flag",
    )
    parser.add_argument(
        "--pair",
        default="dev-libs/zydis::guru",
        help="the two-repository package for the filter shot, as cat/pkg::repo",
    )
    parser.add_argument("--only", action="append", choices=SHOTS, help="just these shots")
    options = parser.parse_args(argv[1:])

    wanted = set(options.only or SHOTS)
    out = Path(options.out)
    package, _, repo = options.pair.partition("::")

    app = GentstoreApplication(["gentstore"])
    app.apply_language(options.lang, persist=False)

    window = MainWindow(app.settings)
    window.context.set_official_only(False, "hide")
    window.show()
    window.load_system_info()
    window.context.ensure_index()
    settle()

    def size(spec: str) -> None:
        width, _, height = spec.partition("x")
        window.resize(int(width), int(height))
        settle(2)

    size(options.size)
    if "search-and-install" in wanted:
        shot_search(window, out)
    if "use-flags" in wanted:
        shot_use_flags(window, out, *options.flag.rsplit(":", 1))
    if "repository-filter" in wanted:
        shot_repo_filter(window, out, package, repo)
    if "repositories" in wanted:
        shot_repos(window, out)

    # The step lists and the preview table want the extra forty pixels.
    size(options.tall)
    if "update" in wanted:
        shot_update(window, out)
    if "config-files" in wanted:
        shot_cfgfiles(window, out)
    if "settings" in wanted:
        shot_settings(window, out)

    settle()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
