"""Putting a backup of ``/etc/portage`` back — after seeing what that means.

Restoring is a change to the system like any other, so it gets the same
treatment as every other change in Gentstore: shown before it happens
(Docs/04-privileges.md §5). "Shown" here is a list of the files that would be
restored, deleted or replaced, and the difference for any one of them.

The list matters because a backup is not obviously old. Ten of them sit in
``/etc`` with timestamps for names, and the only way to tell which one is
wanted is to see what going back to it would undo.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core import backup as backup_core
from ...core.backup import BackupInfo, Change
from ..theme import tokens as t
from .diff_view import DiffView


class RestoreDialog(QDialog):
    """Pick a backup, see what it would change, then decide."""

    def __init__(
        self, backups: tuple[BackupInfo, ...], current: Path, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._backups = backups
        self._current = current
        self._changes: tuple[Change, ...] = ()
        self.setModal(True)
        self.resize(940, 660)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_6, t.SPACE_4, t.SPACE_6, t.SPACE_4)
        layout.setSpacing(t.SPACE_3)

        self._intro = QLabel()
        self._intro.setWordWrap(True)
        self._intro.setProperty("role", "body")
        layout.addWidget(self._intro)

        panes = QHBoxLayout()
        panes.setSpacing(t.SPACE_4)

        left = QVBoxLayout()
        left.setSpacing(t.SPACE_2)
        self._backups_label = QLabel()
        self._backups_label.setProperty("role", "section")
        left.addWidget(self._backups_label)
        self._backup_list = QListWidget()
        self._backup_list.setFixedWidth(220)
        for item in backups:
            entry = QListWidgetItem(item.label)
            entry.setData(Qt.ItemDataRole.UserRole, item)
            self._backup_list.addItem(entry)
        self._backup_list.currentRowChanged.connect(self._on_backup_chosen)
        left.addWidget(self._backup_list, 1)

        self._changes_label = QLabel()
        self._changes_label.setProperty("role", "section")
        left.addWidget(self._changes_label)
        self._change_list = QListWidget()
        self._change_list.setFixedWidth(220)
        self._change_list.currentRowChanged.connect(self._on_change_chosen)
        left.addWidget(self._change_list, 2)
        panes.addLayout(left)

        self._diff = DiffView()
        panes.addWidget(self._diff, 1)
        layout.addLayout(panes, 1)

        self._summary = QLabel()
        self._summary.setProperty("role", "mono")
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self.retranslate_ui()
        if backups:
            self._backup_list.setCurrentRow(0)

    # -- the answer --------------------------------------------------------

    @property
    def chosen(self) -> BackupInfo | None:
        item = self._backup_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    # -- reacting ----------------------------------------------------------

    def _on_backup_chosen(self, _row: int) -> None:
        chosen = self.chosen
        self._change_list.clear()
        self._diff.clear()
        if chosen is None:
            self._changes = ()
            self.retranslate_ui()
            return

        self._changes = backup_core.compare(chosen.path, self._current)
        for change in self._changes:
            entry = QListWidgetItem(f"{_MARK[change.kind]} {change.relative}")
            entry.setData(Qt.ItemDataRole.UserRole, change)
            self._change_list.addItem(entry)
        if self._changes:
            self._change_list.setCurrentRow(0)
        self.retranslate_ui()

    def _on_change_chosen(self, _row: int) -> None:
        chosen = self.chosen
        item = self._change_list.currentItem()
        if chosen is None or item is None:
            self._diff.clear()
            return
        change: Change = item.data(Qt.ItemDataRole.UserRole)
        self._diff.set_lines(
            backup_core.file_diff(chosen.path, self._current, change.relative)
        )

    # -- wording -----------------------------------------------------------

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Restore /etc/portage"))
        self._intro.setText(
            self.tr(
                "Restoring replaces {path} with the copy you pick. The state you have now "
                "is backed up first, so this can itself be undone."
            ).format(path=self._current)
        )
        self._backups_label.setText(self.tr("Backups"))
        self._changes_label.setText(self.tr("What would change"))
        self._diff.set_labels(self.tr("now"), self.tr("the backup"))

        if not self._backups:
            self._summary.setText(self.tr("There are no backups yet."))
        elif not self._changes:
            self._summary.setText(
                self.tr("This backup matches what you have now — nothing would change.")
            )
        else:
            kinds = {kind: 0 for kind in ("added", "removed", "changed")}
            for change in self._changes:
                kinds[change.kind] += 1
            self._summary.setText(
                "   ·   ".join(
                    (
                        self.tr("%n file(s) restored", "", kinds["added"]),
                        self.tr("%n deleted", "", kinds["removed"]),
                        self.tr("%n replaced", "", kinds["changed"]),
                    )
                )
            )

        ok = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(self.tr("Restore"))
            ok.setProperty("variant", "danger")
            ok.setEnabled(bool(self._backups))
        cancel = self._buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel is not None:
            cancel.setText(self.tr("Cancel"))

    def changeEvent(self, event: QEvent | None) -> None:  # noqa: N802 - Qt API
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)


#: The three shapes a restore can take, marked the way a diff marks them.
_MARK = {"added": "+", "removed": "−", "changed": "~"}
