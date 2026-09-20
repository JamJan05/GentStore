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

"""Making a label show the text it was given.

``QLabel`` defaults to ``Qt::AutoText``, which guesses: it runs
``Qt::mightBeRichText()`` over the string and switches to HTML if it finds
something that looks like a tag. That guess is wrong in both directions here.

It is wrong about ordinary input. ``<sys-apps/foo-2 ~amd64`` is a perfectly
normal line for ``emerge --autounmask`` to ask for — the ``<`` is the
less-than-this-version operator — and Qt reads it as an unclosed tag and
displays **nothing at all**. The whole line still goes to
``/etc/portage/package.accept_keywords``. The principle this application is
built on is that the preview is the write; a preview that is empty while the
write is not breaks it without anybody doing anything wrong.

It is wrong about hostile input too. ``DESCRIPTION`` comes out of an ebuild,
flag descriptions come out of ``metadata.xml``, repository descriptions come
out of ``repositories.xml``, news headlines come out of a repository — all
written by whoever wrote the overlay the user added. ``<img src="http://…">``
in any of them is a network request from a program whose documentation says it
makes none (Docs/04-privileges.md §8), and ``<span style=…>`` is a sentence
that looks like Gentstore said it.

There are 181 ``QLabel`` calls in this package and not one of them wants HTML,
so this is set once, for all of them, rather than at each site. A label added
next year is covered without anybody having to remember — which is the part a
list of call sites could never give.

What it does **not** do is overrule a decision. Only ``AutoText``, the guessing
one, is replaced; a label that was explicitly given ``RichText`` keeps it. The
three places that really do build HTML — ``log_view``, ``diff_view`` and the
elog screen — escape their input and say so, and they use ``QTextEdit`` rather
than a label in any case.
"""

from __future__ import annotations

import html

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import QApplication, QLabel


class PlainTextGuard(QObject):
    """Turns ``AutoText`` into ``PlainText`` on every label in the process.

    Hooked to ``QEvent.Polish``, which Qt sends to a widget once, before it is
    first shown and after it has been fully constructed. That is late enough
    that a widget which chose its own format has already chosen it, and early
    enough that nothing has been painted yet.
    """

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:  # noqa: N802 - Qt API
        if (
            event is not None
            and event.type() == QEvent.Type.Polish
            and isinstance(obj, QLabel)
            and obj.textFormat() == Qt.TextFormat.AutoText
        ):
            obj.setTextFormat(Qt.TextFormat.PlainText)
        # Never consume it: this is an observer, and Polish has its own work
        # to do afterwards.
        return False


def install(app: QApplication) -> PlainTextGuard:
    """Put the guard on *app*. The return value has to be kept alive.

    An event filter is held by raw pointer on the Qt side, so a guard nobody
    keeps a reference to is garbage-collected and the filter quietly stops
    running — the kind of failure that looks like it works.
    """
    guard = PlainTextGuard(app)
    app.installEventFilter(guard)
    return guard


def plain_tooltip(text: str) -> str:
    """*text* as a tooltip that shows what it says.

    Tooltips are not labels and the guard above does not reach them:
    ``QToolTip`` runs the same ``mightBeRichText()`` guess of its own, and
    there is no format to set. So the string is escaped and wrapped in a span
    that is unambiguously rich text — the same trick ``log_view`` uses for the
    command output, for the same reason. ``white-space: pre`` keeps runs of
    spaces, which matter in a command line.

    An empty string is passed through, because a tooltip of ``<span></span>``
    is a tooltip, and Qt takes "" to mean "no tooltip".
    """
    if not text:
        return ""
    return f'<span style="white-space:pre">{html.escape(text)}</span>'
