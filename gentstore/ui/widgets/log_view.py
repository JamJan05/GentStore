"""The command log: what is running, what it is saying, and a way to stop it.

Used by every screen that runs something, which is why it owns the whole strip
— the command line at the top, the output, the progress and the stop button —
rather than leaving each screen to assemble its own.

Two details are less obvious than they look. The view **stops following the
output as soon as the user scrolls up**, and starts again when they scroll back
to the bottom: reading an error while the log keeps yanking you to the end is
the single most irritating thing a build log can do. And lines are classified
and coloured here rather than by the caller, so ``emerge``, ``eselect`` and
``emaint`` all read the same way.
"""

from __future__ import annotations

import re

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextOption
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..theme import tokens as t

#: Colour escapes still turn up even with ``--color=n``: anything Portage runs
#: during a build may emit them.
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

#: ``>>> Emerging (3 of 12) media-video/mpv-0.41.0``. The real output parser
#: arrives with the system-update screen in S8; this is the one line of it the
#: progress bar needs.
_PROGRESS = re.compile(r"\((\d+) of (\d+)\)")

#: Kept in memory. A long ``@world`` rebuild produces far more than this, and
#: the interesting parts are the beginning and the end.
MAX_LINES = 20_000


def classify(line: str) -> str:
    """Which of the log's four looks a line gets.

    Portage's own markers, in its own order of severity: ``!!!`` is an error,
    ``***`` a warning, ``>>>`` a step of the merge.
    """
    stripped = line.lstrip()
    if stripped.startswith("!!!"):
        return "error"
    if stripped.startswith("***") or "warning" in stripped.lower():
        return "warning"
    if stripped.startswith(">>>"):
        return "step"
    return "plain"


_COLOURS = {
    "error": t.ERR,
    "warning": t.WARN,
    "step": t.ACCENT_300,
    "plain": t.NEUTRAL_300,
}


class LogView(QFrame):
    """Header, output, progress and a stop button."""

    abort_requested = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("logView")
        self._follow = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, t.SPACE_3)
        layout.setSpacing(t.SPACE_2)

        header = QHBoxLayout()
        header.setSpacing(t.SPACE_3)

        self._command = QLabel()
        self._command.setObjectName("logCommand")
        self._command.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header.addWidget(self._command)

        self._status = QLabel()
        self._status.setProperty("role", "caption")
        header.addWidget(self._status)
        header.addStretch(1)

        self._progress = QProgressBar()
        self._progress.setTextVisible(False)
        self._progress.setFixedWidth(140)
        self._progress.hide()
        header.addWidget(self._progress)

        self._abort = QPushButton()
        self._abort.setProperty("variant", "danger")
        self._abort.clicked.connect(self.abort_requested)
        self._abort.hide()
        header.addWidget(self._abort)

        self._close = QPushButton()
        self._close.setProperty("variant", "ghost")
        self._close.clicked.connect(self.close_requested)
        header.addWidget(self._close)
        layout.addLayout(header)

        self._output = QPlainTextEdit()
        self._output.setObjectName("logOutput")
        self._output.setReadOnly(True)
        self._output.setMaximumBlockCount(MAX_LINES)
        self._output.setWordWrapMode(QTextOption.WrapMode.NoWrap)
        self._output.setFrameShape(QFrame.Shape.NoFrame)
        bar = self._output.verticalScrollBar()
        if bar is not None:
            bar.valueChanged.connect(self._on_scrolled)
        layout.addWidget(self._output, 1)

        self.retranslate_ui()

    # -- contents ----------------------------------------------------------

    def start(self, command: str, description: str = "") -> None:
        """Clear the view and show that *command* is now running."""
        self._output.clear()
        self._follow = True
        self._command.setText(command)
        self._status.setText(description or self.tr("running…"))
        self._status.setProperty("state", "")
        self._progress.setRange(0, 0)
        self._progress.hide()
        self._abort.show()
        self._repolish()

    def append(self, line: str) -> None:
        """Add one line of output, coloured by what it looks like."""
        text = _ANSI.sub("", line)
        bar = self._output.verticalScrollBar()
        # Whether to follow is decided *before* the insert: afterwards the
        # scrollbar's maximum has already moved and the answer is always "no".
        follow = self._follow

        colour = _COLOURS[classify(text)]
        self._output.appendHtml(
            f'<span style="color:{colour};white-space:pre">{_escape(text)}</span>'
        )

        match = _PROGRESS.search(text)
        if match:
            current, total = int(match.group(1)), int(match.group(2))
            self._progress.setRange(0, total)
            self._progress.setValue(current)
            self._progress.show()

        if follow and bar is not None:
            bar.setValue(bar.maximum())

    def finish(self, message: str, state: str = "") -> None:
        """The command ended. *state* is one of ``ok``, ``warn``, ``err``, ``""``."""
        self._abort.hide()
        self._progress.hide()
        self._status.setText(message)
        self._status.setProperty("state", state)
        self._repolish()

    def text(self) -> str:
        return self._output.toPlainText()

    # -- following ---------------------------------------------------------

    def _on_scrolled(self, value: int) -> None:
        bar = self._output.verticalScrollBar()
        if bar is None:  # pragma: no cover - only when the widget is being torn down
            return
        self._follow = value >= bar.maximum() - 2

    # -- presentation ------------------------------------------------------

    def _repolish(self) -> None:
        style = self._status.style()
        if style is not None:
            style.unpolish(self._status)
            style.polish(self._status)
        self._status.update()

    def set_monospace(self, font: QFont) -> None:
        self._output.setFont(font)

    def retranslate_ui(self) -> None:
        self._abort.setText(self.tr("Stop"))
        self._abort.setToolTip(
            self.tr("Sends the same interrupt Ctrl+C does, so Portage can tidy up.")
        )
        self._close.setText(self.tr("Hide"))

    def changeEvent(self, event: QEvent | None) -> None:  # noqa: N802 - Qt API
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace(" ", "&nbsp;")
    )
