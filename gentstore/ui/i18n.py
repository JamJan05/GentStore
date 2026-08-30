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
