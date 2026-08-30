"""Base class for the application's screens.

Two rules every page follows, both of them there so the language can be switched
without restarting (Docs/03-i18n.md §5):

* user-visible text is set in :meth:`retranslate_ui`, never once in ``__init__``;
* the page reacts to ``QEvent.Type.LanguageChange`` by calling it again.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QWidget

from ..context import AppContext
from .registry import PageSpec


class Page(QWidget):
    """A screen in the main stack."""

    def __init__(
        self, spec: PageSpec, context: AppContext, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.spec = spec
        self.context = context
        self.setObjectName(f"page-{spec.page_id}")

    @property
    def page_id(self) -> str:
        return self.spec.page_id

    def retranslate_ui(self) -> None:
        """Re-apply every user-visible string. Subclasses override this."""

    def activated(self) -> None:
        """Called each time the screen becomes the visible one.

        The hook exists so a screen can defer its first expensive read until
        somebody actually looks at it, instead of doing it at start-up.
        """

    def changeEvent(self, event: QEvent | None) -> None:  # noqa: N802 - Qt API
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
