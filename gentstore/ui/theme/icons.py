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

"""Icon loading and tinting.

Gentstore ships its own small monochrome icon set (``theme/icons/*.svg``) instead
of relying on the desktop icon theme, so the window looks the same whether the
user runs Breeze, Adwaita or Papirus. The SVGs are drawn in black; every icon is
recoloured at paint time with :func:`tinted_pixmap`, which lets one file serve
the active, inactive and hover states.

If the Qt SVG image plugin is unavailable, we fall back to the desktop theme via
``QIcon.fromTheme``; if that fails too the caller simply gets a null pixmap and
the interface stays usable, just without the glyph.

:func:`application_icon` is the exception to all of that: the application's own
icon, in colour, loaded from wherever this copy was installed and handed to the
window manager rather than drawn into the interface.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap

from ... import ICON_NAME

_ICON_DIR = Path(__file__).parent / "icons"

#: The application's own icon, in the checkout. An installed copy lives in
#: site-packages instead, where this path does not exist — see below.
_SOURCE_APP_ICON = Path(__file__).resolve().parents[3] / "data" / "icons" / f"{ICON_NAME}.svg"

#: Fallback names in the freedesktop icon naming spec, used only when our own
#: SVG cannot be rendered.
_THEME_FALLBACK = {
    "magnifying-glass": "system-search",
    "arrow-circle-up": "software-update-available",
    "git-branch": "folder-remote",
    "shield-warning": "security-medium",
    "files": "text-x-generic",
    "sliders": "preferences-system",
    "envelope": "mail-message",
    "package": "package-x-generic",
    "user-gear": "preferences-desktop-user",
    "arrows-clockwise": "view-refresh",
    "terminal-window": "utilities-terminal",
    "warning": "dialog-warning",
    "info": "dialog-information",
    "check": "dialog-ok",
}


def app_icon_search_paths() -> Iterator[Path]:
    """Where a copy of Gentstore might keep its own icon, best guess first."""
    yield _SOURCE_APP_ICON
    relative = Path("icons/hicolor/scalable/apps") / f"{ICON_NAME}.svg"
    home = os.environ.get("XDG_DATA_HOME") or "~/.local/share"
    yield Path(home).expanduser() / relative
    for directory in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":"):
        if directory:
            yield Path(directory) / relative


def application_icon() -> QIcon:
    """The window icon — Gentstore's own, not a monochrome interface glyph.

    ``QIcon.fromTheme`` is not enough on its own. It searches whatever paths the
    platform theme hands Qt, and a session that exposes no icon theme leaves
    that list as ``:/icons`` alone: the file is sitting in ``hicolor`` and Qt
    still answers with nothing. So the file is looked for directly — in the
    checkout first, then along ``XDG_DATA_DIRS`` where ``make install-desktop``
    and the ebuild put it — and ``fromTheme`` stays as the last resort for a
    layout none of that anticipated.
    """
    for path in app_icon_search_paths():
        if path.is_file():
            icon = QIcon(str(path))
            if not icon.isNull():
                return icon
    return QIcon.fromTheme(ICON_NAME)


@lru_cache(maxsize=64)
def load_icon(name: str) -> QIcon:
    """Return the bundled icon *name*, falling back to the desktop theme."""
    path = _ICON_DIR / f"{name}.svg"
    if path.is_file():
        icon = QIcon(str(path))
        if not icon.isNull():
            return icon
    return QIcon.fromTheme(_THEME_FALLBACK.get(name, name))


@lru_cache(maxsize=512)
def tinted_pixmap(name: str, color: str, size: int, dpr: float = 1.0) -> QPixmap:
    """Return icon *name* rendered at *size* px and recoloured to *color*.

    The tint works by filling the icon's alpha channel, so it is correct for any
    monochrome source — including a theme fallback that happens to be a different
    colour.
    """
    px = int(round(size * dpr))
    base = load_icon(name).pixmap(QSize(px, px))
    if base.isNull():
        return base

    tinted = QPixmap(base.size())
    tinted.fill(Qt.GlobalColor.transparent)

    painter = QPainter(tinted)
    painter.drawPixmap(0, 0, base)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QColor(color))
    painter.end()

    tinted.setDevicePixelRatio(dpr)
    return tinted


def clear_cache() -> None:
    """Drop cached pixmaps — call after a font-scale or theme change."""
    tinted_pixmap.cache_clear()
    load_icon.cache_clear()
