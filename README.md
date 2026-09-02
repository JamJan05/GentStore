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
  deploy/                OpenRC services for uvicorn and the tunnel
  tests/                 33 tests over the routes and the content
Docs/screenshots/        the eight screenshots the page shows
data/icons/              the application icon, which is also the favicon
```

The screenshots and the icon stay where they are on `main` rather than being
copied into the site: the application takes them, and the page serves the same
files.

## Standing it up

```sh
cd website
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --reload
```

`website/README.md` has the rest — the routes, how the content files work, and
the Cloudflare tunnel the live site is served through.

## Licence

GNU GPL v2 or later, the same as the application. See `LICENSE`.
