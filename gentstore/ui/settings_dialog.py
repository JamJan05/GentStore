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

"""The Settings window.

Five things, and every one of them is a preference about how Gentstore behaves
rather than about the system it manages. Nothing here writes to ``/etc``: the
choices are stored in the user's own configuration and take effect the next time
something needs them.

The wording matters more than the widgets. "Use binary packages" and "how to
become root" both sound like small toggles and are not, so each says what it
actually changes underneath.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core import binrepos
from ..runner import privilege
from ..settings import FONT_SCALES, Settings
from .i18n import untranslated
from .theme import tokens as t


class SettingsDialog(QDialog):
    """Language, size, privileges, binaries and backups."""

    #: The language changed; the application re-translates itself.
    language_changed = pyqtSignal(str)
    #: The interface scale changed.
    font_scale_changed = pyqtSignal(float)

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setModal(True)
        self.setMinimumWidth(620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_6, t.SPACE_4, t.SPACE_6, t.SPACE_4)
        layout.setSpacing(t.SPACE_4)

        form = QFormLayout()
        form.setSpacing(t.SPACE_3)

        self._language = QComboBox()
        for code in ("system", "pl", "en"):
            self._language.addItem("", code)
        self._language.setCurrentIndex(
            max(0, self._language.findData(settings.language))
        )
        self._language_label = QLabel()
        form.addRow(self._language_label, self._language)

        self._scale = QComboBox()
        for value in FONT_SCALES:
            self._scale.addItem(f"{round(value * 100)} %", value)
        self._scale.setCurrentIndex(max(0, self._scale.findData(settings.font_scale)))
        self._scale_label = QLabel()
        form.addRow(self._scale_label, self._scale)

        self._escalation = QComboBox()
        for code in ("auto", "pkexec", "sudo"):
            self._escalation.addItem("", code)
        self._escalation.setCurrentIndex(
            max(0, self._escalation.findData(settings.escalation))
        )
        self._escalation_label = QLabel()
        form.addRow(self._escalation_label, self._escalation)

        self._binaries = QCheckBox()
        self._binaries.setChecked(settings.use_binaries)
        self._binaries_label = QLabel()
        form.addRow(self._binaries_label, self._binaries)

        self._form = QComboBox()
        for code in ("directory", "archive"):
            self._form.addItem("", code)
        self._form.setCurrentIndex(max(0, self._form.findData(settings.backup_form)))
        self._form_label = QLabel()
        form.addRow(self._form_label, self._form)

        self._keep = QSpinBox()
        self._keep.setRange(1, 100)
        self._keep.setValue(settings.backup_keep)
        self._keep_label = QLabel()
        form.addRow(self._keep_label, self._keep)
        layout.addLayout(form)

        self._notes = QLabel()
        self._notes.setProperty("role", "caption")
        self._notes.setWordWrap(True)
        layout.addWidget(self._notes)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self._apply)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._escalation.currentIndexChanged.connect(self.retranslate_ui)
        self._binaries.toggled.connect(self.retranslate_ui)
        self.retranslate_ui()

    # -- saving ------------------------------------------------------------

    def _apply(self) -> None:
        settings = self._settings
        language = self._language.currentData()
        scale = self._scale.currentData()

        settings.escalation = self._escalation.currentData()
        settings.use_binaries = self._binaries.isChecked()
        settings.backup_form = self._form.currentData()
        settings.backup_keep = self._keep.value()
        settings.sync()

        # The two that change the window itself go out as signals; the rest are
        # read when they are next needed.
        privilege.preferred = settings.escalation
        if language != settings.language:
            self.language_changed.emit(language)
        if abs(scale - settings.font_scale) > 0.01:
            self.font_scale_changed.emit(scale)
        self.accept()

    # -- wording -----------------------------------------------------------

    def _escalation_note(self) -> str:
        chosen = self._escalation.currentData()
        if chosen == "sudo":
            return self.tr(
                "sudo needs a terminal or SUDO_ASKPASS to ask for the password; without "
                "one, privileged operations will not run."
            )
        if chosen == "pkexec":
            return self.tr("pkexec asks in a window and names what it is being asked for.")
        return self.tr("pkexec when it is available, sudo otherwise.")

    def _binary_note(self) -> str:
        if not self._binaries.isChecked():
            return self.tr("Everything is compiled from source, which is the Gentoo default.")
        hosts = ", ".join(repo.name for repo in binrepos.read()) or self.tr("none configured")
        return self.tr(
            "A prebuilt package is used only when its USE flags and dependencies match "
            "this system exactly, so nothing about *what* gets installed changes — only "
            "how it arrives. Binary hosts: {hosts}."
        ).format(hosts=hosts)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Settings"))
        self._language_label.setText(self.tr("Language"))
        self._language.setItemText(0, self.tr("System default"))
        self._language.setItemText(1, untranslated("Polski"))
        self._language.setItemText(2, untranslated("English"))

        self._scale_label.setText(self.tr("Interface size"))
        self._escalation_label.setText(self.tr("Becoming root"))
        self._escalation.setItemText(0, self.tr("automatic"))
        self._escalation.setItemText(1, untranslated("pkexec"))
        self._escalation.setItemText(2, untranslated("sudo"))

        self._binaries_label.setText(self.tr("Use binary packages"))
        self._binaries.setText(self.tr("pass --getbinpkg when installing"))

        self._form_label.setText(self.tr("Backup form"))
        self._form.setItemText(0, self.tr("a directory in /etc"))
        self._form.setItemText(1, self.tr("one .tar.gz archive"))
        self._keep_label.setText(self.tr("Backups kept"))

        self._notes.setText(f"{self._escalation_note()}\n\n{self._binary_note()}")

        ok = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(self.tr("Save"))
            ok.setProperty("variant", "primary")
        cancel = self._buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel is not None:
            cancel.setText(self.tr("Cancel"))

    def changeEvent(self, event: QEvent | None) -> None:  # noqa: N802 - Qt API
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
