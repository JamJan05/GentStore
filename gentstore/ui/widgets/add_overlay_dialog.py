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

"""Adding a repository that is not in Gentoo's published list.

Kept behind a dialog of its own, and a blunt one, because this is the single
most dangerous thing the application can be asked to do. An ebuild is a shell
script that Portage runs **as root** while building, so adding a repository is
handing its author that. The published catalogue at least means somebody put
their name to it; a URL typed in here means nothing of the sort.

The dialog says that in as many words and refuses to enable its own button until
both fields look like a name and a URL.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ...core.overlays import is_valid_name, is_valid_uri
from ..theme import tokens as t

#: What eselect can sync with. git covers nearly everything in practice.
SYNC_TYPES = ("git", "rsync", "svn", "mercurial")


class AddOverlayDialog(QDialog):
    """Name, sync type and URL — plus the warning that goes with them."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_6, t.SPACE_4, t.SPACE_6, t.SPACE_4)
        layout.setSpacing(t.SPACE_4)

        self._warning = QLabel()
        self._warning.setObjectName("addOverlayWarning")
        self._warning.setWordWrap(True)
        layout.addWidget(self._warning)

        form = QFormLayout()
        form.setSpacing(t.SPACE_3)
        self._name = QLineEdit()
        self._name.textChanged.connect(self._revalidate)
        self._name_label = QLabel()
        form.addRow(self._name_label, self._name)

        self._type = QComboBox()
        self._type.addItems(SYNC_TYPES)
        self._type_label = QLabel()
        form.addRow(self._type_label, self._type)

        self._uri = QLineEdit()
        self._uri.textChanged.connect(self._revalidate)
        self._uri_label = QLabel()
        form.addRow(self._uri_label, self._uri)
        layout.addLayout(form)

        self._command = QLabel()
        self._command.setProperty("role", "mono")
        self._command.setWordWrap(True)
        self._command.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._command)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self.retranslate_ui()
        self._revalidate()

    # -- the answer --------------------------------------------------------

    @property
    def repository(self) -> tuple[str, str, str]:
        """``(name, sync_type, uri)`` as typed."""
        return self._name.text().strip(), self._type.currentText(), self._uri.text().strip()

    @property
    def is_valid(self) -> bool:
        name, _sync_type, uri = self.repository
        return is_valid_name(name) and is_valid_uri(uri)

    def _revalidate(self) -> None:
        button = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if button is not None:
            button.setEnabled(self.is_valid)
        name, sync_type, uri = self.repository
        self._command.setText(
            f"eselect repository add {name} {sync_type} {uri}" if self.is_valid else ""
        )

    # -- i18n --------------------------------------------------------------

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Add a repository by hand"))
        self._warning.setText(
            self.tr(
                "Nobody has vouched for this repository.\n\n"
                "Building a package runs its ebuild as root. Adding a repository means "
                "trusting whoever writes those ebuilds with your machine — not just now, "
                "but at every future sync. Add one only if you know who is behind it."
            )
        )
        self._name_label.setText(self.tr("Name"))
        self._type_label.setText(self.tr("Sync type"))
        self._uri_label.setText(self.tr("URL"))
        ok = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(self.tr("Add"))
            ok.setProperty("variant", "danger")
        cancel = self._buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel is not None:
            cancel.setText(self.tr("Cancel"))

    def changeEvent(self, event: QEvent | None) -> None:  # noqa: N802 - Qt API
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
