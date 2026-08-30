"""Deciding what to do with the files an update left behind.

The list on the left is every ``._cfg`` file waiting for an answer, with the
package that put it there and how many lines differ. The right side is the
difference itself — which is the preview, in the sense the rest of the
application uses that word: nothing happens until it has been looked at.

Three answers, and the third is the interesting one. *Keep mine* and *take
theirs* are the two ``dispatch-conf`` offers; *merge* opens the new version in
an editable pane so the two can be reconciled by hand and the result saved as
the file. In every case the version being replaced is copied into
``/etc/config-archive`` first, which is where ``dispatch-conf`` puts it too.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextOption
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...core import cfgfiles
from ...core.cfgfiles import ConfigFile
from ...runner import helper_client
from ..context import AppContext
from ..tasks import run_async
from ..theme import icons
from ..theme import tokens as t
from ..widgets.diff_view import DiffView
from .registry import PageSpec
from .split_page import SplitPage

log = logging.getLogger(__name__)


class _FileRow(QFrame):
    """One pending file."""

    def __init__(self, page: CfgFilesPage, item: ConfigFile) -> None:
        super().__init__(page)
        self.setObjectName("cfgRow")
        self._page = page
        self.item = item

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, t.SPACE_3)
        layout.setSpacing(t.SPACE_1)

        top = QHBoxLayout()
        top.setSpacing(t.SPACE_3)
        self._name = QLabel(item.name)
        self._name.setObjectName("cfgName")
        top.addWidget(self._name)
        self._counts = QLabel()
        self._counts.setProperty("role", "mono")
        top.addWidget(self._counts)
        top.addStretch(1)
        layout.addLayout(top)

        self._where = QLabel(str(item.directory))
        self._where.setProperty("role", "mono")
        layout.addWidget(self._where)

        self._owner = QLabel()
        self._owner.setProperty("role", "caption")
        layout.addWidget(self._owner)

        self.retranslate_ui()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802, ANN001 - Qt API
        self._page.select(self.item)
        super().mouseReleaseEvent(event)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "yes" if selected else "no")
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)

    def retranslate_ui(self) -> None:
        item = self.item
        if item.is_new_file:
            self._counts.setText(self.tr("new file"))
        else:
            self._counts.setText(f"+{item.added} −{item.removed}")
        self._owner.setText(
            self.tr("from {package}").format(package=item.owner)
            if item.owner
            else self.tr("no package claims this file")
        )


class CfgFilesPage(SplitPage):
    """Pending configuration files, their differences and the three answers."""

    def __init__(
        self, spec: PageSpec, context: AppContext, parent: QWidget | None = None
    ) -> None:
        super().__init__(spec, context, parent)

        self._items: tuple[ConfigFile, ...] = ()
        self._rows: list[_FileRow] = []
        self._selected: ConfigFile | None = None
        self._merging = False

        self._build_list_pane()
        self._build_detail_pane()
        self.retranslate_ui()

    # ------------------------------------------------------------ building --

    def _build_list_pane(self) -> None:
        header = QFrame()
        header.setObjectName("searchHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(t.SPACE_4, t.SPACE_4, t.SPACE_4, t.SPACE_4)
        header_layout.setSpacing(t.SPACE_1)
        self._list_title = QLabel()
        self._list_title.setProperty("role", "subheading")
        header_layout.addWidget(self._list_title)
        self._list_note = QLabel()
        self._list_note.setProperty("role", "caption")
        self._list_note.setWordWrap(True)
        header_layout.addWidget(self._list_note)
        self.list_layout.addWidget(header)

        self._rows_holder = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_holder)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)
        self._rows_layout.addStretch(1)
        self.list_layout.addWidget(self._rows_holder, 1)

    def _build_detail_pane(self) -> None:
        self._stack = QStackedWidget()
        self.detail_layout.addWidget(self._stack, 1)

        self._empty = QLabel()
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setProperty("role", "caption")
        self._empty.setWordWrap(True)
        self._stack.addWidget(self._empty)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(t.SPACE_4)

        heading = QHBoxLayout()
        heading.setSpacing(t.SPACE_3)
        self._icon = QLabel()
        heading.addWidget(self._icon)
        self._title = QLabel()
        self._title.setObjectName("packageAtom")
        self._title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        heading.addWidget(self._title)
        heading.addStretch(1)
        layout.addLayout(heading)

        self._paths = QLabel()
        self._paths.setProperty("role", "mono")
        self._paths.setWordWrap(True)
        self._paths.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._paths)

        self._diff = DiffView()
        layout.addWidget(self._diff, 1)

        self._editor = QPlainTextEdit()
        self._editor.setObjectName("mergeEditor")
        self._editor.setWordWrapMode(QTextOption.WrapMode.NoWrap)
        self._editor.hide()
        layout.addWidget(self._editor, 1)

        actions = QHBoxLayout()
        actions.setSpacing(t.SPACE_2)
        self._btn_keep = QPushButton()
        self._btn_keep.clicked.connect(lambda: self._decide("reject"))
        actions.addWidget(self._btn_keep)
        self._btn_take = QPushButton()
        self._btn_take.setProperty("variant", "primary")
        self._btn_take.clicked.connect(lambda: self._decide("accept"))
        actions.addWidget(self._btn_take)
        self._btn_merge = QPushButton()
        self._btn_merge.clicked.connect(self._toggle_merge)
        actions.addWidget(self._btn_merge)
        self._btn_save_merge = QPushButton()
        self._btn_save_merge.setProperty("variant", "primary")
        self._btn_save_merge.clicked.connect(lambda: self._decide("merge"))
        self._btn_save_merge.hide()
        actions.addWidget(self._btn_save_merge)
        actions.addStretch(1)
        layout.addLayout(actions)

        self._report = QLabel()
        self._report.setObjectName("writeReport")
        self._report.setWordWrap(True)
        self._report.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._report.hide()
        layout.addWidget(self._report)

        self._stack.addWidget(content)

    # -------------------------------------------------------------- data --

    def activated(self) -> None:
        self.reload()

    def reload(self) -> None:
        run_async(cfgfiles.find, self._on_found, self._on_find_failed)

    def _on_found(self, items: object) -> None:
        if not isinstance(items, tuple):
            return
        self._items = items

        while self._rows_layout.count() > 1:
            entry = self._rows_layout.takeAt(0)
            widget = entry.widget() if entry is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._rows = []

        for item in items:
            row = _FileRow(self, item)
            self._rows.append(row)
            self._rows_layout.insertWidget(len(self._rows) - 1, row)

        self.context.sidebar_badge.emit("cfg", str(len(items)) if items else "")
        if items:
            still_there = next(
                (
                    item
                    for item in items
                    if self._selected and item.candidate == self._selected.candidate
                ),
                items[0],
            )
            self.select(still_there)
        else:
            self._selected = None
            self._stack.setCurrentIndex(0)
        self.retranslate_ui()

    def _on_find_failed(self, error: Exception) -> None:
        log.error("Looking for configuration files failed: %s", error)

    def select(self, item: ConfigFile) -> None:
        self._selected = item
        self._merging = False
        self._report.hide()
        for row in self._rows:
            row.set_selected(row.item.candidate == item.candidate)
        self._diff.set_lines(cfgfiles.diff(item))
        self._stack.setCurrentIndex(1)
        self._refresh_detail()

    # ---------------------------------------------------------- deciding --

    def _toggle_merge(self) -> None:
        """Open the new version for editing, or put the diff back."""
        item = self._selected
        if item is None:
            return
        self._merging = not self._merging
        if self._merging:
            try:
                text = item.candidate.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:  # pragma: no cover - it vanished
                log.error("Could not read %s: %s", item.candidate, exc)
                self._merging = False
                return
            self._editor.setPlainText(text)
        self._diff.setVisible(not self._merging)
        self._editor.setVisible(self._merging)
        self._btn_save_merge.setVisible(self._merging)
        self.retranslate_ui()

    def _decide(self, decision: str) -> None:
        item = self._selected
        if item is None:
            return

        question = {
            "accept": self.tr(
                "Replace {target} with the version {package} brought?\n\n"
                "The file you have now is copied to /etc/config-archive first."
            ),
            "reject": self.tr(
                "Keep {target} as it is and discard the new version?\n\n"
                "{candidate} is deleted. Nothing else changes."
            ),
            "merge": self.tr(
                "Save what is in the editor as {target}?\n\n"
                "The file you have now is copied to /etc/config-archive first, and "
                "{candidate} is deleted."
            ),
        }[decision].format(
            target=item.target, candidate=item.candidate.name, package=item.owner or "?"
        )

        answer = QMessageBox.question(
            self,
            self.tr("Configuration file"),
            question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        fields: dict[str, object] = {"path": str(item.candidate), "decision": decision}
        if decision == "merge":
            fields["content"] = self._editor.toPlainText()

        self._set_busy(True)
        run_async(
            helper_client.request,
            self._on_decided,
            self._on_decide_failed,
            "cfg_apply",
            ensure_backup=self.context.backups.needs_backup(),
            **self.context.backup_options(),
            **fields,
        )

    def _set_busy(self, busy: bool) -> None:
        for button in (
            self._btn_keep,
            self._btn_take,
            self._btn_merge,
            self._btn_save_merge,
        ):
            button.setEnabled(not busy)

    def _on_decided(self, result: object) -> None:
        self._set_busy(False)
        data = getattr(result, "data", {}) or {}
        if getattr(result, "ok", False):
            self.context.backups.note(getattr(result, "backup", None))
            self.context.backups_changed.emit()
            self._report.setProperty("state", "ok")
            self._report.setText(self._success_text(data))
            self._merging = False
            self._diff.show()
            self._editor.hide()
            self._btn_save_merge.hide()
            self.reload()
        elif getattr(result, "cancelled", False):
            self._report.setProperty("state", "err")
            self._report.setText(self.tr("Cancelled — nothing was changed."))
        else:
            self._report.setProperty("state", "err")
            self._report.setText(
                self.tr("Nothing was changed: {error}").format(
                    error=getattr(result, "error", "")
                )
            )
        self._report.show()
        style = self._report.style()
        if style is not None:
            style.unpolish(self._report)
            style.polish(self._report)

    def _success_text(self, data: dict) -> str:
        decision = data.get("decision", "")
        target = data.get("target", "")
        archived = data.get("archived")
        if decision == "reject":
            return self.tr("Kept your version of {target}.").format(target=target)
        text = (
            self.tr("Saved the merged version as {target}.")
            if decision == "merge"
            else self.tr("Replaced {target} with the new version.")
        ).format(target=target)
        if archived:
            text += "\n" + self.tr("The previous version is at {path}.").format(path=archived)
        return text

    def _on_decide_failed(self, error: Exception) -> None:
        self._set_busy(False)
        log.error("Applying the configuration file failed: %s", error)
        self._report.setProperty("state", "err")
        self._report.setText(str(error))
        self._report.show()

    # -------------------------------------------------------------- i18n --

    def _refresh_detail(self) -> None:
        item = self._selected
        if item is None:
            return
        size = max(14, round(self.fontMetrics().height() * 1.05))
        self._icon.setPixmap(
            icons.tinted_pixmap("files", t.WARN, size, self.devicePixelRatioF())
        )
        self._title.setText(item.name)
        self._paths.setText(
            self.tr("yours: {target}\nnew:   {candidate}").format(
                target=item.target, candidate=item.candidate
            )
        )
        self._btn_merge.setText(
            self.tr("Back to the difference") if self._merging else self.tr("Merge by hand…")
        )
        self._btn_take.setEnabled(not self._merging)
        self._btn_keep.setEnabled(not self._merging)

    def retranslate_ui(self) -> None:
        self._list_title.setText(self.tr("Waiting for a decision"))
        self._list_note.setText(
            self.tr(
                "Portage never overwrites a configuration file you have edited. It writes "
                "the new version beside it and leaves both, which is what these are."
            )
        )
        self._empty.setText(
            self.tr("Nothing is waiting. Every configuration file is as you left it.")
        )
        self._btn_keep.setText(self.tr("Keep mine"))
        self._btn_take.setText(self.tr("Take the new one"))
        self._btn_save_merge.setText(self.tr("Save what I merged"))
        for row in self._rows:
            row.retranslate_ui()
        self._diff.retranslate_ui()
        self._refresh_detail()
