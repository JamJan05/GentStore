"""Render the site to a directory of files.

The page is static once rendered — the server does nothing per request that
cannot be done once — so this walks the application with a test client and
writes what it answers. Rendering through the application rather than through
the templates directly is deliberate: whatever the tests assert about the
served page is then true of the built one, down to the byte.

    python build.py --base-url https://www.gentstore.dev

Writes ``dist/`` by default, replacing whatever was there.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from app.content import ICON_DIR, LANGUAGES, SCREENSHOT_DIR, STATIC_DIR, WEBSITE_DIR

#: Copied verbatim: the URL they are served at, and where the files come from.
ASSET_TREES = {
    "static": STATIC_DIR,
    "screenshots": SCREENSHOT_DIR,
    "icons": ICON_DIR,
}

#: The one decision the application makes per request that a file cannot: which
#: language "/" leads to. Served as a page rather than as a redirect, it costs a
#: hop — a crawler reads the meta refresh, a browser runs the script and gets
#: the same answer the server would have given from Accept-Language.
INDEX_FALLBACK = """<!DOCTYPE html>
<html lang="{default}">
<head>
<meta charset="utf-8">
<title>GentStore</title>
<meta http-equiv="refresh" content="0; url=/{default}">
<link rel="canonical" href="{base_url}/{default}">
</head>
<body>
<script>
  var wanted = (navigator.languages || [navigator.language || ""])
    .map(function (tag) {{ return String(tag).toLowerCase().split("-")[0]; }})
    .filter(function (code) {{ return {languages}.indexOf(code) !== -1; }})[0];
  location.replace("/" + (wanted || "{default}"));
</script>
<p><a href="/{default}">GentStore</a></p>
</body>
</html>
"""

#: Cloudflare reads these two out of the assets directory. The rewrite keeps the
#: API at the path the application serves it at, rather than at the name of the
#: file behind it.
REDIRECTS = """# The application answers /api/content/pl; a file needs an extension.
/api/content/pl  /api/content/pl.json  200
/api/content/en  /api/content/en.json  200
"""

HEADERS = """/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin

# Nothing here is fingerprinted, so cache in hours rather than forever: an
# updated screenshot or stylesheet has to be able to reach a returning visitor.
/static/*
  Cache-Control: public, max-age=3600
/screenshots/*
  Cache-Control: public, max-age=86400
/icons/*
  Cache-Control: public, max-age=86400
"""


def build(destination: Path, base_url: str = "") -> list[Path]:
    """Write the whole site under *destination*, and return what was written."""
    if base_url:
        os.environ["GENTSTORE_WEB_BASE_URL"] = base_url.rstrip("/")
    else:
        os.environ.pop("GENTSTORE_WEB_BASE_URL", None)

    # Imported here, after the environment is set: the application reads it.
    from fastapi.testclient import TestClient

    from app.main import app

    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    written: list[Path] = []

    def write(relative: str, text: str) -> None:
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(path)

    with TestClient(app) as client:
        for language in LANGUAGES:
            page = client.get(f"/{language}")
            page.raise_for_status()
            # /pl as a directory, so the URL stays /pl and not /pl.html.
            write(f"{language}/index.html", page.text)

            content = client.get(f"/api/content/{language}")
            content.raise_for_status()
            write(
                f"api/content/{language}.json",
                json.dumps(content.json(), ensure_ascii=False, indent=2) + "\n",
            )

        # Served for anything that is not a file — see not_found_handling.
        missing = client.get("/this-path-does-not-exist")
        write("404.html", missing.text)

        write("robots.txt", client.get("/robots.txt").text)

    write(
        "index.html",
        INDEX_FALLBACK.format(
            default=LANGUAGES[0],
            base_url=base_url.rstrip("/"),
            languages=json.dumps(list(LANGUAGES)),
        ),
    )
    write("_redirects", REDIRECTS)
    write("_headers", HEADERS)

    for name, source in ASSET_TREES.items():
        shutil.copytree(source, destination / name)
        written.extend(sorted((destination / name).rglob("*")))

    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=WEBSITE_DIR.parent / "dist",
        help="where to write the site (default: dist/ beside the repository root)",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("GENTSTORE_WEB_BASE_URL", ""),
        help="the address the site will answer on, for the canonical and preview URLs",
    )
    args = parser.parse_args(argv)

    written = build(args.out, args.base_url)
    pages = sum(1 for path in written if path.suffix in {".html", ".json", ".txt"})
    print(f"{args.out}: {len(written)} files, {pages} of them rendered")
    if not args.base_url:
        print("no --base-url: the canonical and preview links are relative", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
