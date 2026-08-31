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

"""QPalette built from the design tokens.

The stylesheet covers most of the interface, but a handful of things Qt draws
itself — native context menus, tooltips, focus rings, disabled text — read the
palette instead. Setting both keeps the window dark everywhere, whatever theme
the user's desktop happens to use.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette

from . import tokens as t

Role = QPalette.ColorRole
Group = QPalette.ColorGroup


def build_palette() -> QPalette:
    """Return the application palette."""
    p = QPalette()

    p.setColor(Role.Window, QColor(t.BG))
    p.setColor(Role.WindowText, QColor(t.TEXT))
    p.setColor(Role.Base, QColor(t.BG))
    p.setColor(Role.AlternateBase, QColor(t.SURFACE))
    p.setColor(Role.Text, QColor(t.TEXT))
    p.setColor(Role.Button, QColor(t.SURFACE))
    p.setColor(Role.ButtonText, QColor(t.NEUTRAL_300))
    p.setColor(Role.BrightText, QColor(t.ERR))
    p.setColor(Role.Highlight, QColor(t.ACCENT_800))
    p.setColor(Role.HighlightedText, QColor(t.TEXT))
    p.setColor(Role.ToolTipBase, QColor(t.SURFACE))
    p.setColor(Role.ToolTipText, QColor(t.TEXT))
    p.setColor(Role.Link, QColor(t.ACCENT_300))
    p.setColor(Role.LinkVisited, QColor(t.ACCENT_400))
    p.setColor(Role.PlaceholderText, QColor(t.NEUTRAL_600))

    for role in (Role.WindowText, Role.Text, Role.ButtonText):
        p.setColor(Group.Disabled, role, QColor(t.NEUTRAL_700))

    return p
