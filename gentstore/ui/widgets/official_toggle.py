"""The application-wide "official repository only" control.

It sits in the toolbar because it changes what every screen shows. Two modes,
deliberately kept distinguishable at a glance (Docs/02-ui-design.md §6):

``hide``
    a display filter — overlays keep syncing, they just stop appearing.
``mask``
    a real change to Portage, written as ``*/*::<overlay>`` into
    ``/etc/portage/package.mask/<overlay>``.

In mask mode the control spells the pending entry out next to itself, so the
consequence is visible before anything is written.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..i18n import untranslated
from ..theme import tokens as t
from .chips import Pill, ToggleChip

MODES = ("hide", "mask")


class OfficialOnlyControl(QWidget):
    """Toggle plus mode selector for "show packages from ::gentoo only"."""

    changed = pyqtSignal(bool, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._enabled = False
        self._mode = "hide"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(t.SPACE_2)

        self._chip = ToggleChip()
        self._chip.clicked.connect(self._toggle)
        layout.addWidget(self._chip)

        self._pills: dict[str, Pill] = {}
        for mode in MODES:
            pill = Pill()
            pill.clicked.connect(lambda m=mode: self._set_mode(m))
            self._pills[mode] = pill
            layout.addWidget(pill)

        self._hint = QLabel()
        self._hint.setProperty("role", "mono-accent")
        layout.addWidget(self._hint)

        self.retranslate_ui()

    # -- state -------------------------------------------------------------

    def set_state(self, enabled: bool, mode: str) -> None:
        """Apply a stored state without emitting :attr:`changed`."""
        self._enabled = enabled
        self._mode = mode if mode in MODES else "hide"
        self._refresh()

    def state(self) -> tuple[bool, str]:
        return self._enabled, self._mode

    def _toggle(self) -> None:
        self._enabled = not self._enabled
        self._refresh()
        self.changed.emit(self._enabled, self._mode)

    def _set_mode(self, mode: str) -> None:
        if mode == self._mode:
            return
        self._mode = mode
        self._refresh()
        self.changed.emit(self._enabled, self._mode)

    # -- presentation ------------------------------------------------------

    def _refresh(self) -> None:
        self._chip.set_checked(self._enabled)
        self._chip.set_suffix(self._suffix_text())
        for mode, pill in self._pills.items():
            pill.setVisible(self._enabled)
            pill.set_checked(mode == self._mode)
        self._hint.setVisible(self._enabled and self._mode == "mask")

    def _suffix_text(self) -> str:
        if not self._enabled:
            return self.tr("off")
        return self.tr("hide in GUI") if self._mode == "hide" else self.tr("mask in Portage")

    def retranslate_ui(self) -> None:
        self._chip.set_text(self.tr("Only ::gentoo"))
        self._pills["hide"].set_text(self.tr("a) hide in GUI"))
        self._pills["mask"].set_text(self.tr("b) mask in Portage"))
        # Not translated on purpose: this is the literal entry that gets written.
        self._hint.setText(untranslated("+ /etc/portage/package.mask/<overlay> → */*::<overlay>"))
        self._refresh()

    def changeEvent(self, event: QEvent | None) -> None:  # noqa: N802 - Qt API
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
