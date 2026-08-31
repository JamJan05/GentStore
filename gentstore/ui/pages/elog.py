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

"""Messages packages left behind while they were being installed.

``einfo`` and ``ewarn`` scroll past during a build and are gone by the time the
merge finishes. Portage keeps them and almost nobody knows where. This screen is
that place: every message, newest first, with the package that wrote it, the
build phase it came from and how seriously it meant it.

The list is filterable because a system with a few hundred merges behind it has
a few hundred of these, and the ones worth reading are the warnings and the
errors — which is why they sort to the top of a package's entry and colour it.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core import elog
from ...core.elog import ElogEntry, Severity
from ..context import AppContext
from ..tasks import run_async
from ..theme import tokens as t
from ..widgets.chips import Pill
from ..widgets.flow_layout import FlowWidget
from .registry import PageSpec
from .split_page import SplitPage

log = logging.getLogger(__name__)

#: Colour per class. QA notices are the package failing one of Gentoo's own
#: checks — worth seeing, but not the user's problem to fix.
SEVERITY_COLOURS = {
    Severity.ERROR: t.ERR,
    Severity.WARN: t.WARN,
    Severity.QA: t.ACCENT_300,
    Severity.LOG: t.NEUTRAL_400,
    Severity.INFO: t.OK,
}

#: Entries kept in the list. A long-lived system has thousands.
LIMIT = 500


class _EntryRow(QFrame):
    """One package's messages from one merge."""

    def __init__(self, page: ElogPage, entry: ElogEntry) -> None:
        super().__init__(page)
        self.setObjectName("elogRow")
        self.setProperty("severity", entry.severity.value)
        self._page = page
        self.entry = entry

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, t.SPACE_3)
        layout.setSpacing(t.SPACE_1)

        top = QHBoxLayout()
        top.setSpacing(t.SPACE_3)
        self._when = QLabel(entry.when.strftime("%Y-%m-%d %H:%M") if entry.when else "")
        self._when.setProperty("role", "mono")
        top.addWidget(self._when)
        self._severity = QLabel()
        self._severity.setObjectName("elogSeverity")
        self._severity.setProperty("severity", entry.severity.value)
        top.addWidget(self._severity)
        top.addStretch(1)
        layout.addLayout(top)

        name = QLabel(entry.package)
        name.setObjectName("elogPackage")
        layout.addWidget(name)

        summary = QLabel(entry.summary)
        summary.setProperty("role", "caption")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        self.retranslate_ui()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802, ANN001 - Qt API
        self._page.select(self.entry)
        super().mouseReleaseEvent(event)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "yes" if selected else "no")
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)

    def retranslate_ui(self) -> None:
        self._severity.setText(self._page.severity_label(self.entry.severity))


