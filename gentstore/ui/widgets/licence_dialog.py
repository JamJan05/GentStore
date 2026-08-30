"""Reading a licence before agreeing to it.

The whole point of ``ACCEPT_LICENSE`` is that somebody decided what they are
willing to run. A button that says "accept" without showing the text turns that
into a formality, so the text is here, scrollable, with the accept button
underneath it rather than beside it.

The dialog is careful about one thing in particular: accepting here applies to
**one package**, not to the licence everywhere and not to its group. Widening
``ACCEPT_LICENSE`` is a different decision, made in ``make.conf``, and the
wording says so.
"""

from __future__ import annotations

from PyQt6.QtGui import QTextOption
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...core.licenses import Licence
from ..theme import tokens as t


class LicenceDialog(QDialog):
    """The full text of one licence, with an accept button."""

    def __init__(
        self,
        licence: Licence,
        text: str | None,
        package: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._licence = licence
        self._package = package
        self.setModal(True)
        self.resize(760, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_6, t.SPACE_4, t.SPACE_6, t.SPACE_4)
        layout.setSpacing(t.SPACE_3)

        heading = QHBoxLayout()
        heading.setSpacing(t.SPACE_3)
        self._name = QLabel(licence.name)
        self._name.setObjectName("packageAtom")
        heading.addWidget(self._name)
        self._groups = QLabel()
        self._groups.setProperty("role", "mono")
        heading.addWidget(self._groups)
        heading.addStretch(1)
        layout.addLayout(heading)

        self._body = QPlainTextEdit()
        self._body.setObjectName("licenceText")
        self._body.setReadOnly(True)
        self._body.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self._body.setPlainText(text or "")
        layout.addWidget(self._body, 1)

        self._scope = QLabel()
        self._scope.setProperty("role", "caption")
        self._scope.setWordWrap(True)
        layout.addWidget(self._scope)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        accept = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if accept is not None:
            accept.setProperty("variant", "primary")
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Licence {name}").format(name=self._licence.name))
        self._groups.setText(
            " ".join(f"@{group}" for group in self._licence.groups)
            or self.tr("in no licence group")
        )
        if not self._body.toPlainText().strip():
            self._body.setPlainText(
                self.tr(
                    "No repository ships the text of this licence.\n\n"
                    "That is not unusual for licences that only exist as a reference to "
                    "something published elsewhere, but it does mean nobody can read it "
                    "here. Look it up before accepting."
                )
            )
        self._scope.setText(
            self.tr(
                "Accepting adds one line to /etc/portage/package.license for {package} "
                "only. It does not change ACCEPT_LICENSE and it does not accept the rest "
                "of the licence group."
            ).format(package=self._package)
        )
        accept = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if accept is not None:
            accept.setText(self.tr("Accept for this package"))
        cancel = self._buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel is not None:
            cancel.setText(self.tr("Cancel"))

    def changeEvent(self, event) -> None:  # noqa: N802, ANN001 - Qt API
        from PyQt6.QtCore import QEvent  # noqa: PLC0415 - only needed here

        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
