"""Gentoo news items, with the reason each one is being shown.

``emerge`` says "32 news items need reading" and leaves it there. The useful
part is not the count but *why* an item concerns this machine: because
``sys-kernel/dracut`` is installed, because of the profile in use, because of
the architecture. That reason is on every row, and it is what makes a list of
thirty items readable in a few seconds.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...core.news import NewsItem
from ..theme import tokens as t
from .clickable_label import ClickableLabel


class NewsEntry(QFrame):
    """One item: heading, why it applies, and the text on demand."""

    def __init__(self, item: NewsItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("newsEntry")
        self.setProperty("unread", "yes" if item.unread else "no")
        self._item = item
        self._expanded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, t.SPACE_3)
        layout.setSpacing(t.SPACE_1)

        top = QHBoxLayout()
        top.setSpacing(t.SPACE_3)

        self._date = QLabel(item.posted.isoformat() if item.posted else "")
        self._date.setProperty("role", "mono")
        top.addWidget(self._date)

        self._title = QLabel(item.title)
        self._title.setObjectName("newsTitle")
        self._title.setWordWrap(True)
        top.addWidget(self._title, 1)

        self._state = QLabel()
        self._state.setProperty("role", "caption")
        top.addWidget(self._state)

        self._toggle = ClickableLabel()
        self._toggle.setProperty("role", "mono-accent")
        self._toggle.clicked.connect(self._flip)
        top.addWidget(self._toggle)
        layout.addLayout(top)

        self._why = QLabel()
        self._why.setProperty("role", "mono")
        self._why.setWordWrap(True)
        layout.addWidget(self._why)

        self._body = QLabel(item.body)
        self._body.setObjectName("newsBody")
        self._body.setWordWrap(True)
        self._body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._body.hide()
        layout.addWidget(self._body)

        self.retranslate_ui()

    def _flip(self) -> None:
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        self._toggle.setText(self._toggle_text())

    def _toggle_text(self) -> str:
        return self.tr("Collapse") if self._expanded else self.tr("Read")

    def retranslate_ui(self) -> None:
        item = self._item
        self._state.setText(self.tr("unread") if item.unread else "")
        self._toggle.setText(self._toggle_text())
        if item.matched:
            self._why.setText(
                self.tr("concerns you because of: {reason}").format(reason=item.matched)
            )
        elif item.is_targeted:
            self._why.setText("")
        else:
            self._why.setText(self.tr("posted to everyone"))
        self._why.setVisible(bool(self._why.text()))

    def changeEvent(self, event: QEvent | None) -> None:  # noqa: N802 - Qt API
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