class ElogPage(SplitPage):
    """Every message, and the one being read."""

    def __init__(
        self, spec: PageSpec, context: AppContext, parent: QWidget | None = None
    ) -> None:
        super().__init__(spec, context, parent)

        self._entries: tuple[ElogEntry, ...] = ()
        self._rows: list[_EntryRow] = []
        self._selected: ElogEntry | None = None
        self._severity_filter: str = ""
        self._pills: dict[str, Pill] = {}

        self._build_list_pane()
        self._build_detail_pane()
        context.command.finished.connect(self._on_command_finished)
        self.retranslate_ui()

    # ------------------------------------------------------------ building --

    def _build_list_pane(self) -> None:
        header = QFrame()
        header.setObjectName("searchHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(t.SPACE_4, t.SPACE_4, t.SPACE_4, t.SPACE_4)
        header_layout.setSpacing(t.SPACE_3)

        self._search = QLineEdit()
        self._search.setObjectName("searchInput")
        self._search.textChanged.connect(lambda _text: self._rebuild())
        header_layout.addWidget(self._search)

        self._filters = FlowWidget(t.SPACE_2)
        for key in ("", Severity.ERROR.value, Severity.WARN.value, Severity.QA.value):
            pill = Pill()
            pill.clicked.connect(lambda k=key: self._set_filter(k))
            self._pills[key] = pill
            self._filters.add(pill)
        header_layout.addWidget(self._filters)
        self.list_layout.addWidget(header)

        holder = QScrollArea()
        holder.setWidgetResizable(True)
        holder.setObjectName("detailPane")
        holder.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        self._rows_layout = QVBoxLayout(content)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)
        self._rows_layout.addStretch(1)
        holder.setWidget(content)
        self.list_layout.addWidget(holder, 1)

    def _build_detail_pane(self) -> None:
        self._empty = QLabel()
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setProperty("role", "caption")
        self._empty.setWordWrap(True)
        self.detail_layout.addWidget(self._empty)

        self._title = QLabel()
        self._title.setObjectName("packageAtom")
        self._title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._title.hide()
        self.detail_layout.addWidget(self._title)

        self._meta = QLabel()
        self._meta.setProperty("role", "mono")
        self._meta.hide()
        self.detail_layout.addWidget(self._meta)

        self._body = QPlainTextEdit()
        self._body.setObjectName("elogBody")
        self._body.setReadOnly(True)
        self._body.hide()
        self.detail_layout.addWidget(self._body, 1)

    # -------------------------------------------------------------- data --

    def activated(self) -> None:
        self.reload()

    def reload(self) -> None:
        run_async(elog.load, self._on_loaded, self._on_load_failed)

    def _on_loaded(self, entries: object) -> None:
        if not isinstance(entries, tuple):
            return
        self._entries = entries[:LIMIT]
        self._rebuild()
        self.context.sidebar_badge.emit("elog", str(len(entries)) if entries else "")
        self.retranslate_ui()

    def _on_load_failed(self, error: Exception) -> None:
        log.error("Reading the elog messages failed: %s", error)

    def _on_command_finished(self, _code: int) -> None:
        """A merge just ended, so there may be new messages to read."""
        self.reload()

    def _set_filter(self, key: str) -> None:
        self._severity_filter = key
        self._rebuild()

    def _matching(self) -> tuple[ElogEntry, ...]:
        needle = self._search.text().strip().lower()
        found = self._entries
        if self._severity_filter:
            found = tuple(
                item for item in found if item.severity.value == self._severity_filter
            )
        if needle:
            found = tuple(
                item
                for item in found
                if needle in item.package.lower() or needle in item.text.lower()
            )
        return found

    def _rebuild(self) -> None:
        while self._rows_layout.count() > 1:
            entry = self._rows_layout.takeAt(0)
            widget = entry.widget() if entry is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._rows = []

        for item in self._matching():
            row = _EntryRow(self, item)
            self._rows.append(row)
            self._rows_layout.insertWidget(len(self._rows) - 1, row)

        for key, pill in self._pills.items():
            pill.set_checked(key == self._severity_filter)

        if self._rows:
            still = next(
                (
                    row.entry
                    for row in self._rows
                    if self._selected and row.entry.package == self._selected.package
                ),
                self._rows[0].entry,
            )
            self.select(still)
        else:
            self._selected = None
            self._show_detail(None)
        self.retranslate_ui()

    def select(self, entry: ElogEntry) -> None:
        self._selected = entry
        for row in self._rows:
            row.set_selected(row.entry is entry)
        self._show_detail(entry)

    def _show_detail(self, entry: ElogEntry | None) -> None:
        visible = entry is not None
        self._empty.setVisible(not visible)
        for widget in (self._title, self._meta, self._body):
            widget.setVisible(visible)
        if entry is None:
            return

        self._title.setText(entry.package)
        self._meta.setText(
            "   ·   ".join(
                part
                for part in (
                    entry.when.strftime("%Y-%m-%d %H:%M:%S") if entry.when else "",
                    str(entry.source) if entry.source else "",
                )
                if part
            )
        )
        self._body.clear()
        for block in entry.blocks:
            colour = SEVERITY_COLOURS[block.severity]
            self._body.appendHtml(
                f'<span style="color:{colour};font-weight:600">'
                f"{block.severity.value} · {block.phase}</span>"
            )
            for line in block.lines:
                self._body.appendHtml(
                    f'<span style="color:{t.NEUTRAL_300};white-space:pre">'
                    f"{_escape(line)}</span>"
                )
            self._body.appendHtml("")
        cursor = self._body.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        self._body.setTextCursor(cursor)

    # -------------------------------------------------------------- i18n --

    def severity_label(self, severity: Severity) -> str:
        return {
            Severity.ERROR: self.tr("error"),
            Severity.WARN: self.tr("warning"),
            Severity.QA: self.tr("quality notice"),
            Severity.LOG: self.tr("note"),
            Severity.INFO: self.tr("information"),
        }[severity]

    def retranslate_ui(self) -> None:
        self._search.setPlaceholderText(self.tr("package or text"))
        labels = {
            "": self.tr("all"),
            Severity.ERROR.value: self.severity_label(Severity.ERROR),
            Severity.WARN.value: self.severity_label(Severity.WARN),
            Severity.QA.value: self.severity_label(Severity.QA),
        }
        for key, pill in self._pills.items():
            pill.set_text(labels[key])
        self._empty.setText(
            self.tr("No messages yet. They appear here after a package is installed.")
            if not self._entries
            else self.tr("Nothing matches the filter.")
        )
        for row in self._rows:
            row.retranslate_ui()


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace(" ", "&nbsp;")
    )
