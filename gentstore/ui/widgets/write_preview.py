"""The "this is what will be written" panel.

The visual form of the rule from Docs/01-architecture.md: every change to
``/etc/portage`` is *preview → write → report*. Six screens use it, so it looks
and behaves identically everywhere — the same three beats in the same place,
whether the user is changing a USE flag, accepting a keyword or enabling an
overlay.

The middle beat is deliberately dull: one button, and it stays disabled until
there is something to write and the choice is valid.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.confedit import TargetKind, WritePlan
from ..theme import tokens as t


class WritePreview(QFrame):
    """Shows the pending line, writes it on request, then reports what happened."""

    save_requested = pyqtSignal()
    reset_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("writePreview")
        self._plan: WritePlan | None = None
        self._blocked_reason = ""
        self._busy = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, t.SPACE_3)
        layout.setSpacing(t.SPACE_2)

        header = QHBoxLayout()
        header.setSpacing(t.SPACE_3)
        self._title = QLabel()
        self._title.setProperty("role", "subheading")
        header.addWidget(self._title)
        self._subtitle = QLabel()
        self._subtitle.setProperty("role", "caption")
        header.addWidget(self._subtitle)
        header.addStretch(1)
        layout.addLayout(header)

        self._path = QLabel()
        self._path.setObjectName("writePath")
        self._path.setWordWrap(True)
        self._path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._path)

        self._line = QLabel()
        self._line.setObjectName("writeLine")
        self._line.setWordWrap(True)
        self._line.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._line)

        self._explanation = QLabel()
        self._explanation.setProperty("role", "caption")
        self._explanation.setWordWrap(True)
        layout.addWidget(self._explanation)

        buttons = QHBoxLayout()
        buttons.setSpacing(t.SPACE_2)
        buttons.addStretch(1)
        self._reset = QPushButton()
        self._reset.clicked.connect(self.reset_requested)
        buttons.addWidget(self._reset)
        self._save = QPushButton()
        self._save.setProperty("variant", "primary")
        self._save.clicked.connect(self.save_requested)
        buttons.addWidget(self._save)
        layout.addLayout(buttons)

        self._report = QLabel()
        self._report.setObjectName("writeReport")
        self._report.setWordWrap(True)
        self._report.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._report.hide()
        layout.addWidget(self._report)

        self.retranslate_ui()
        self.hide()

    # -- the preview -------------------------------------------------------

    def set_plan(self, plan: WritePlan | None, blocked_reason: str = "") -> None:
        """Show *plan*, or hide the panel when there is nothing to write.

        *blocked_reason* — a broken ``REQUIRED_USE``, say — leaves the plan on
        screen but refuses to write it, because the user still needs to see the
        line they are trying to save.
        """
        self._plan = plan
        self._blocked_reason = blocked_reason
        self._report.hide()
        self._busy = False

        if plan is None or plan.is_noop:
            self.hide()
            return
        self.show()
        self.retranslate_ui()

    def set_busy(self, busy: bool) -> None:
        """While the helper is running and polkit may be asking for a password."""
        self._busy = busy
        self.retranslate_ui()

    def report_success(self, message: str) -> None:
        self._report.setProperty("state", "ok")
        self._report.setText(message)
        self._report.show()
        self._busy = False
        self._repolish(self._report)
        self.retranslate_ui()

    def report_failure(self, message: str) -> None:
        self._report.setProperty("state", "err")
        self._report.setText(message)
        self._report.show()
        self._busy = False
        self._repolish(self._report)
        self.retranslate_ui()

    # -- presentation ------------------------------------------------------

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)
        widget.update()

    def _target_note(self, plan: WritePlan) -> str:
        """Why this file and not another.

        The name comes from the plan rather than being written into the
        sentence: the same panel explains ``package.use``, ``package.mask`` and
        ``package.accept_keywords``, and telling somebody their repository mask
        went into package.use would be worse than saying nothing.
        """
        target = plan.path.parent.name if plan.creates_file else plan.path.name
        return {
            TargetKind.DIRECTORY: self.tr(
                "{file} is a directory, so the entry goes in a file of its own."
            ).format(file=target),
            TargetKind.EXISTING: self.tr("This file already has an entry for it."),
            TargetKind.SINGLE_FILE: self.tr(
                "{file} is a single file; the line is added at the end."
            ).format(file=target),
            TargetKind.NEW_DIRECTORY: self.tr(
                "Neither {file} nor a directory of that name exists yet. Gentoo "
                "recommends the directory form, so that is what will be created."
            ).format(file=target),
        }[plan.kind]

    def _operation_note(self, plan: WritePlan) -> str:
        if plan.op == "replace_line":
            return self.tr("One line is replaced:\n− {old}\n+ {new}").format(
                old=plan.previous or "", new=plan.line
            )
        if plan.op == "remove_line":
            return self.tr("One line is removed:\n− {old}").format(old=plan.previous or "")
        return self.tr("One line is added. Everything else in the file is left alone.")

    def retranslate_ui(self) -> None:
        self._title.setText(self.tr("Will be written"))
        self._subtitle.setText(self.tr("preview before saving"))
        self._reset.setText(self.tr("Discard changes"))
        self._save.setText(self.tr("Saving…") if self._busy else self.tr("Save"))

        plan = self._plan
        if plan is None or plan.is_noop:
            return

        self._path.setText(str(plan.path))
        self._line.setText(plan.previous if plan.op == "remove_line" else plan.line)
        self._explanation.setText(f"{self._operation_note(plan)}\n{self._target_note(plan)}")

        can_save = not self._busy and not self._blocked_reason
        self._save.setEnabled(can_save)
        self._save.setToolTip(self._blocked_reason)
        self._reset.setEnabled(not self._busy)

    def changeEvent(self, event: QEvent | None) -> None:  # noqa: N802 - Qt API
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
