# The GentStore website

The landing page for `app-portage/gentstore`, and the small FastAPI application
that serves it. Built from the design canvas the project was mocked up in; the
colours, type and spacing are the tokens in `gentstore/ui/theme/tokens.py`, so
the page and the application window look like the same piece of software.

It has no database and makes no outbound calls. Everything on the page comes
from two JSON files in this directory and from files that already live in the
repository.

## Running it

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

python -m uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000/>. With `--reload` the server restarts on a
code change; for the content files, set `GENTSTORE_WEB_RELOAD=1` and they are
re-read on every request.

In production, drop `--reload` and give uvicorn the workers and the host it
should bind to:

```sh
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
```

The page is static once rendered, so anything that can sit in front of a WSGI
or ASGI server — nginx, Caddy — can cache it whole.

## Routes

| Route | What it is |
| --- | --- |
| `/` | Redirects to `/pl` or `/en` — a remembered choice first, then `Accept-Language` |
| `/pl`, `/en` | The page, rendered server-side, and a `lang` cookie remembering the choice |
| `/api/content/{pl,en}` | The copy behind the page, exactly as the template receives it |
| `/api/health` | Liveness, plus the version of GentStore the page is describing |
| `/api/docs` | The generated OpenAPI page for the two endpoints above |
| `/static/…` | The stylesheet and the one script |
| `/screenshots/…` | `Docs/screenshots/` from the repository, served as-is |
| `/icons/…` | `data/icons/` from the repository — the application icon is the favicon |

Nothing is copied into this directory that the repository already has: a
retaken screenshot is live on the next request.

## Content

`content/pl.json` and `content/en.json` are the whole of the site's copy. They
hold text, not markup:

- `` `like this` `` becomes a `<code>` element,
- `**like this**` becomes `<strong>`,
- everything else is escaped.

That is the entire vocabulary, which is why a translator never has to see a
tag and why the content files can be checked for having none. Both files have
to describe the same sections in the same shape — a test enforces it, so a
section added to one and forgotten in the other fails rather than renders half
a page.

External links live in `LINKS` in `app/content.py` and are referenced by key,
so a moved repository is one edit.

## Tests

```sh
pip install -r requirements-dev.txt
pytest
```

They live here rather than in the repository's `tests/` tree: the application
suite runs where FastAPI is not installed, and these need it. `pytest` from
this directory picks up `conftest.py` and finds them.
