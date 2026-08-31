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

"""Stand-in screen used until a page gets its real implementation.

It names the session that will build it, so the shell is honest about what is
and is not there yet instead of showing an empty rectangle.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..context import AppContext
from ..theme import icons
from ..theme import tokens as t
from .base import Page
from .registry import PageSpec


class PlaceholderPage(Page):
    """Centred icon, screen name and a note about the implementing session."""

    def __init__(
        self, spec: PageSpec, context: AppContext, parent: QWidget | None = None
    ) -> None:
        super().__init__(spec, context, parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_8, t.SPACE_8, t.SPACE_8, t.SPACE_8)
        layout.setSpacing(t.SPACE_4)
        layout.addStretch(1)

        self._icon = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._icon.setPixmap(
            icons.tinted_pixmap(spec.icon, t.NEUTRAL_800, 56, self.devicePixelRatioF())
        )
        layout.addWidget(self._icon)

        self._title = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._title.setProperty("role", "heading")
        layout.addWidget(self._title)

        self._note = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._note.setProperty("role", "caption")
        layout.addWidget(self._note)

        layout.addStretch(2)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._title.setText(self.spec.title)
        self._note.setText(
            self.tr("This screen is built in session {session}.").format(session=self.spec.session)
        )
