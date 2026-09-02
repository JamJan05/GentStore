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
    SCREENSHOT_DIR,
    STATIC_DIR,
    TEMPLATE_DIR,
    base_url,
    inline,
    load,
    negotiate,
    other_language,
)

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
templates.env.globals["links"] = LINKS

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOT_DIR)), name="screenshots")
app.mount("/icons", StaticFiles(directory=str(ICON_DIR)), name="icons")


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


@app.get("/", include_in_schema=False)
def root(request: Request) -> RedirectResponse:
    """Send a visitor to the language they are most likely to want."""
    language = negotiate(
        request.headers.get("accept-language"),
        request.cookies.get(LANGUAGE_COOKIE),
    )
    return RedirectResponse(f"/{language}", status_code=302)


@app.get("/api/health", tags=["api"])
def health() -> dict[str, Any]:
    """A liveness check that also names what the site is currently serving."""
    return {
        "status": "ok",
        "site_version": __version__,
        "app_version": load("en")["header"]["version"],
        "languages": list(LANGUAGES),
    }


@app.get("/api/content/{language}", tags=["api"])
def api_content(language: str) -> JSONResponse:
    """The page's copy, exactly as the template receives it."""
    if language not in LANGUAGES:
        raise StarletteHTTPException(status_code=404, detail=f"No content for {language!r}")
    return JSONResponse(load(language))


@app.get("/robots.txt", include_in_schema=False)
def robots() -> PlainTextResponse:
    return PlainTextResponse("User-agent: *\nAllow: /\n")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse(ICON_DIR / "gentstore.svg", media_type="image/svg+xml")


@app.get("/{language}", include_in_schema=False)
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
