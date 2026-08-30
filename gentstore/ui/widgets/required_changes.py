"""What emerge wants changed before it will build anything.

A masked package is a question about the package itself, and
:mod:`gentstore.ui.widgets.block_notice` answers it. This frame is for the
other case: the package is perfectly installable, and something it *depends on*
is not configured the way it needs. ``emerge`` finds that out while resolving
the graph, refuses, and prints a block of lines for ``/etc/portage``.

That refusal used to arrive as raw terminal output with no way to act on it,
even though the line is already written out and the machinery to save it is the
same one the licence and keyword blocks use. So the lines are shown as lines,
each with the reason emerge gave for wanting it, and each with the preview →
save → report the rest of the screen uses for /etc/portage.

The "why" matters more here than anywhere else on this screen. Nothing is wrong
with the package the user asked for; the demand comes from a dependency they
very likely have never heard of, and without the ``# required by`` lines the
request looks arbitrary.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.confedit import WritePlan, cp_from_atom, plan_entry
from ...core.emerge_parse import Preview, RequiredEntry
from ..theme import icons
from ..theme import tokens as t
from .write_preview import WritePreview

log = logging.getLogger(__name__)


class RequiredChanges(QFrame):
    """The ``/etc/portage`` lines emerge is waiting for, each one actionable."""

    #: Save was pressed; the payload is the :class:`WritePlan`.
    write_requested = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("requiredChanges")
        self._entries: tuple[RequiredEntry, ...] = ()
        self._armed: RequiredEntry | None = None
        self._plan: WritePlan | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(t.SPACE_6, t.SPACE_4, t.SPACE_6, t.SPACE_4)
        body_layout.setSpacing(t.SPACE_3)

        heading = QHBoxLayout()
        heading.setSpacing(t.SPACE_3)
        self._icon = QLabel()
        heading.addWidget(self._icon)
        self._title = QLabel()
        self._title.setProperty("role", "lead")
        heading.addWidget(self._title)
        heading.addStretch(1)
        body_layout.addLayout(heading)

        self._explanation = QLabel()
        self._explanation.setProperty("role", "body")
        self._explanation.setWordWrap(True)
        body_layout.addWidget(self._explanation)

        #: One row per line emerge asked for, rebuilt whenever the answer changes.
        self._rows = QWidget()
        self._rows_layout = QVBoxLayout(self._rows)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(t.SPACE_3)
        body_layout.addWidget(self._rows)

        layout.addWidget(body)

        self._preview = WritePreview()
        self._preview.save_requested.connect(self._on_save)
        self._preview.reset_requested.connect(self._disarm)
        layout.addWidget(self._preview)

        self.hide()

    # -- contents ----------------------------------------------------------

    def set_preview(self, preview: Preview | None) -> None:
        """Show what *preview* says emerge is waiting for, or hide the frame.

        Only the blocks that map to a file are kept. A REQUIRED_USE conflict
        also arrives as a "required change" and is deliberately dropped here:
        there is no line that resolves it, and offering one would be a lie.
        """
        entries: list[RequiredEntry] = []
        if preview is not None:
            for change in preview.required_changes:
                entries.extend(change.entries)

        self._entries = tuple(entries)
        self._disarm()

        if not self._entries:
            self.hide()
            return

        self.show()
        self.retranslate_ui()

    def clear(self) -> None:
        self.set_preview(None)

    def set_busy(self, busy: bool) -> None:
        self._preview.set_busy(busy)

    def report_success(self, message: str) -> None:
        self._preview.report_success(message)

    def report_failure(self, message: str) -> None:
        self._preview.report_failure(message)

    @property
    def plan(self) -> WritePlan | None:
        return self._plan

    @property
    def entries(self) -> tuple[RequiredEntry, ...]:
        return self._entries

    # -- the fix -----------------------------------------------------------

    def _arm(self, entry: RequiredEntry) -> None:
        """Show the exact line. Pressing a row's button never writes."""
        self._armed = entry
        self._plan = plan_entry(
            entry.file, cp_from_atom(entry.atom), entry.atom, entry.tokens
        )
        self._preview.set_plan(self._plan)
        self.retranslate_ui()

    def _disarm(self) -> None:
        self._armed = None
        self._plan = None
        self._preview.set_plan(None)

    def _on_save(self) -> None:
        if self._plan is not None and not self._plan.is_noop:
            self.write_requested.emit(self._plan)

    # -- wording -----------------------------------------------------------

    def _explanation_text(self) -> str:
        files = {entry.file for entry in self._entries}
        if files == {"package.use"}:
            return self.tr(
                "Nothing is wrong with the package you asked for. Something it needs "
                "is built without a feature it requires, and Portage will not guess "
                "whether rebuilding it is acceptable to you. Each line below turns one "
                "feature on for one package."
            )
        return self.tr(
            "Portage stopped before building anything because it needs these lines in "
            "your configuration first. Each one is shown with the package that asked "
            "for it."
        )

    def _row_reason(self, entry: RequiredEntry) -> str:
        """Who wants this line, in as few words as emerge gives us.

        The first ``required by`` is the package that needs it directly; the
        ones after it are the rest of the chain out to whatever was typed, and
        the last of them carries emerge's own ``(argument)`` marker, which
        means nothing to anybody reading a window.
        """
        if not entry.required_by:
            return ""
        who = entry.required_by[0].removeprefix("required by ").strip()
        who = who.partition(" (")[0].strip() or who
        return self.tr("Asked for by {package}").format(package=who)

    def _rebuild_rows(self) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

        for entry in self._entries:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(t.SPACE_3)

            text = QVBoxLayout()
            text.setSpacing(t.SPACE_1)
            line = QLabel(entry.line)
            line.setProperty("role", "mono")
            line.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            text.addWidget(line)
            reason = self._row_reason(entry)
            if reason:
                caption = QLabel(reason)
                caption.setProperty("role", "caption")
                caption.setWordWrap(True)
                text.addWidget(caption)
            row_layout.addLayout(text, 1)

            button = QPushButton(self.tr("Add this line…"))
            button.setToolTip(f"{entry.file}: {entry.line}")
            button.clicked.connect(lambda _checked=False, e=entry: self._arm(e))
            button.setVisible(self._armed is None)
            row_layout.addWidget(button)

            self._rows_layout.addWidget(row)

    def retranslate_ui(self) -> None:
        if not self._entries:
            return

        size = max(14, round(self.fontMetrics().height() * 1.05))
        self._icon.setPixmap(
            icons.tinted_pixmap("shield-warning", t.WARN, size, self.devicePixelRatioF())
        )
        self._title.setText(self.tr("Emerge needs a change first"))
        self._explanation.setText(self._explanation_text())
        self._rebuild_rows()

    def changeEvent(self, event: QEvent | None) -> None:  # noqa: N802 - Qt API
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
