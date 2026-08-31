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

"""Marking the text that is deliberately not translated.

Docs/03-i18n.md §3 lists what stays as it is in every language: atoms, paths,
commands, Portage's own variable names, USE flag names, program names, and the
names of languages themselves. All of those reach the interface as ordinary
strings, and from the outside they are indistinguishable from a sentence
somebody forgot to wrap in ``tr()``.

:func:`untranslated` is that distinction, written down. It does nothing at run
time; what it does is let the code say "yes, this one is meant to be like
that", so a reviewer and the catalogue test can both tell the difference.
"""

from __future__ import annotations


def untranslated(text: str) -> str:
    """Text that must read the same in every language.

    ``untranslated("emaint sync -a")`` is a command the user could retype;
    ``self.tr("Synchronise")`` is a label. Both end up in ``setToolTip``, and
    only one of them belongs in the catalogue.
    """
    return text
