"""The layout most screens share: a narrow list on the left, details on the right.

Six of the nine screens are variations on it (Docs/02-ui-design.md §4), so the
frame, the divider, the fixed 352 px width and the scrolling behaviour of the
details side are settled once here. Subclasses only fill
:attr:`list_layout` and :attr:`detail_layout`.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..context import AppContext
from ..theme import tokens as t
from .base import Page
from .registry import PageSpec


class SplitPage(Page):
    """Two-pane screen. The list keeps its width; the details take the rest."""

    def __init__(
        self, spec: PageSpec, context: AppContext, parent: QWidget | None = None
    ) -> None:
        super().__init__(spec, context, parent)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.list_pane = QFrame()
        self.list_pane.setObjectName("listPane")
        self.list_pane.setFixedWidth(t.LIST_PANE_WIDTH)
        self.list_layout = QVBoxLayout(self.list_pane)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        outer.addWidget(self.list_pane)

        # The details side scrolls as a whole: its content is a stack of blocks
        # of unpredictable height (description, versions, later USE flags), and
        # scrolling them independently would make the screen hard to follow.
        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setObjectName("detailPane")
        # Details reflow to the available width; they never scroll sideways.
        self.detail_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.detail = QWidget()
        self.detail.setObjectName("detailContent")
        self.detail_layout = QVBoxLayout(self.detail)
        self.detail_layout.setContentsMargins(t.SPACE_8, t.SPACE_6, t.SPACE_8, t.SPACE_8)
        self.detail_layout.setSpacing(t.SPACE_6)
        self.detail_scroll.setWidget(self.detail)
        outer.addWidget(self.detail_scroll, 1)

    def set_list_width(self, width: int) -> None:
        """Widen the list pane — the repositories screen uses 512 px."""
        self.list_pane.setFixedWidth(width)
