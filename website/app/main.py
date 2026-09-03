"""The web application: two rendered pages, the content behind them as JSON.

Run it from the ``website`` directory::

    python -m uvicorn app.main:app --reload

Nothing here reaches outside the machine. The screenshots and the icon are
served straight out of the repository working tree, so a retaken screenshot is
live on the next request without a copy step.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.content import (
    ICON_DIR,
    LANGUAGES,
    LINKS,
    LOCALES,
    SCREENSHOT_DIR,
    STATIC_DIR,
    TEMPLATE_DIR,
    base_url,
    inline,
    load,
    negotiate,
    other_language,
)

#: Answer HEAD as well as GET. Starlette adds it for a plain route, FastAPI does
#: not, and a 405 to a HEAD is a broken link to a monitor and to half the tools
#: that check one.
PAGE_METHODS = ["GET", "HEAD"]

#: How long a visitor's choice of language is remembered.
LANGUAGE_COOKIE = "lang"
LANGUAGE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365

app = FastAPI(
    title="GentStore website",
    version=__version__,
    description="The landing page for app-portage/gentstore and the content behind it.",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
templates.env.filters["inline"] = inline
templates.env.globals["languages"] = LANGUAGES
templates.env.globals["locales"] = LOCALES
templates.env.globals["links"] = LINKS

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOT_DIR)), name="screenshots")
app.mount("/icons", StaticFiles(directory=str(ICON_DIR)), name="icons")


#: One ``<url>`` per page, each naming every language the page exists in — the
#: same set the ``<head>`` declares, which is what a crawler is asked to find in
#: both places.
SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
{urls}</urlset>
"""


def sitemap_xml(site: str) -> str:
    """The sitemap for a deployment answering at *site*."""
    alternates = "".join(
        f'    <xhtml:link rel="alternate" hreflang="{code}" href="{site}/{code}"/>\n'
        for code in LANGUAGES
    )
    alternates += f'    <xhtml:link rel="alternate" hreflang="x-default" href="{site}/"/>\n'
    urls = "".join(
        f"  <url>\n    <loc>{site}/{code}</loc>\n{alternates}  </url>\n" for code in LANGUAGES
    )
    return SITEMAP.format(urls=urls)


def _structured_data(content: dict[str, Any], language: str, site: str) -> dict[str, Any]:
    """What the page says about the application, in the form a search engine reads.

    Every value is one the page already carries — the same description, version,
    repository and screenshot — so what a search result shows and what a visitor
    reads cannot drift apart.
    """
    return {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "GentStore",
        "url": f"{site}/{language}",
        "description": content["meta"]["description"],
        "applicationCategory": "DeveloperApplication",
        "operatingSystem": "Gentoo Linux",
        "softwareVersion": content["header"]["version"],
        "codeRepository": LINKS["github"],
        "license": "https://www.gnu.org/licenses/gpl-2.0.html",
        "isAccessibleForFree": True,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
        "inLanguage": language,
        "screenshot": f"{site}/screenshots/search-and-install.png",
        "author": {"@type": "Person", "name": "JamJan05", "url": LINKS["github"]},
    }


def _page(request: Request, language: str, status_code: int = 200) -> Response:
    content = load(language)
    response = templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "c": content,
            "lang": language,
            "other": other_language(language),
            "version": __version__,
            "base_url": base_url(),
            "structured_data": _structured_data(content, language, base_url()),
        },
        status_code=status_code,
    )
    response.set_cookie(
        LANGUAGE_COOKIE,
        language,
        max_age=LANGUAGE_COOKIE_MAX_AGE,
        samesite="lax",
        httponly=False,
    )
    return response


@app.api_route("/", methods=PAGE_METHODS, include_in_schema=False)
def root(request: Request) -> RedirectResponse:
    """Send a visitor to the language they are most likely to want."""
    language = negotiate(
        request.headers.get("accept-language"),
        request.cookies.get(LANGUAGE_COOKIE),
    )
    return RedirectResponse(f"/{language}", status_code=302)


@app.api_route("/api/health", methods=PAGE_METHODS, tags=["api"])
def health() -> dict[str, Any]:
    """A liveness check that also names what the site is currently serving."""
    return {
        "status": "ok",
        "site_version": __version__,
        "app_version": load("en")["header"]["version"],
        "languages": list(LANGUAGES),
    }


@app.api_route("/api/content/{language}", methods=PAGE_METHODS, tags=["api"])
def api_content(language: str) -> JSONResponse:
    """The page's copy, exactly as the template receives it."""
    if language not in LANGUAGES:
        raise StarletteHTTPException(status_code=404, detail=f"No content for {language!r}")
    return JSONResponse(load(language))


@app.api_route("/robots.txt", methods=PAGE_METHODS, include_in_schema=False)
def robots() -> PlainTextResponse:
    """Nothing here is hidden, and the sitemap is named for a crawler that
    arrives at the root: this file is the only place it is told about it."""
    lines = ["User-agent: *", "Allow: /"]
    site = base_url()
    if site:
        # The line has to carry an absolute URL, so it appears only where the
        # deployment knows the address it answers on.
        lines.append(f"Sitemap: {site}/sitemap.xml")
    return PlainTextResponse("\n".join(lines) + "\n")


@app.api_route("/sitemap.xml", methods=PAGE_METHODS, include_in_schema=False)
def sitemap() -> Response:
    """Both pages, listed once each, with the other language beside them.

    The site is two pages linked from one another, so a crawler would find them
    anyway; the sitemap exists so that a new deployment can be submitted rather
    than waited for, and so the pair is declared as translations of each other
    in the place Google reads that from.
    """
    return Response(content=sitemap_xml(base_url()), media_type="application/xml")


@app.api_route("/favicon.ico", methods=PAGE_METHODS, include_in_schema=False)
def favicon() -> FileResponse:
    """A real .ico at the root: it is the only icon some crawlers look for."""
    return FileResponse(ICON_DIR / "favicon.ico", media_type="image/x-icon")


@app.api_route("/{language}", methods=PAGE_METHODS, include_in_schema=False)
def page(request: Request, language: str) -> Response:
    """The landing page in one language."""
    if language not in LANGUAGES:
        raise StarletteHTTPException(status_code=404, detail=f"No page at /{language}")
    return _page(request, language)


@app.exception_handler(StarletteHTTPException)
def http_error(request: Request, exc: StarletteHTTPException) -> Response:
    """Answer in the shape the caller asked for: JSON under /api, a page elsewhere."""
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    language = negotiate(
        request.headers.get("accept-language"),
        request.cookies.get(LANGUAGE_COOKIE),
    )
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "c": load(language),
            "lang": language,
            "other": other_language(language),
            "status_code": exc.status_code,
            "detail": exc.detail,
            "base_url": base_url(),
        },
        status_code=exc.status_code,
    )
