"""One row in the sidebar.

Drawn by hand rather than assembled from stock widgets: the row needs a rounded
highlight, a 2 px accent bar clipped to that rounding, a tinted icon and an
optional count badge — a combination that is far shorter to paint than to coax
out of a stylesheet.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPainterPath
from PyQt6.QtWidgets import QSizePolicy, QWidget

from ..theme import icons
from ..theme import tokens as t

_ROW_PADDING_V = 1
_ROW_HEIGHT = 30
_BADGE_PADDING_H = 5


class NavItem(QWidget):
    """A clickable sidebar entry with icon, label and optional badge."""

    activated = pyqtSignal(str)

    def __init__(self, page_id: str, icon_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.page_id = page_id
        self._icon_name = icon_name
        self._label = ""
        self._badge = ""
        self._active = False
        self._hovered = False

        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(_ROW_HEIGHT)

    # -- state -------------------------------------------------------------

    def set_label(self, text: str) -> None:
        self._label = text
        self.update()

    def set_badge(self, text: str) -> None:
        """Set the count badge; an empty string hides it."""
        self._badge = text
        self.update()

    def set_active(self, active: bool) -> None:
        if active != self._active:
            self._active = active
            self.update()

    def is_active(self) -> bool:
        return self._active

    # -- interaction -------------------------------------------------------

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
            self.activated.emit(self.page_id)
        super().mouseReleaseEvent(event)

    def changeEvent(self, event: QEvent | None) -> None:  # noqa: N802 - Qt API
        if event is not None and event.type() == QEvent.Type.FontChange:
            self.setFixedHeight(max(_ROW_HEIGHT, self.fontMetrics().height() + 2 * t.SPACE_2))
        super().changeEvent(event)

    # -- painting ----------------------------------------------------------

    def _icon_size(self) -> int:
        return max(14, round(self.fontMetrics().height() * 1.05))

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(
            t.SPACE_2, _ROW_PADDING_V, -t.SPACE_2, -_ROW_PADDING_V
        )
        path = QPainterPath()
        path.addRoundedRect(rect, t.RADIUS_SM, t.RADIUS_SM)

        if self._active:
            painter.fillPath(path, QColor(t.ACCENT_900))
        elif self._hovered:
            painter.fillPath(path, QColor(t.NEUTRAL_900))

        if self._active:
            painter.save()
            painter.setClipPath(path)
            painter.fillRect(QRectF(rect.left(), rect.top(), 2, rect.height()), QColor(t.ACCENT))
            painter.restore()

        if self._active:
            fg = t.TEXT
        elif self._hovered:
            fg = t.NEUTRAL_300
        else:
            fg = t.NEUTRAL_400

        size = self._icon_size()
        pixmap = icons.tinted_pixmap(self._icon_name, fg, size, self.devicePixelRatioF())
        icon_x = rect.left() + t.SPACE_3
        if not pixmap.isNull():
            painter.drawPixmap(
                int(icon_x), int(rect.center().y() - size / 2 + 0.5), pixmap
            )

        text_left = icon_x + size + t.SPACE_3
        text_right = rect.right() - t.SPACE_3

        if self._badge:
            badge_font = QFont(self.font())
            badge_font.setPixelSize(max(9, round(self.fontMetrics().height() * 0.62)))
            painter.setFont(badge_font)
            metrics = painter.fontMetrics()
            width = metrics.horizontalAdvance(self._badge) + 2 * _BADGE_PADDING_H
            height = metrics.height() + 1
            badge_rect = QRectF(
                rect.right() - t.SPACE_3 - width,
                rect.center().y() - height / 2,
                width,
                height,
            )
            badge_path = QPainterPath()
            badge_path.addRoundedRect(badge_rect, height / 2, height / 2)
            painter.fillPath(badge_path, QColor(t.ACCENT_800))
            painter.setPen(QColor(t.ACCENT_200))
            painter.drawText(badge_rect, int(Qt.AlignmentFlag.AlignCenter), self._badge)
            text_right = badge_rect.left() - t.SPACE_2

        painter.setFont(self.font())
        painter.setPen(QColor(fg))
        text_rect = QRectF(text_left, rect.top(), max(0.0, text_right - text_left), rect.height())
        elided = painter.fontMetrics().elidedText(
            self._label, Qt.TextElideMode.ElideRight, int(text_rect.width())
        )
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elided,
        )
        painter.end()
