"""The nine screens of the application, declared once.

The sidebar, the page stack and the keyboard shortcuts all read this list, so a
screen is added or reordered in exactly one place.

Titles are wrapped in ``QT_TRANSLATE_NOOP`` so ``lupdate`` can find them while
the actual lookup happens in :attr:`PageSpec.title`, i.e. after a language
switch as well as before it.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QCoreApplication

try:  # pragma: no cover - depends on the PyQt6 build
    from PyQt6.QtCore import QT_TRANSLATE_NOOP
except ImportError:  # pragma: no cover
    def QT_TRANSLATE_NOOP(_context: str, text: str) -> str:  # noqa: N802 - Qt spelling
        """Mark a string for extraction without translating it here."""
        return text

#: Context used for every page title in the .ts files.
#:
#: The literal ``"Pages"`` is repeated in every ``QT_TRANSLATE_NOOP`` call below
#: instead of this constant, and that is not an oversight: ``lupdate`` reads the
#: source as text, so a variable in the context slot makes it drop the string —
#: silently, leaving the sidebar in English while the rest of the window is
#: translated.
CONTEXT = "Pages"


@dataclass(frozen=True, slots=True)
class PageSpec:
    """Everything the chrome needs to know about one screen."""

    page_id: str
    icon: str
    title_source: str
    #: Session in Docs/05-session-plan.md that implements this screen.
    session: str

    @property
    def title(self) -> str:
        """The screen's name in the current language."""
        return QCoreApplication.translate(CONTEXT, self.title_source)


PAGES: tuple[PageSpec, ...] = (
    PageSpec("search", "magnifying-glass", QT_TRANSLATE_NOOP("Pages", "Search & install"), "S3"),
    PageSpec("update", "arrow-circle-up", QT_TRANSLATE_NOOP("Pages", "System update"), "S8"),
    PageSpec("repos", "git-branch", QT_TRANSLATE_NOOP("Pages", "Repositories"), "S7"),
    PageSpec("mask", "shield-warning", QT_TRANSLATE_NOOP("Pages", "Masks & licences"), "S6"),
    PageSpec("cfg", "files", QT_TRANSLATE_NOOP("Pages", "Configuration files"), "S9"),
    PageSpec("makeconf", "sliders", QT_TRANSLATE_NOOP("Pages", "make.conf"), "S10"),
    PageSpec("elog", "envelope", QT_TRANSLATE_NOOP("Pages", "elog messages"), "S11"),
    PageSpec("world", "package", QT_TRANSLATE_NOOP("Pages", "@world set"), "S11"),
    PageSpec("profile", "user-gear", QT_TRANSLATE_NOOP("Pages", "Profile"), "S10"),
)

PAGES_BY_ID: dict[str, PageSpec] = {page.page_id: page for page in PAGES}
