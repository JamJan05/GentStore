"""Tests for the website — the routes, the content files and the small renderer.

They are deliberately outside the repository's ``tests/`` tree: the application
suite runs on a Gentoo box that has no FastAPI installed, and this needs one.
Run them from the ``website`` directory with ``pytest``.
"""

from __future__ import annotations

import html
import json
from xml.etree import ElementTree

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402
from markupsafe import escape  # noqa: E402

from app.content import (  # noqa: E402
    CONTENT_DIR,
    DEFAULT_LANGUAGE,
    LANGUAGES,
    LINKS,
    LOCALES,
    SCREENSHOT_DIR,
    base_url,
    inline,
    load,
    negotiate,
)
from app.main import app  # noqa: E402


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


def test_every_figure_the_content_declares_reaches_the_page(client: TestClient) -> None:
    """A screenshot that exists on disk is not the same as one that is shown.

    ``c.figures.update`` looked like every other reference in the template and
    was not one: Jinja resolves an attribute before a key, ``dict`` has an
    ``update`` method, and the ``.file`` on that method is undefined — which
    renders as nothing. What reached the page was an empty frame with an empty
    caption next to a real screenshot, and every other check passed: the file
    existed, the content had the caption, the shapes matched.
    """
    for language in LANGUAGES:
        page = client.get(f"/{language}").text
        for name, figure in load(language)["figures"].items():
            assert f'/screenshots/{figure["file"]}' in page, f"{language}: {name} has no image"
            # Escaped, because the captions carry apostrophes and the template
            # escapes them; comparing the raw text would fail on the wrong thing.
            caption = str(escape(figure["caption"]))
            assert caption in page, f"{language}: {name} has no caption"
        assert 'src="/screenshots/"' not in page, f"{language}: an empty figure is on the page"


def test_no_content_key_is_shadowed_by_a_dict_method() -> None:
    """The trap above, closed for the keys nobody has written a template for yet.

    Any key that is also an attribute of ``dict`` — ``update``, ``items``,
    ``keys``, ``values``, ``get``, ``copy``, ``pop`` — will silently be the
    method when a template reaches it with a dot. The subscript form works and
    is what the one existing case uses, but nothing makes a later template use
    it, so the safer rule is not to have such a key.
    """
    def walk(node: object, path: str = "") -> list[str]:
        found = []
        if isinstance(node, dict):
            for key, value in node.items():
                if hasattr({}, str(key)):
                    found.append(f"{path}.{key}" if path else str(key))
                found.extend(walk(value, f"{path}.{key}" if path else str(key)))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                found.extend(walk(value, f"{path}[{index}]"))
        return found

    for language in LANGUAGES:
        shadowed = walk(load(language))
        # ``figures.update`` is the one that exists; the template subscripts it.
        assert shadowed == ["figures.update"], f"{language}: {shadowed}"


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
    # A visitor who has said nothing. The client is shared across this module and
    # a page above it left a `lang` cookie behind, which negotiate() honours
    # before anything else — so without this the test asserts about whichever
    # page happened to run first, not about the default.
    client.cookies.clear()
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
    assert client.get("/icons/apple-touch-icon.png").status_code == 200
    assert client.get("/favicon.ico").headers["content-type"] == "image/x-icon"
    assert client.get("/robots.txt").text.startswith("User-agent: *")


def test_robots_names_the_sitemap_once_the_address_is_known(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A relative Sitemap line is not one, so it appears only when deployed."""
    monkeypatch.delenv("GENTSTORE_WEB_BASE_URL", raising=False)
    assert "Sitemap:" not in client.get("/robots.txt").text

    monkeypatch.setenv("GENTSTORE_WEB_BASE_URL", "https://gentstore.example")
    assert "Sitemap: https://gentstore.example/sitemap.xml" in client.get("/robots.txt").text


def test_the_sitemap_lists_every_page_with_its_translations(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GENTSTORE_WEB_BASE_URL", "https://gentstore.example")
    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")

    sitemap = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    xhtml = "{http://www.w3.org/1999/xhtml}"
    root = ElementTree.fromstring(response.text)

    located = [url.findtext(f"{sitemap}loc") for url in root.findall(f"{sitemap}url")]
    assert located == [f"https://gentstore.example/{code}" for code in LANGUAGES]

    for url in root.findall(f"{sitemap}url"):
        alternates = {
            link.get("hreflang"): link.get("href") for link in url.findall(f"{xhtml}link")
        }
        assert alternates == {
            **{code: f"https://gentstore.example/{code}" for code in LANGUAGES},
            "x-default": "https://gentstore.example/",
        }


def test_each_page_declares_its_own_locale(client: TestClient) -> None:
    """An unfurler told nothing assumes en_US, which is wrong for half the site."""
    # A language added without a locale would fail in the template, not here.
    assert set(LOCALES) == set(LANGUAGES)

    polish = client.get("/pl").text
    assert '<meta property="og:locale" content="pl_PL">' in polish
    assert '<meta property="og:locale:alternate" content="en_GB">' in polish

    english = client.get("/en").text
    assert '<meta property="og:locale" content="en_GB">' in english
    assert '<meta property="og:locale:alternate" content="pl_PL">' in english


def test_the_page_carries_the_application_as_structured_data(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What a search engine reads has to be what the page says, not a second copy."""
    monkeypatch.setenv("GENTSTORE_WEB_BASE_URL", "https://gentstore.example")
    page = client.get("/en").text

    block = page.split('<script type="application/ld+json">')[1].split("</script>")[0]
    data = json.loads(html.unescape(block))

    content = load("en")
    assert data["@type"] == "SoftwareApplication"
    assert data["description"] == content["meta"]["description"]
    assert data["softwareVersion"] == content["header"]["version"]
    assert data["url"] == "https://gentstore.example/en"
    assert data["codeRepository"] == LINKS["github"]


def test_screenshots_are_not_a_way_out_of_their_directory(client: TestClient) -> None:
    assert client.get("/screenshots/../../LICENSE").status_code == 404
