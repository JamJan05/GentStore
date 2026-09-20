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

"""The preview is the write.

``QLabel`` guesses whether its text is HTML, and the guess is wrong in both
directions for what this application displays: it swallows an ordinary
upper-bound atom, and it renders whatever an overlay author put in a
``DESCRIPTION``. See gentstore/ui/plaintext.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextDocument
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gentstore.core.confedit import TargetKind, WritePlan
from gentstore.ui.plaintext import plain_tooltip
from gentstore.ui.widgets.write_preview import WritePreview


def _shown(label: QLabel) -> str:
    """What the label actually puts on screen.

    A label in ``PlainText`` shows its text; one left on ``AutoText`` runs the
    string through Qt's rich-text engine first, and that is where a line can
    disappear. Asking the engine directly is the only way to compare the two
    without taking a screenshot.
    """
    if label.textFormat() == Qt.TextFormat.PlainText:
        return label.text()
    document = QTextDocument()
    document.setHtml(label.text())
    return document.toPlainText()


# -- the guard --------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "<sys-apps/foo-2 ~amd64",
        "<=media-video/mpv-0.41.0 vulkan",
        "!<sys-libs/zlib-1.3",
        'A tool <img src="http://tracker.example/b.png"> for things',
        "harmless<span style='color:red'> — Gentstore: this change is safe</span>",
    ],
)
def test_a_label_shows_the_string_it_was_given(app, text: str) -> None:
    """An atom beginning with "<" is the less-than-this-version operator, which
    emerge --autounmask prints and Qt reads as an unclosed tag.

    Without the guard the first three of these render as the empty string while
    the whole line still goes to /etc/portage, and the last two fetch a URL and
    forge a sentence out of an ebuild.
    """
    holder = QWidget()
    layout = QVBoxLayout(holder)
    label = QLabel(text)
    layout.addWidget(label)
    holder.show()
    app.processEvents()

    assert label.textFormat() == Qt.TextFormat.PlainText
    assert _shown(label) == text


def test_a_deliberate_choice_is_left_alone(app) -> None:
    """The guard replaces guessing, not deciding.

    log_view, diff_view and the elog screen build escaped HTML on purpose. None
    of them is a QLabel today, but a label that asks for RichText has asked.
    """
    holder = QWidget()
    layout = QVBoxLayout(holder)
    label = QLabel("<b>on purpose</b>")
    label.setTextFormat(Qt.TextFormat.RichText)
    layout.addWidget(label)
    holder.show()
    app.processEvents()

    assert label.textFormat() == Qt.TextFormat.RichText


def test_the_guard_is_installed_by_the_application(app) -> None:
    """Held on the application: an event filter is a raw pointer on the Qt side,
    so a guard nobody references is collected and stops running."""
    from gentstore.ui.plaintext import PlainTextGuard

    assert isinstance(getattr(app, "_plain_text", None), PlainTextGuard)


# -- the panel that says what will be written -------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "<sys-apps/foo-2 ~amd64",
        "<=media-video/mpv-0.41.0 vulkan",
        "media-video/mpv vulkan wayland",
    ],
)
def test_the_preview_shows_the_bytes_that_will_be_written(app, line: str) -> None:
    """The principle the whole application is built on, as a test.

    Whatever is in this label is what goes into the file, so the two have to be
    the same string — not merely similar, and certainly not empty.
    """
    preview = WritePreview()
    preview.set_plan(
        WritePlan(
            op="append_line",
            path=Path("/etc/portage/package.accept_keywords/foo"),
            line=line,
            kind=TargetKind.DIRECTORY,
        )
    )
    preview.show()
    app.processEvents()

    assert preview._line.textFormat() == Qt.TextFormat.PlainText
    assert _shown(preview._line) == line


def test_the_preview_shows_the_path_it_will_write_to(app) -> None:
    path = Path("/etc/portage/package.use/media-video")
    preview = WritePreview()
    preview.set_plan(
        WritePlan(op="append_line", path=path, line="x/y flag", kind=TargetKind.DIRECTORY)
    )
    preview.show()
    app.processEvents()

    assert _shown(preview._path) == str(path)


# -- tooltips ---------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "<sys-apps/foo-2 ~amd64",
        "emerge --unmerge  media-video/mpv",
        'x <img src="http://tracker.example/b.png">',
    ],
)
def test_a_tooltip_shows_what_it_says(text: str) -> None:
    """QToolTip is not a label and the guard does not reach it: it runs the same
    guess of its own and there is no format to set.

    So the string is escaped and wrapped in something unambiguously rich, which
    is what log_view already does with command output.
    """
    document = QTextDocument()
    document.setHtml(plain_tooltip(text))
    assert document.toPlainText() == text


def test_an_empty_tooltip_stays_empty() -> None:
    """Qt reads "" as "no tooltip"; "<span></span>" is a tooltip."""
    assert plain_tooltip("") == ""


def test_no_label_in_the_package_asks_qt_to_guess() -> None:
    """A regression guard with a wider net than the cases above.

    Every QLabel in gentstore/ui is covered by the filter at runtime, so this
    checks the thing the filter cannot: that nobody has written
    ``setTextFormat(AutoText)`` back in on purpose somewhere.
    """
    import gentstore.ui as ui

    offenders = [
        f"{path.relative_to(Path(ui.__file__).parent)}:{number}"
        for path in Path(ui.__file__).parent.rglob("*.py")
        for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if "setTextFormat" in text and "AutoText" in text
    ]
    assert offenders == []
