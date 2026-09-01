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

"""Render the window off-screen and save it as PNG.

    python tools/screenshot.py                     # current page, system language
    python tools/screenshot.py --lang pl --all     # every screen, Polish
    python tools/screenshot.py --out /tmp/shots    # choose the output directory
    python tools/screenshot.py --query mpv         # search screen with results

Useful for reviewing layout changes without a display, and for the screenshots
in the README. Forces the ``offscreen`` Qt platform plugin unless one is already
set in the environment.
"""

from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Rendering a screenshot must not change how the application starts next time.
# The window saves its geometry, the last screen and the toolbar switches on
# close, so the tool is pointed at a throwaway configuration directory unless
# it is told otherwise with --real-settings.
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


if "--real-settings" not in sys.argv:
    _sandbox = _private_dir("gentstore-screenshot-config")
    os.environ["XDG_CONFIG_HOME"] = str(_sandbox)
    os.environ["XDG_STATE_HOME"] = str(_sandbox)

from PyQt6.QtWidgets import QApplication  # noqa: E402

from gentstore.app import GentstoreApplication  # noqa: E402
from gentstore.ui.main_window import MainWindow  # noqa: E402
from gentstore.ui.pages import PAGES, SearchPage  # noqa: E402
from gentstore.ui.tasks import wait_for_tasks  # noqa: E402


def settle(rounds: int = 10) -> None:
    """Finish outstanding background work and deliver its queued signals."""
    for _ in range(rounds):
        wait_for_tasks()
        for _ in range(20):
            QApplication.processEvents()


def run_query(window: MainWindow, query: str) -> None:
    """Type *query* into the search screen and wait for the results."""
    window.set_page("search")
    page = window.stack.currentWidget()
    if not isinstance(page, SearchPage):  # pragma: no cover - defensive
        return
    settle()  # the index has to exist before there is anything to search
    page.set_query(query)
    settle()


def capture(window: MainWindow, path: Path) -> None:
    QApplication.processEvents()
    pixmap = window.grab()
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(path), "PNG")
    print(f"{path}  ({pixmap.width()}×{pixmap.height()})")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", default="en", choices=("system", "pl", "en"))
    parser.add_argument("--all", action="store_true", help="capture every screen")
    parser.add_argument("--query", help="type this into the search screen first")
    parser.add_argument(
        "--real-settings",
        action="store_true",
        help="use the real configuration instead of a throwaway one",
    )
    parser.add_argument("--out", default="/tmp/gentstore-shots", help="output directory")
    parser.add_argument("--size", default="1520x960", help="window size, e.g. 1280x800")
    parser.add_argument(
        "--scale", type=float, default=1.0, choices=(1.0, 1.15, 1.3), help="interface scale"
    )
    options = parser.parse_args(argv[1:])

    width, _, height = options.size.partition("x")

    app = GentstoreApplication(["gentstore"])
    app.apply_font_scale(options.scale)
    app.apply_language(options.lang, persist=False)

    window = MainWindow(app.settings)
    window.resize(int(width), int(height))
    window.show()

    out = Path(options.out)
    suffix = "" if options.scale == 1.0 else f"{round(options.scale * 100)}-"

    # Let the system-info task finish so the chrome is populated, then drain the
    # queued signal that delivers its result.
    window.load_system_info()
    settle()

    if options.query:
        run_query(window, options.query)

    if options.all:
        for spec in PAGES:
            window.set_page(spec.page_id)
            capture(window, out / f"{options.lang}-{suffix}{spec.page_id}.png")
    else:
        capture(window, out / f"{options.lang}-{suffix}{window.current_page_id()}.png")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
