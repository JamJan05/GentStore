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
