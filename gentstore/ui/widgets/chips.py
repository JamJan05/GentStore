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

"""Small pill-shaped controls used in the toolbar and in filter rows.

Qt has no stock widget with the outlined-pill look the design uses, and pushing
a QPushButton into that shape means fighting the style engine over metrics. Two
short painted widgets are cheaper and behave identically at every font scale.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QMouseEvent, QPainter, QPainterPath
from PyQt6.QtWidgets import QSizePolicy, QWidget

from ..theme import icons
from ..theme import tokens as t


class _ClickableChip(QWidget):
    """Shared behaviour: hover tracking, click signal, rounded background."""

    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hovered = False
        self._checked = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, checked: bool) -> None:
        if checked != self._checked:
            self._checked = checked
            self.update()

    def event(self, event: QEvent | None) -> bool:  # noqa: D102 - Qt API
        if event is not None:
            if event.type() == QEvent.Type.HoverEnter:
                self._hovered = True
                self.update()
            elif event.type() == QEvent.Type.HoverLeave:
                self._hovered = False
                self.update()
        return super().event(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802 - Qt API
        if (
            event is not None
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def changeEvent(self, event: QEvent | None) -> None:  # noqa: N802 - Qt API
        if event is not None and event.type() == QEvent.Type.FontChange:
            self.updateGeometry()
            self.update()
        super().changeEvent(event)

    def _paint_frame(self, painter: QPainter, bg: str | None, border: str | None) -> QRectF:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, t.RADIUS_SM, t.RADIUS_SM)
        if bg is not None:
            painter.fillPath(path, QColor(bg))
        if border is not None:
            painter.setPen(QColor(border))
            painter.drawPath(path)
        return rect


class Pill(_ClickableChip):
    """A compact, checkable text chip — used for mode and filter selection.

    An optional dimmed suffix carries a qualifier that should not compete with
    the label itself: the keyword state next to a version number, say.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = ""
        self._suffix = ""

    def set_text(self, text: str) -> None:
        self._text = text
        self.updateGeometry()
        self.update()

    def set_suffix(self, suffix: str) -> None:
        self._suffix = suffix
        self.updateGeometry()
        self.update()

    def _font(self) -> QFont:
        font = QFont(self.font())
        font.setPixelSize(max(9, round(self.fontMetrics().height() * 0.78)))
        return font

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        metrics = QFontMetrics(self._font())
        width = metrics.horizontalAdvance(self._full_text()) + 2 * t.SPACE_3
        return QSize(width, metrics.height() + 2 * t.SPACE_1 + 2)

    def _full_text(self) -> str:
        return f"{self._text}  {self._suffix}" if self._suffix else self._text

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001 - Qt API
        painter = QPainter(self)
        painter.setFont(self._font())
        if self._checked:
            bg, border, fg = t.ACCENT_900, t.ACCENT, t.ACCENT_200
        elif self._hovered:
            bg, border, fg = t.NEUTRAL_900, t.NEUTRAL_700, t.NEUTRAL_400
        else:
            bg, border, fg = None, t.NEUTRAL_800, t.NEUTRAL_500
        rect = self._paint_frame(painter, bg, border)

        if not self._suffix:
            painter.setPen(QColor(fg))
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), self._text)
            painter.end()
            return

        # Label and suffix are drawn separately so the suffix can be dimmer;
        # together they are centred as one block.
        metrics = painter.fontMetrics()
        gap = metrics.horizontalAdvance("  ")
        label_width = metrics.horizontalAdvance(self._text)
        suffix_width = metrics.horizontalAdvance(self._suffix)
        left = rect.center().x() - (label_width + gap + suffix_width) / 2
        painter.setPen(QColor(fg))
        painter.drawText(
            QRectF(left, rect.top(), label_width, rect.height()),
            int(Qt.AlignmentFlag.AlignVCenter),
            self._text,
        )
        painter.setPen(QColor(t.NEUTRAL_600))
        painter.drawText(
            QRectF(left + label_width + gap, rect.top(), suffix_width, rect.height()),
            int(Qt.AlignmentFlag.AlignVCenter),
            self._suffix,
        )
        painter.end()


class ToggleChip(_ClickableChip):
    """Checkbox-like chip: icon, label and a dimmed suffix showing the state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = ""
        self._suffix = ""

    def set_text(self, text: str) -> None:
        self._text = text
        self.updateGeometry()
        self.update()

    def set_suffix(self, suffix: str) -> None:
        self._suffix = suffix
        self.updateGeometry()
        self.update()

    def _icon_size(self) -> int:
        return max(13, round(self.fontMetrics().height() * 0.95))

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        metrics = self.fontMetrics()
        width = (
            t.SPACE_3
            + self._icon_size()
            + t.SPACE_2
            + metrics.horizontalAdvance(self._text)
            + (t.SPACE_2 + metrics.horizontalAdvance(self._suffix) if self._suffix else 0)
            + t.SPACE_3
        )
        return QSize(width, metrics.height() + 2 * t.SPACE_2)

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001 - Qt API
        painter = QPainter(self)
        if self._checked:
            border, fg, icon_name = t.ACCENT, t.ACCENT_200, "check-square"
        else:
            border, fg, icon_name = t.NEUTRAL_800, t.NEUTRAL_400, "square"
        bg = t.NEUTRAL_900 if self._hovered and not self._checked else None
        rect = self._paint_frame(painter, bg, border)

        size = self._icon_size()
        pixmap = icons.tinted_pixmap(icon_name, fg, size, self.devicePixelRatioF())
        x = rect.left() + t.SPACE_3
        if not pixmap.isNull():
            painter.drawPixmap(int(x), int(rect.center().y() - size / 2 + 0.5), pixmap)
        x += size + t.SPACE_2

        metrics = painter.fontMetrics()
        painter.setPen(QColor(fg))
        text_rect = QRectF(x, rect.top(), metrics.horizontalAdvance(self._text), rect.height())
        painter.drawText(text_rect, int(Qt.AlignmentFlag.AlignVCenter), self._text)

        if self._suffix:
            x = text_rect.right() + t.SPACE_2
            painter.setPen(QColor(t.NEUTRAL_600))
            suffix_rect = QRectF(
                x, rect.top(), metrics.horizontalAdvance(self._suffix), rect.height()
            )
            painter.drawText(suffix_rect, int(Qt.AlignmentFlag.AlignVCenter), self._suffix)
        painter.end()
