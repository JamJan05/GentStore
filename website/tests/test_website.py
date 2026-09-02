"""Tests for the website — the routes, the content files and the small renderer.

They are deliberately outside the repository's ``tests/`` tree: the application
suite runs on a Gentoo box that has no FastAPI installed, and this needs one.
Run them from the ``website`` directory with ``pytest``.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")

from app.content import (  # noqa: E402
    CONTENT_DIR,
    DEFAULT_LANGUAGE,
    LANGUAGES,
    LINKS,
    SCREENSHOT_DIR,
    base_url,
    inline,
    load,
    negotiate,
)
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


# --------------------------------------------------------------------------- #
# Content
# --------------------------------------------------------------------------- #


def test_both_languages_have_the_same_shape() -> None:
    """A section added to one language has to be added to the other."""

    def shape(value: object) -> object:
        if isinstance(value, dict):
            return {key: shape(item) for key, item in sorted(value.items())}
        if isinstance(value, list):
            return [shape(item) for item in value]
        return type(value).__name__

    assert shape(load("pl")) == shape(load("en"))


def test_every_screenshot_the_content_names_exists() -> None:
    for language in LANGUAGES:
        for name, figure in load(language)["figures"].items():
            assert (SCREENSHOT_DIR / figure["file"]).is_file(), f"{language}/{name}"


def test_footer_links_resolve_to_a_known_url() -> None:
    for language in LANGUAGES:
        for link in load(language)["footer"]["links"]:
            assert link["key"] in LINKS


def test_content_files_carry_no_markup() -> None:
    """The copy is text; the template supplies the tags."""
    for language in LANGUAGES:
        raw = (CONTENT_DIR / f"{language}.json").read_text(encoding="utf-8")
        assert "<" not in raw


# --------------------------------------------------------------------------- #
# The inline renderer
# --------------------------------------------------------------------------- #


def test_inline_marks_up_backticks_and_bold() -> None:
    assert str(inline("a `b` c")) == "a <code>b</code> c"
    assert str(inline("a **b** c")) == "a <strong>b</strong> c"


def test_inline_escapes_before_it_marks_up() -> None:
    rendered = str(inline("<script>alert(1)</script> `x`"))
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "<code>x</code>" in rendered


# --------------------------------------------------------------------------- #
# Language negotiation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, DEFAULT_LANGUAGE),
        ("", DEFAULT_LANGUAGE),
        ("en-GB,en;q=0.9", "en"),
        ("pl-PL,pl;q=0.9,en;q=0.8", "pl"),
        ("en;q=0.8, pl", "pl"),
        ("de,fr;q=0.9", DEFAULT_LANGUAGE),
    ],
)
def test_negotiate_reads_the_header(header: str | None, expected: str) -> None:
    assert negotiate(header) == expected


def test_a_remembered_choice_beats_the_header() -> None:
    assert negotiate("en-GB,en;q=0.9", cookie="pl") == "pl"
    assert negotiate("pl", cookie="nonsense") == "pl"


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


def test_root_redirects_to_the_negotiated_language(client: TestClient) -> None:
    response = client.get("/", headers={"accept-language": "en"}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/en"


def test_root_honours_the_language_cookie() -> None:
    remembered = TestClient(app, cookies={"lang": "pl"})
    response = remembered.get(
        "/",
        headers={"accept-language": "en"},
        follow_redirects=False,
    )
    assert response.headers["location"] == "/pl"


@pytest.mark.parametrize("language", LANGUAGES)
def test_each_page_renders(client: TestClient, language: str) -> None:
    response = client.get(f"/{language}")
    assert response.status_code == 200
    body = response.text
    content = load(language)
    assert f'<html lang="{language}">' in body
    assert content["hero"]["title_lines"][0] in body
    assert content["cta"]["title"] in body
    # Nine screens, and the shortcut row under them.
    assert body.count('<div class="screen">') == 9
    assert body.count("screen--shortcuts") == 1
    assert response.cookies.get("lang") == language


def test_a_page_offers_the_other_language(client: TestClient) -> None:
    body = client.get("/pl").text
    assert 'href="/en" hreflang="en"' in body
    assert '<link rel="alternate" hreflang="en" href="/en">' in body


def test_unknown_language_is_a_page_not_a_traceback(client: TestClient) -> None:
    response = client.get("/de")
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert load(DEFAULT_LANGUAGE)["error"]["title"] in response.text


def test_api_content_matches_the_files(client: TestClient) -> None:
    for language in LANGUAGES:
        response = client.get(f"/api/content/{language}")
        assert response.status_code == 200
        assert response.json() == json.loads(
            (CONTENT_DIR / f"{language}.json").read_text(encoding="utf-8")
        )


def test_api_errors_stay_json(client: TestClient) -> None:
    response = client.get("/api/content/de")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert "de" in response.json()["detail"]


def test_health_names_the_application_version(client: TestClient) -> None:
    payload = client.get("/api/health").json()
    assert payload["status"] == "ok"
    assert payload["app_version"] == load("en")["header"]["version"]
    assert payload["languages"] == list(LANGUAGES)


def test_without_a_base_url_the_page_stays_relative(client: TestClient) -> None:
    body = client.get("/pl").text
    assert '<link rel="canonical" href="/pl">' in body
    assert '<meta property="og:image" content="/screenshots/search-and-install.png">' in body


def test_a_base_url_makes_the_crawler_facing_links_absolute(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GENTSTORE_WEB_BASE_URL", "https://gentstore.example/")
    assert base_url() == "https://gentstore.example"
    body = client.get("/pl").text
    assert '<link rel="canonical" href="https://gentstore.example/pl">' in body
    assert '<link rel="alternate" hreflang="en" href="https://gentstore.example/en">' in body
    assert '<meta property="og:url" content="https://gentstore.example/pl">' in body
    assert (
        '<meta property="og:image" '
        'content="https://gentstore.example/screenshots/search-and-install.png">'
    ) in body
    # The links a visitor clicks stay relative, so the page works on any origin.
    assert 'href="/en" hreflang="en"' in body


@pytest.mark.parametrize(
    "path", ["/", "/pl", "/en", "/api/health", "/api/content/pl", "/robots.txt", "/favicon.ico"]
)
def test_head_is_answered_wherever_get_is(client: TestClient, path: str) -> None:
    """A 405 to a HEAD reads as a broken link to whatever is checking."""
    head = client.head(path, follow_redirects=False)
    get = client.get(path, follow_redirects=False)
    assert head.status_code == get.status_code, path


def test_assets_are_served_from_the_repository(client: TestClient) -> None:
    assert client.get("/static/site.css").status_code == 200
    assert client.get("/screenshots/search-and-install.png").status_code == 200
    assert client.get("/icons/gentstore.svg").status_code == 200
    assert client.get("/favicon.ico").headers["content-type"] == "image/svg+xml"
    assert client.get("/robots.txt").text.startswith("User-agent: *")


def test_screenshots_are_not_a_way_out_of_their_directory(client: TestClient) -> None:
    assert client.get("/screenshots/../../LICENSE").status_code == 404
