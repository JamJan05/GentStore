"""List model behind the search results."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

from PyQt6.QtCore import QAbstractListModel, QModelIndex, QObject, Qt

from ..core.packages import PackageState, PackageSummary, package_state

log = logging.getLogger(__name__)

_EMPTY_STATE = PackageState(
    cp="", installed_version=None, available_version=None, newest_version=None
)


class PackageListModel(QAbstractListModel):
    """Search results, one :class:`PackageSummary` per row.

    The summary carries what the index already knows — name, description,
    repositories. The version line needs a second, more expensive question
    (:func:`~gentstore.core.packages.package_state`), so it is asked lazily, for
    the rows a view actually paints, and the answers are cached. Populating the
    twenty-odd visible rows costs about 10 ms; doing it for the whole tree up
    front would cost seven seconds.
    """

    SummaryRole = Qt.ItemDataRole.UserRole + 1
    StateRole = Qt.ItemDataRole.UserRole + 2
    CpRole = Qt.ItemDataRole.UserRole + 3

    def __init__(
        self,
        state_provider: Callable[[str], PackageState] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._results: list[PackageSummary] = []
        self._states: dict[str, PackageState] = {}
        self._provider = state_provider or package_state

    # -- contents ----------------------------------------------------------

    def set_results(self, results: Sequence[PackageSummary]) -> None:
        self.beginResetModel()
        self._results = list(results)
        self.endResetModel()

    def set_state_provider(self, provider: Callable[[str], PackageState] | None) -> None:
        """Change the question the version line asks, and ask it again.

        The search screen uses this to narrow the line to one repository while a
        repository filter is on: the same row means something different when
        only ``::gentoo`` is on the table.
        """
        self._provider = provider or package_state
        self.invalidate_states()

    def invalidate_states(self) -> None:
        """Forget the cached version lines — after an install or a sync."""
        self._states.clear()
        if self._results:
            self.dataChanged.emit(
                self.index(0), self.index(len(self._results) - 1), [self.StateRole]
            )

    def summary_at(self, row: int) -> PackageSummary | None:
        return self._results[row] if 0 <= row < len(self._results) else None

    def row_of(self, cp: str) -> int:
        """Row showing *cp*, or ``-1``."""
        return next((i for i, item in enumerate(self._results) if item.cp == cp), -1)

    # -- QAbstractListModel ------------------------------------------------

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802 - Qt API
        if parent is not None and parent.isValid():
            return 0
        return len(self._results)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: D102
        if not index.isValid():
            return None
        summary = self._results[index.row()]
        if role == self.SummaryRole:
            return summary
        if role == self.CpRole:
            return summary.cp
        if role == self.StateRole:
            return self._state(summary.cp)
        if role == Qt.ItemDataRole.DisplayRole:
            return summary.cp
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{summary.cp}\n{summary.description}"
        return None

    def _state(self, cp: str) -> PackageState:
        cached = self._states.get(cp)
        if cached is not None:
            return cached
        try:
            state = self._provider(cp)
        except Exception:  # pragma: no cover - a repository disappearing mid-scroll
            log.warning("Could not read the state of %s", cp, exc_info=True)
            state = _EMPTY_STATE
        self._states[cp] = state
        return state
