# GentStore — the website

This branch carries the site at <https://www.gentstore.dev> and nothing else.
The application it describes — the graphical front-end for Portage that the
page is about — lives on [`main`](https://github.com/JamJan05/GentStore/tree/main).

`Web` is a deployment branch, not a development one. It was made by removing
everything from `main` that serving the page does not need, so merging it back
would delete the application; treat the two as separate lines of work.

```
website/                 the site: a FastAPI application and its content
  app/                   routes, templates, stylesheet, the one script
  content/               the copy, one JSON file per language
  build.py               renders the whole site to dist/
wrangler.jsonc           how Cloudflare serves what build.py produced
  tests/                 40 tests over the routes, the content and the build
Docs/screenshots/        the six screenshots the page shows
data/icons/              the application icon, which is also the favicon
```

The screenshots and the icon stay where they are on `main` rather than being
copied into the site: the application takes them, and the page serves the same
files.

## How it is served

Cloudflare builds this branch on every push and serves the result as static
assets. The page is static once rendered, so nothing runs between deploys and
the site does not depend on any machine here being awake.

## Working on it

```sh
cd website
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --reload
```

That is a preview for editing, not the thing the public reaches. To see exactly
what gets published, `python build.py` and open `dist/`.

`website/README.md` has the rest — the routes, how the content files work, and
the build.

## Licence

GNU GPL v2 or later, the same as the application. See `LICENSE`.
