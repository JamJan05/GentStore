"""Tests for the static build.

The build renders the site through the application, so what these check is that
everything the deployed directory needs is in it, and that a rendered page is
the page the application serves — not a second implementation of it.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from app.content import DEFAULT_LANGUAGE, LANGUAGES, load  # noqa: E402
from build import build  # noqa: E402

BASE_URL = "https://gentstore.example"


@pytest.fixture
def site(tmp_path: Path) -> Iterator[Path]:
    """A built site, with the environment build() edits put back afterwards."""
    before = os.environ.get("GENTSTORE_WEB_BASE_URL")
    out = tmp_path / "dist"
    build(out, BASE_URL)
    yield out
    if before is None:
        os.environ.pop("GENTSTORE_WEB_BASE_URL", None)
    else:
        os.environ["GENTSTORE_WEB_BASE_URL"] = before


def test_every_url_the_site_needs_is_a_file(site: Path) -> None:
    expected = [
        "index.html",
        "404.html",
        "robots.txt",
        "sitemap.xml",
        "_redirects",
        "_headers",
        "static/site.css",
        "static/site.js",
        "icons/gentstore.svg",
        "icons/apple-touch-icon.png",
        "favicon.ico",
    ]
    expected += [f"{language}.html" for language in LANGUAGES]
    expected += [f"api/content/{language}.json" for language in LANGUAGES]
    missing = [name for name in expected if not (site / name).is_file()]
    assert missing == []


def test_the_screenshots_the_page_shows_are_copied(site: Path) -> None:
    for language in LANGUAGES:
        for figure in load(language)["figures"].values():
            assert (site / "screenshots" / figure["file"]).is_file()


def test_a_built_page_is_the_page_the_application_serves(site: Path) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    os.environ["GENTSTORE_WEB_BASE_URL"] = BASE_URL
    with TestClient(app) as client:
        for language in LANGUAGES:
            served = client.get(f"/{language}").text
            assert (site / f"{language}.html").read_text(encoding="utf-8") == served


def test_the_built_page_carries_the_deployed_address(site: Path) -> None:
    page = (site / "pl.html").read_text(encoding="utf-8")
    assert f'<link rel="canonical" href="{BASE_URL}/pl">' in page


def test_what_a_crawler_is_pointed_at_is_absolute(site: Path) -> None:
    """Both files are read from the root of the deployment, not from a page."""
    assert f"Sitemap: {BASE_URL}/sitemap.xml" in (site / "robots.txt").read_text("utf-8")
    assert f"<loc>{BASE_URL}/pl</loc>" in (site / "sitemap.xml").read_text("utf-8")


def test_the_api_files_match_the_content(site: Path) -> None:
    for language in LANGUAGES:
        built = json.loads((site / "api" / "content" / f"{language}.json").read_text("utf-8"))
        assert built == load(language)


def test_the_index_sends_a_visitor_to_a_language(site: Path) -> None:
    """The only page whose whole job is to send you somewhere else."""
    index = (site / "index.html").read_text(encoding="utf-8")
    assert 'http-equiv="refresh"' in index
    assert f'content="0; url=/{DEFAULT_LANGUAGE}"' in index
    assert "location.replace" in index
    # The script has to be ahead of the refresh, or it never runs.
    assert index.index("location.replace") < index.index("http-equiv")


def test_building_twice_leaves_nothing_behind(site: Path) -> None:
    stray = site / "static" / "left-over.css"
    stray.write_text("/* from an older build */", encoding="utf-8")
    build(site, BASE_URL)
    assert not stray.exists()
