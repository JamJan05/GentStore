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

"""Table model for the update preview.

One row per package ``emerge`` intends to touch. The columns are the questions
people actually ask of that list: what, from which version to which, what
changed about its USE flags, how big the download is, and whether it will be
compiled or unpacked from a binary.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt

from ..core.emerge_parse import Action, MergeRow

#: Column order, and the keys the view turns into headings.
COLUMNS = ("package", "version", "use", "size", "source")

_SIZE_UNITS = ("B", "KiB", "MiB", "GiB")


def format_size(size: int | None) -> str:
    if size is None:
        return ""
    value = float(size)
    for unit in _SIZE_UNITS:
        if value < 1024 or unit == _SIZE_UNITS[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return ""  # pragma: no cover - unreachable


class MergePreviewModel(QAbstractTableModel):
    """The rows of an ``emerge -pv`` run."""

    RowRole = Qt.ItemDataRole.UserRole + 1
    ActionRole = Qt.ItemDataRole.UserRole + 2

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[MergeRow] = []
        self._headings: tuple[str, ...] = COLUMNS

    def set_rows(self, rows: Sequence[MergeRow]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def set_headings(self, headings: Sequence[str]) -> None:
        """Called from the view's ``retranslate_ui``; the model holds no strings."""
        self._headings = tuple(headings)
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, len(COLUMNS) - 1)

    def row_at(self, row: int) -> MergeRow | None:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    # -- QAbstractTableModel ----------------------------------------------

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802 - Qt API
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802 - Qt API
        if parent is not None and parent.isValid():
            return 0
        return len(COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: D102
        if not index.isValid():
            return None
        row = self._rows[index.row()]

        if role == self.RowRole:
            return row
        if role == self.ActionRole:
            return row.action
        if role == Qt.ItemDataRole.TextAlignmentRole and COLUMNS[index.column()] == "size":
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ToolTipRole:
            return row.raw
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        column = COLUMNS[index.column()]
        if column == "package":
            return row.cp
        if column == "version":
            return row.version_change
        if column == "use":
            # Only the flags that changed: the full list is in the tooltip, and
            # a column showing forty unchanged flags shows nothing at all.
            return " ".join(item.display for item in row.changed_use)
        if column == "size":
            return format_size(row.size)
        if column == "source":
            return self._headings[-1] if row.is_binary else ""
        return None

    def headerData(  # noqa: N802 - Qt API
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation is not Qt.Orientation.Horizontal or role != Qt.ItemDataRole.DisplayRole:
            return None
        return self._headings[section] if section < len(self._headings) else ""

    # -- summaries ---------------------------------------------------------

    def counts(self) -> dict[Action, int]:
        totals: dict[Action, int] = {}
        for row in self._rows:
            totals[row.action] = totals.get(row.action, 0) + 1
        return totals

    def total_size(self) -> int:
        return sum(row.size or 0 for row in self._rows)
