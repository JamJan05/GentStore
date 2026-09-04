"""Loading and rendering the page content.

The two JSON files under ``website/content/`` are the whole of the site's copy,
one per language. They hold text, not markup: a fragment wrapped in backticks
becomes a ``<code>`` element and one wrapped in ``**`` becomes ``<strong>``.
Everything else is escaped, so the content files never carry HTML and can be
translated without touching the template.
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from markupsafe import Markup, escape

#: ``website/app/content.py`` → ``website/app`` → ``website`` → the repository root.
APP_DIR = Path(__file__).resolve().parent
WEBSITE_DIR = APP_DIR.parent
REPO_ROOT = WEBSITE_DIR.parent

CONTENT_DIR = WEBSITE_DIR / "content"
STATIC_DIR = APP_DIR / "static"
TEMPLATE_DIR = APP_DIR / "templates"

#: Assets the page borrows from the repository rather than keeping a second copy of.
SCREENSHOT_DIR = REPO_ROOT / "Docs" / "screenshots"
ICON_DIR = REPO_ROOT / "data" / "icons"

LANGUAGES: tuple[str, ...] = ("pl", "en")

#: Where a visitor goes when nothing about them asks for anything: no
#: Accept-Language header, or one that names neither of our languages. English
#: rather than the first of LANGUAGES, because the visitor who sends no header
#: is usually a crawler, and the page it should index for "portage gui" is the
#: one written in the language that question is asked in. Anybody whose browser
#: does say `pl` still gets Polish — that is what negotiate() is for.
DEFAULT_LANGUAGE = "en"

#: What ``og:locale`` calls each of them. A link unfurler that is told nothing
#: assumes ``en_US``, which is wrong for half the site. The English is written
#: with British spelling — "licences" — so it is ``en_GB``.
LOCALES: dict[str, str] = {"pl": "pl_PL", "en": "en_GB"}


def base_url() -> str:
    """The origin the page is reachable at, or ``""`` when it is not deployed.

    Set ``GENTSTORE_WEB_BASE_URL`` to something like ``https://gentstore.example``
    and the canonical link, the ``hreflang`` alternates and the preview image
    become absolute, which is what a crawler and a link unfurler need. Left
    unset — a development server, or a machine reached by its address — the page
    keeps the relative URLs, which are correct wherever it is answering from.
    """
    return os.environ.get("GENTSTORE_WEB_BASE_URL", "").rstrip("/")


#: Every outbound link on the page. Kept here, and referenced by key from the
#: content files, so that a moved repository is one edit rather than four.
LINKS: dict[str, str] = {
    "github": "https://github.com/JamJan05/GentStore",
    "docs": "https://github.com/JamJan05/GentStore/tree/main/Docs",
    "changelog": "https://github.com/JamJan05/GentStore/blob/main/CHANGELOG.md",
    "packaging": "https://github.com/JamJan05/GentStore/tree/main/packaging",
}

_CODE = re.compile(r"`([^`]+)`")
_STRONG = re.compile(r"\*\*([^*]+)\*\*")


class UnknownLanguageError(LookupError):
    """Raised when a language outside :data:`LANGUAGES` is asked for."""


def inline(text: str) -> Markup:
    """Turn one line of content into HTML.

    The text is escaped first and marked up afterwards, so a stray ``<`` in the
    copy stays a ``<`` and only the two markers below produce elements.
    """
    out = str(escape(text))
    out = _STRONG.sub(r"<strong>\1</strong>", out)
    out = _CODE.sub(r"<code>\1</code>", out)
    return Markup(out)


def _read(language: str) -> dict[str, Any]:
    if language not in LANGUAGES:
        raise UnknownLanguageError(language)
    path = CONTENT_DIR / f"{language}.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=len(LANGUAGES))
def _read_cached(language: str) -> dict[str, Any]:
    return _read(language)


def load(language: str) -> dict[str, Any]:
    """Return the content for *language*.

    Cached, unless ``GENTSTORE_WEB_RELOAD`` is set — with it, editing a content
    file shows up on the next request, which is what the reloading development
    server is for.
    """
    if os.environ.get("GENTSTORE_WEB_RELOAD"):
        return _read(language)
    return _read_cached(language)


def negotiate(accept_language: str | None, cookie: str | None = None) -> str:
    """Pick a language for a visitor who has not asked for one explicitly.

    A previous choice, remembered in a cookie, wins over the browser's header.
    The header is read for the first of our languages it mentions, by quality:
    ``en;q=0.8, pl`` means Polish, because ``pl`` carries the implied ``q=1``.
    """
    if cookie in LANGUAGES:
        return cookie
    if not accept_language:
        return DEFAULT_LANGUAGE

    best: tuple[float, int, str] | None = None
    for position, part in enumerate(accept_language.split(",")):
        tag, _, params = part.strip().partition(";")
        tag = tag.strip().lower()
        language = tag.split("-", 1)[0]
        if language not in LANGUAGES:
            continue
        quality = 1.0
        for param in params.split(";"):
            key, _, value = param.strip().partition("=")
            if key.strip().lower() == "q":
                try:
                    quality = float(value)
                except ValueError:
                    quality = 0.0
        candidate = (-quality, position, language)
        if best is None or candidate < best:
            best = candidate
    return best[2] if best else DEFAULT_LANGUAGE


def other_language(language: str) -> str:
    """The language the switch in the header leads to."""
    return "en" if language == "pl" else "pl"
