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

"""The left-hand navigation column."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..pages.registry import PAGES
from ..theme import tokens as t
from .clickable_label import ClickableLabel
from .nav_item import NavItem


def _section_font(base: QFont) -> QFont:
    """Small, wide-tracked, upper-case font used for column headings."""
    font = QFont(base)
    font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108)
    font.setCapitalization(QFont.Capitalization.AllUppercase)
    return font


class Sidebar(QFrame):
    """Fixed-width navigation with one row per screen and a backup footer."""

    page_requested = pyqtSignal(str)
    restore_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(t.SIDEBAR_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, t.SPACE_3, 0, t.SPACE_3)
        layout.setSpacing(0)

        self._heading = QLabel()
        self._heading.setProperty("role", "section")
        self._heading.setFont(_section_font(self._heading.font()))
        self._heading.setContentsMargins(t.SPACE_4, 0, t.SPACE_4, t.SPACE_2)
        layout.addWidget(self._heading)

        self._items: dict[str, NavItem] = {}
        for spec in PAGES:
            item = NavItem(spec.page_id, spec.icon, self)
            item.activated.connect(self.page_requested)
            self._items[spec.page_id] = item
            layout.addWidget(item)

        layout.addStretch(1)

        separator = QFrame()
        separator.setProperty("role", "hline")
        separator.setFixedHeight(1)
        separator.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addSpacing(t.SPACE_3)
        layout.addWidget(separator)

        footer = QWidget()
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, 0)
        footer_layout.setSpacing(2)

        self._backup_heading = QLabel()
        self._backup_heading.setProperty("role", "caption")
        footer_layout.addWidget(self._backup_heading)

        self._backup_path = QLabel()
        self._backup_path.setProperty("role", "mono")
        self._backup_path.setWordWrap(True)
        self._backup_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        footer_layout.addWidget(self._backup_path)

        self._restore = ClickableLabel()
        self._restore.setProperty("role", "mono-accent")
        self._restore.setContentsMargins(0, t.SPACE_2, 0, 0)
        self._restore.clicked.connect(self.restore_requested)
        footer_layout.addWidget(self._restore)

        layout.addWidget(footer)

        self._backup_label: str | None = None
        self.retranslate_ui()

    # -- public API --------------------------------------------------------

    def set_active_page(self, page_id: str) -> None:
        for item_id, item in self._items.items():
            item.set_active(item_id == page_id)

    def set_badge(self, page_id: str, text: str) -> None:
        """Set the count badge on a row; an empty string clears it."""
        item = self._items.get(page_id)
        if item is not None:
            item.set_badge(text)

    def set_backup(self, label: str | None) -> None:
        """Name of the most recent ``/etc/portage`` backup, or ``None``."""
        self._backup_label = label
        self.retranslate_ui()

    # -- internals ---------------------------------------------------------

    def _update_width(self) -> None:
        """Widen the column just enough for the longest screen name.

        The design width fits every label at 100 %, but the interface-size setting
        and translation both make labels longer; rather than eliding them, the
        column grows — up to a cap, so it never eats the content area.
        """
        metrics = self.fontMetrics()
        icon = max(14, round(metrics.height() * 1.05))
        longest = max((metrics.horizontalAdvance(spec.title) for spec in PAGES), default=0)
        #  row margins + icon + gaps + text + room for a count badge
        needed = 2 * t.SPACE_2 + t.SPACE_3 + icon + t.SPACE_3 + longest + t.SPACE_3 + 30
        self.setFixedWidth(
            max(t.SIDEBAR_WIDTH, min(needed, round(t.SIDEBAR_WIDTH * 1.6)))
        )

    def retranslate_ui(self) -> None:
        self._heading.setText(self.tr("Management"))
        self._backup_heading.setText(self.tr("Backup"))
        self._backup_path.setText(self._backup_label or self.tr("none yet"))
        self._restore.setText(self.tr("Restore…"))
        self._restore.setEnabled(self._backup_label is not None)
        for spec in PAGES:
            self._items[spec.page_id].set_label(spec.title)
        self._update_width()

    def changeEvent(self, event: QEvent | None) -> None:  # noqa: N802 - Qt API
        if event is not None:
            if event.type() == QEvent.Type.LanguageChange:
                self.retranslate_ui()
            elif event.type() == QEvent.Type.FontChange:
                self._update_width()
        super().changeEvent(event)
