"""The search-result list: a view plus the delegate that paints its rows.

Each row packs four different pieces of information — where the package lives,
what it does, which version is on offer and whether it is installed — into about
seventy pixels. Stock item widgets cannot do that, and building a widget per row
would rule out showing hundreds of results, so the rows are painted.
"""

from __future__ import annotations

from PyQt6.QtCore import QModelIndex, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath
from PyQt6.QtWidgets import QListView, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from ...core.packages import PackageState, PackageSummary
from ...models.packages import PackageListModel
from ..theme import tokens as t
from .repo_badge import draw_badge

#: Font sizes as a fraction of the row's line height, so the list follows the
#: interface scale the same way the hand-painted chrome does.
_RATIO_NAME = 0.78
_RATIO_DESCRIPTION = 0.72
_RATIO_META = 0.655
_RATIO_BADGE = 0.62

_MARK_WIDTH = 2


class PackageDelegate(QStyledItemDelegate):
    """Paints one search result."""

    def __init__(self, official_repo: str = "gentoo", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._official_repo = official_repo

    def set_official_repository(self, name: str) -> None:
        """Which repository counts as the main one, for badge colouring."""
        self._official_repo = name

    # -- metrics -----------------------------------------------------------

    def _font(self, base: QFont, ratio: float, *, mono: bool = False, bold: bool = False) -> QFont:
        font = QFont(base)
        if mono:
            font.setFamilies(list(t.MONO_FONT_FAMILIES))
        font.setPixelSize(max(8, round(QFontMetrics(base).height() * ratio)))
        font.setBold(bold)
        return font

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        base = option.font
        name = QFontMetrics(self._font(base, _RATIO_NAME, mono=True)).height()
        description = QFontMetrics(self._font(base, _RATIO_DESCRIPTION)).height()
        meta = QFontMetrics(self._font(base, _RATIO_META, mono=True)).height()
        return QSize(
            t.LIST_PANE_WIDTH,
            2 * t.SPACE_3 + name + t.SPACE_1 + description + t.SPACE_2 + meta,
        )

    # -- painting ----------------------------------------------------------

    def paint(  # noqa: D102 - Qt API
        self, painter: QPainter | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        if painter is None:
            return
        summary = index.data(PackageListModel.SummaryRole)
        if not isinstance(summary, PackageSummary):
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        rect = QRectF(option.rect).adjusted(t.SPACE_1, 0, -t.SPACE_1, 0)

        if selected or hovered:
            path = QPainterPath()
            path.addRoundedRect(rect, t.RADIUS_SM, t.RADIUS_SM)
            painter.fillPath(path, QColor(t.ACCENT_900 if selected else t.NEUTRAL_900))
            if selected:
                painter.save()
                painter.setClipPath(path)
                painter.fillRect(
                    QRectF(rect.left(), rect.top(), _MARK_WIDTH, rect.height()), QColor(t.ACCENT)
                )
                painter.restore()

        inner = rect.adjusted(t.SPACE_3, t.SPACE_3, -t.SPACE_3, -t.SPACE_3)
        base = option.font

        y = self._paint_title(painter, inner, base, summary, selected)
        y = self._paint_description(painter, inner, base, summary.description, y)
        self._paint_meta(painter, inner, base, index.data(PackageListModel.StateRole), y)

        painter.restore()

    def _paint_title(
        self,
        painter: QPainter,
        inner: QRectF,
        base: QFont,
        summary: PackageSummary,
        selected: bool,
    ) -> float:
        name_font = self._font(base, _RATIO_NAME, mono=True, bold=True)
        category_font = self._font(base, _RATIO_NAME, mono=True)
        badge_font = self._font(base, _RATIO_BADGE, mono=True)

        line_height = QFontMetrics(name_font).height()
        line = QRectF(inner.left(), inner.top(), inner.width(), line_height)

        # The badge is placed first: it is the one element that must never be
        # cut, so the name is elided against whatever space is left over.
        repo = summary.repos[0] if summary.repos else ""
        badge_left = inner.right()
        if repo:
            painter.setFont(badge_font)
            text = f"::{repo}"
            width = QFontMetrics(badge_font).horizontalAdvance(text) + 10
            badge_left = inner.right() - width
            draw_badge(
                painter,
                badge_left,
                line.center().y(),
                text,
                repo == self._official_repo,
            )

        painter.setFont(category_font)
        painter.setPen(QColor(t.NEUTRAL_600))
        category = f"{summary.category}/"
        category_width = QFontMetrics(category_font).horizontalAdvance(category)
        painter.drawText(
            QRectF(line.left(), line.top(), category_width, line_height),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            category,
        )

        painter.setFont(name_font)
        painter.setPen(QColor(t.TEXT if selected else t.NEUTRAL_200))
        available = max(0.0, badge_left - t.SPACE_2 - (line.left() + category_width))
        name = QFontMetrics(name_font).elidedText(
            summary.name, Qt.TextElideMode.ElideRight, int(available)
        )
        painter.drawText(
            QRectF(line.left() + category_width, line.top(), available, line_height),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            name,
        )
        return line.bottom() + t.SPACE_1

    def _paint_description(
        self, painter: QPainter, inner: QRectF, base: QFont, description: str, y: float
    ) -> float:
        font = self._font(base, _RATIO_DESCRIPTION)
        metrics = QFontMetrics(font)
        painter.setFont(font)
        painter.setPen(QColor(t.NEUTRAL_500))
        rect = QRectF(inner.left(), y, inner.width(), metrics.height())
        painter.drawText(
            rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            metrics.elidedText(description, Qt.TextElideMode.ElideRight, int(inner.width())),
        )
        return rect.bottom() + t.SPACE_2

    def _paint_meta(
        self, painter: QPainter, inner: QRectF, base: QFont, state: object, y: float
    ) -> None:
        if not isinstance(state, PackageState):
            return
        font = self._font(base, _RATIO_META, mono=True)
        metrics = QFontMetrics(font)
        painter.setFont(font)

        version = self._version_text(state)
        painter.setPen(QColor(t.NEUTRAL_600))
        rect = QRectF(inner.left(), y, inner.width(), metrics.height())
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                         version)

        label, colour = self._state_text(state)
        if not label:
            return
        left = inner.left() + metrics.horizontalAdvance(version) + t.SPACE_3
        painter.setPen(QColor(colour))
        painter.drawText(
            QRectF(left, y, max(0.0, inner.right() - left), metrics.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            metrics.elidedText(label, Qt.TextElideMode.ElideRight, int(inner.right() - left)),
        )

    def _version_text(self, state: PackageState) -> str:
        if state.has_update:
            return f"{state.installed_version} → {state.available_version}"
        return state.installed_version or state.available_version or state.newest_version or ""

    def _state_text(self, state: PackageState) -> tuple[str, str]:
        """The short status word and its colour. Translated in the view's context."""
        if state.is_blocked:
            return self.tr("blocked"), t.ERR
        if state.has_update:
            return self.tr("update available"), t.WARN
        if state.is_installed:
            return self.tr("installed"), t.NEUTRAL_600
        return "", t.NEUTRAL_600


class PackageListView(QListView):
    """The results pane. Nothing but a view with the delegate already fitted."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.delegate = PackageDelegate(parent=self)
        self.setItemDelegate(self.delegate)
        self.setObjectName("packageList")
        self.setFrameShape(QListView.Shape.NoFrame)
        self.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setUniformItemSizes(True)
        self.setMouseTracking(True)  # so the delegate sees State_MouseOver
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
