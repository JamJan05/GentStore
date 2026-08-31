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

"""The profile: the one setting that changes everything at once.

A profile decides the default USE flags, which packages are masked, what counts
as part of the system. Changing it is not like changing a variable — it is the
nearest thing Gentoo has to changing distribution, and the rest of the machine
has to be rebuilt to match.

So this screen is mostly explanation. The list is there, the change is one
command, and between them sits a confirmation that says what will happen next
rather than "are you sure?".
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core import profiles
from ...core.profiles import Profile
from ...runner import eselect
from ..context import AppContext
from ..i18n import untranslated
from ..theme import tokens as t
from .base import Page
from .registry import PageSpec

log = logging.getLogger(__name__)


class _ProfileRow(QFrame):
    """One profile eselect offers."""

    def __init__(self, page: ProfilePage, item: Profile) -> None:
        super().__init__(page)
        self.setObjectName("profileRow")
        self.setProperty("current", "yes" if item.current else "no")
        self._page = page
        self.item = item

        layout = QHBoxLayout(self)
        layout.setContentsMargins(t.SPACE_4, t.SPACE_2, t.SPACE_4, t.SPACE_2)
        layout.setSpacing(t.SPACE_3)

        index = QLabel(f"[{item.index}]")
        index.setProperty("role", "mono")
        index.setFixedWidth(46)
        layout.addWidget(index)

        path = QLabel(item.path)
        path.setObjectName("profilePath")
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(path)

        self._stability = QLabel(item.stability)
        self._stability.setObjectName("repoQuality")
        self._stability.setProperty("official", "yes" if item.is_stable else "no")
        layout.addWidget(self._stability)
        layout.addStretch(1)

        self._action = QPushButton()
        self._action.clicked.connect(lambda: page.choose(item))
        layout.addWidget(self._action)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._stability.setText(self.item.stability or self.tr("unmarked"))
        self._action.setText(
            self.tr("in use") if self.item.current else self.tr("Use this one…")
        )
        self._action.setEnabled(not self.item.current)


class ProfilePage(Page):
    """Which profile is in use, and how to change it."""

    def __init__(
        self, spec: PageSpec, context: AppContext, parent: QWidget | None = None
    ) -> None:
        super().__init__(spec, context, parent)
        self._profiles: tuple[Profile, ...] = ()
        self._rows: list[_ProfileRow] = []
        self._collecting = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("detailPane")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("detailContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(t.SPACE_8, t.SPACE_6, t.SPACE_8, t.SPACE_8)
        layout.setSpacing(t.SPACE_4)

        self._heading = QLabel()
        self._heading.setProperty("role", "heading")
        layout.addWidget(self._heading)

        self._current = QLabel()
        self._current.setObjectName("packageAtom")
        self._current.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._current)

        self._warning = QLabel()
        self._warning.setObjectName("addOverlayWarning")
        self._warning.setWordWrap(True)
        layout.addWidget(self._warning)

        controls = QHBoxLayout()
        controls.setSpacing(t.SPACE_3)
        self._search = QLineEdit()
        self._search.setObjectName("searchInput")
        self._search.textChanged.connect(self._rebuild)
        controls.addWidget(self._search, 1)
        self._refresh = QPushButton()
        self._refresh.clicked.connect(self.reload)
        controls.addWidget(self._refresh)
        layout.addLayout(controls)

        self._list = QWidget()
        self._list_layout = QVBoxLayout(self._list)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        layout.addWidget(self._list)

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        context.command.finished.connect(self._on_command_finished)
        self.retranslate_ui()

    # -------------------------------------------------------------- data --

    def activated(self) -> None:
        if not self._profiles:
            self.reload()

    def reload(self) -> None:
        """Ask eselect. Its numbering is what the user would type, so we use it."""
        self._collecting = True
        if not self.context.run(eselect.list_profiles()):
            self._collecting = False

    def _on_command_finished(self, code: int) -> None:
        if not self._collecting:
            return
        self._collecting = False
        if code != 0:
            return
        window = self.window()
        output = window.log_view.text() if hasattr(window, "log_view") else ""
        self._profiles = profiles.parse(output)
        self._rebuild()
        self.retranslate_ui()

    def _rebuild(self) -> None:
        while self._list_layout.count():
            entry = self._list_layout.takeAt(0)
            widget = entry.widget() if entry is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._rows = []

        for item in profiles.search(self._profiles, self._search.text()):
            row = _ProfileRow(self, item)
            self._rows.append(row)
            self._list_layout.addWidget(row)

    # ------------------------------------------------------------ changing --

    def choose(self, item: Profile) -> None:
        """Docs/04-privileges.md §6: say what follows, then ask."""
        current = profiles.current(self._profiles)
        answer = QMessageBox.question(
            self,
            self.tr("Change the profile"),
            self.tr(
                "Switch from\n  {old}\nto\n  {new}?\n\n"
                "This changes the default USE flags, which packages are masked and what "
                "counts as part of the system. Afterwards the machine has to be rebuilt "
                "to match:\n\n"
                "  emerge --ask --verbose --update --deep --newuse @world\n\n"
                "That is a long build, and it is not optional. This will run:\n\n"
                "  eselect profile set {index}"
            ).format(
                old=current.path if current else "?",
                new=item.path,
                index=item.index,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self.context.run(eselect.set_profile(item.index)):
            # The profile decides the defaults for everything, so nothing the
            # application has cached about packages survives it.
            self.context.reload_portage()
            self.context.reload_index()

    # -------------------------------------------------------------- i18n --

    def retranslate_ui(self) -> None:
        self._heading.setText(self.spec.title)
        current = profiles.current(self._profiles)
        self._current.setText(
            current.path if current else self.tr("reading the profile list…")
        )
        self._warning.setText(
            self.tr(
                "The profile is the closest thing Gentoo has to a choice of distribution. "
                "It sets the default USE flags, masks packages and decides what belongs to "
                "the system set. Changing it is not a setting — it is a decision followed "
                "by a full rebuild of everything installed."
            )
        )
        self._search.setPlaceholderText(self.tr("filter, e.g. plasma or hardened"))
        self._refresh.setText(self.tr("Refresh"))
        self._refresh.setToolTip(untranslated("eselect profile list"))
        for row in self._rows:
            row.retranslate_ui()
