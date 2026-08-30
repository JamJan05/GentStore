"""The repository marker: ``::gentoo`` against ``::guru`` at a glance.

Colour carries the meaning (Docs/02-ui-design.md §5): the main repository is
neutral because it is the unremarkable case, an overlay is tinted with the
accent because it is the one worth noticing. The same two rules paint the badge
next to a package title and the badge inside a result row, so the drawing lives
in a function the item delegate can call directly.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath
from PyQt6.QtWidgets import QSizePolicy, QWidget

from ..theme import tokens as t

_PADDING_H = 5
_PADDING_V = 1


def badge_colours(official: bool) -> tuple[str, str]:
    """Background and foreground for a repository badge."""
    if official:
        return t.NEUTRAL_900, t.NEUTRAL_400
    return t.ACCENT_800, t.ACCENT_200


def badge_size(text: str, metrics: QFontMetrics) -> QSize:
    return QSize(
        metrics.horizontalAdvance(text) + 2 * _PADDING_H,
        metrics.height() + 2 * _PADDING_V,
    )


def draw_badge(
    painter: QPainter, left: float, centre_y: float, text: str, official: bool
) -> QRectF:
    """Paint a badge whose left edge is at *left*, vertically centred.

    Uses the painter's current font, and returns the rectangle it covered so the
    caller can lay out whatever comes next.
    """
    metrics = painter.fontMetrics()
    size = badge_size(text, metrics)
    rect = QRectF(left, centre_y - size.height() / 2, size.width(), size.height())

    background, foreground = badge_colours(official)
    path = QPainterPath()
    path.addRoundedRect(rect, 3, 3)
    painter.fillPath(path, QColor(background))
    painter.setPen(QColor(foreground))
    painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text)
    return rect


class RepoBadge(QWidget):
    """Stand-alone badge for the package details panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = ""
        self._official = True
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_repository(self, name: str, official: bool) -> None:
        """Show ``::name``; *official* picks the neutral or the accented look."""
        self._text = f"::{name}" if name else ""
        self._official = official
        self.setVisible(bool(name))
        self.updateGeometry()
        self.update()

    def _font(self) -> QFont:
        font = QFont(self.font())
        font.setPixelSize(max(9, round(self.fontMetrics().height() * 0.8)))
        return font

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        if not self._text:
            return QSize(0, 0)
        return badge_size(self._text, QFontMetrics(self._font()))

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001 - Qt API
        if not self._text:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self._font())
        draw_badge(painter, 0.5, self.rect().center().y() + 0.5, self._text, self._official)
        painter.end()
