"""The difference between two versions of a configuration file.

Unified rather than side by side. Configuration files are mostly comments and
long lines; two narrow columns of those are harder to read than one wide one
with the changed lines marked, and the marks are what people scan for.

Shared between this screen and the ``make.conf`` editor in session S10, so the
widget knows nothing about where its lines came from.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent
from PyQt6.QtGui import QTextOption
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from ...core.cfgfiles import DiffKind, DiffLine
from ..theme import tokens as t

_COLOURS = {
    DiffKind.ADDED: (t.OK, t.DIFF_ADD_BG),
    DiffKind.REMOVED: (t.ERR, t.DIFF_DEL_BG),
    DiffKind.HEADER: (t.NEUTRAL_600, "transparent"),
    DiffKind.CONTEXT: (t.NEUTRAL_400, "transparent"),
}

#: A diff longer than this is shown truncated: nobody reads eight thousand
#: lines in a panel, and rendering them costs more than the answer is worth.
MAX_LINES = 4000


class DiffView(QFrame):
    """Legend, then the diff."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("diffView")
        self._truncated = 0
        self._labels: tuple[str, str] | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(t.SPACE_2)

        legend = QHBoxLayout()
        legend.setContentsMargins(t.SPACE_1, 0, 0, 0)
        legend.setSpacing(t.SPACE_4)
        self._old = QLabel()
        self._old.setProperty("state", "err")
        legend.addWidget(self._old)
        self._new = QLabel()
        self._new.setProperty("state", "ok")
        legend.addWidget(self._new)
        legend.addStretch(1)
        self._note = QLabel()
        self._note.setProperty("role", "caption")
        legend.addWidget(self._note)
        layout.addLayout(legend)

        self._body = QPlainTextEdit()
        self._body.setObjectName("diffBody")
        self._body.setReadOnly(True)
        self._body.setWordWrapMode(QTextOption.WrapMode.NoWrap)
        self._body.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(self._body, 1)

        self.retranslate_ui()

    def set_lines(self, lines: tuple[DiffLine, ...]) -> None:
        self._body.clear()
        self._truncated = max(0, len(lines) - MAX_LINES)
        for line in lines[:MAX_LINES]:
            colour, background = _COLOURS[line.kind]
            self._body.appendHtml(
                f'<span style="color:{colour};background:{background};white-space:pre">'
                f"{_escape(line.text)}</span>"
            )
        cursor = self._body.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        self._body.setTextCursor(cursor)
        self.retranslate_ui()

    def set_labels(self, before: str, after: str) -> None:
        """Name the two sides. The default wording is about a package's file;
        the ``make.conf`` screen is comparing a file with itself."""
        self._labels = (before, after)
        self.retranslate_ui()

    def clear(self) -> None:
        self._body.clear()
        self._truncated = 0
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        before, after = self._labels or (
            self.tr("the file you have"),
            self.tr("the version the package brought"),
        )
        self._old.setText(f"− {before}")
        self._new.setText(f"+ {after}")
        self._note.setText(
            self.tr("%n more line(s) not shown", "", self._truncated)
            if self._truncated
            else ""
        )

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
