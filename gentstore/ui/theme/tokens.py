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

"""Design tokens — the single source of truth for colours, spacing and type.

Values are transcribed from the "nocturne" design canvas (see Docs/02-ui-design.md).
Nothing else in the code base is allowed to hard-code a colour: styling either goes
through the generated stylesheet (``qss.py``) or reads a constant from here.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Colours
# --------------------------------------------------------------------------- #

BG = "#161826"
SURFACE = "#232532"
TEXT = "#e9e9ed"
ACCENT = "#9184d9"

NEUTRAL_100 = "#f3f5fe"
NEUTRAL_200 = "#e4e7f5"
NEUTRAL_300 = "#cfd3e5"
NEUTRAL_400 = "#b2b6ca"
NEUTRAL_500 = "#9397ab"
NEUTRAL_600 = "#75798c"
NEUTRAL_700 = "#595d6c"
NEUTRAL_800 = "#3f424d"
NEUTRAL_900 = "#292b31"

ACCENT_100 = "#f5f4ff"
ACCENT_200 = "#e7e5fe"
ACCENT_300 = "#d2cefd"
ACCENT_400 = "#b5abfc"
ACCENT_500 = "#968ae0"
ACCENT_600 = "#796cbf"
ACCENT_700 = "#5d5294"
ACCENT_800 = "#423a6a"
ACCENT_900 = "#2b2741"

#: Border colour used for every panel, card and separator.
BORDER = NEUTRAL_800

# Semantic colours — success / warning / error.
OK = "#74b58c"
WARN = "#d9b072"
ERR = "#d98a72"

#: Translucent backgrounds for diff lines (added / removed).
#:
#: Written as ``rgba()`` and not as ``#RRGGBBAA``: neither Qt's stylesheets nor
#: its rich text understand an eight-digit hex colour, and rather than refusing
#: it they read it as something else entirely — which turned a red removal and a
#: green addition into two identical olive stripes.
DIFF_ADD_BG = "rgba(116, 181, 140, 0.13)"
DIFF_DEL_BG = "rgba(217, 138, 114, 0.13)"

# --------------------------------------------------------------------------- #
# Spacing and radii (pixels, rounded from the canvas' fractional values)
# --------------------------------------------------------------------------- #

SPACE_1 = 3
SPACE_2 = 6
SPACE_3 = 8
SPACE_4 = 11
SPACE_6 = 17
SPACE_8 = 22

RADIUS_SM = 4
RADIUS_MD = 8
RADIUS_LG = 14

# --------------------------------------------------------------------------- #
# Fixed chrome dimensions
# --------------------------------------------------------------------------- #

MENUBAR_HEIGHT = 29
TOOLBAR_HEIGHT = 38
STATUSBAR_HEIGHT = 26
SIDEBAR_WIDTH = 206
LIST_PANE_WIDTH = 352

WINDOW_DEFAULT_SIZE = (1520, 960)
WINDOW_MINIMUM_SIZE = (1100, 700)

# --------------------------------------------------------------------------- #
# Typography
# --------------------------------------------------------------------------- #

#: Preferred UI faces, in order. Inter is what the canvas uses; the rest are
#: fallbacks that are realistically present on a Gentoo desktop.
UI_FONT_FAMILIES = ("Inter", "Noto Sans", "DejaVu Sans", "Liberation Sans", "sans-serif")

#: Monospace faces, used for everything the user might retype into a terminal:
#: atoms, paths, commands, versions, USE flags.
MONO_FONT_FAMILIES = ("JetBrains Mono", "Fira Mono", "Noto Sans Mono", "DejaVu Sans Mono",
                      "Liberation Mono", "monospace")

#: Base pixel sizes at 100 % scale. ``scaled()`` multiplies these.
FONT_NANO = 10
FONT_MICRO = 10.5
FONT_TINY = 11
FONT_SMALL = 11.5
FONT_BASE = 12.5
FONT_MEDIUM = 13
FONT_H2 = 15
FONT_H1 = 19
FONT_H1_MONO = 20


def font_stack(families: tuple[str, ...]) -> str:
    """Render a font family tuple as a CSS/QSS font-family value."""
    return ", ".join(f'"{name}"' if " " in name else name for name in families)


def scaled(size: float, scale: float) -> int:
    """Scale a base pixel size, never dropping below 8 px."""
    return max(8, round(size * scale))
