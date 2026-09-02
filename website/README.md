# The GentStore website

The landing page for `app-portage/gentstore`, and the small FastAPI application
that serves it. Built from the design canvas the project was mocked up in; the
colours, type and spacing are the tokens in `gentstore/ui/theme/tokens.py` on
the `main` branch, so the page and the application window look like the same
piece of software.

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
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 \
    --proxy-headers --forwarded-allow-ips 127.0.0.1
```

The page is static once rendered, so anything that can sit in front of a WSGI
or ASGI server — nginx, Caddy, a CDN — can cache it whole.

`GENTSTORE_WEB_BASE_URL=https://www.gentstore.dev` makes the canonical link, the
`hreflang` alternates and the preview image absolute, which is what a crawler
and a link unfurler want. The links a visitor clicks stay relative either way,
so the page is correct on whatever origin answers for it.

## Building the static site

The page does nothing per request that cannot be done once, so it can be
rendered to files and served without a Python process anywhere:

```sh
pip install -r requirements-build.txt
python build.py --base-url https://www.gentstore.dev
```

That writes `dist/` beside the repository root: `pl.html` and `en.html`,
a `404.html`, the content as JSON under `api/content/`, and
the stylesheet, screenshots and icon copied in. It renders by walking the
application with a test client rather than by driving the templates directly,
so a built page is the served page byte for byte — and everything the tests
assert about one is true of the other.

Two files are for Cloudflare Pages rather than for a browser: `_redirects`
keeps the API at `/api/content/pl`, the path the application answers at, and
`_headers` sets cache lifetimes in hours — nothing here is fingerprinted, so an
updated screenshot has to be able to reach a returning visitor.

The one thing a file cannot answer is which language `/` should go to. The
served site decides that from `Accept-Language`; the built one decides it in
`dist/index.html`, from `navigator.languages`, which is the same list the
browser puts in that header. It costs a hop, and a crawler that runs no script
reads the meta refresh to `/pl`.

### On Cloudflare

`wrangler.jsonc` at the repository root describes the deployment: the assets
directory, `/pl` served from `dist/pl.html`, and `dist/404.html` for anything
missing. The project settings in the dashboard supply the rest:

| Setting | Value |
| --- | --- |
| Build command | `pip install -r website/requirements-build.txt && python website/build.py` |
| Deploy command | `npx wrangler deploy` |
| Variable | `GENTSTORE_WEB_BASE_URL` = `https://www.gentstore.dev` |
| Variable | `PYTHON_VERSION` = `3.12` |

A push to the branch builds and publishes. Nothing runs between deploys, so
the site does not depend on any machine of yours being awake.

## Behind a Cloudflare tunnel

The other way to serve it, and the one to reach for if the site ever grows
something that has to run per request. It costs a machine that stays on: the
page is reachable exactly as long as this one is.

The deployment this was written for: `cloudflared` holds an outbound connection
to Cloudflare, and Cloudflare hands requests back down it. Nothing listens on a
public address, no port is forwarded, and the machine can sit behind any
router. Two services, both under `deploy/`, both OpenRC:

```sh
# 1. The virtualenv the service runs out of.
python -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. The website.
sudo install -m 0755 deploy/gentstore-website.initd /etc/init.d/gentstore-website
sudo install -m 0644 deploy/gentstore-website.confd /etc/conf.d/gentstore-website
sudoedit /etc/conf.d/gentstore-website          # the path, the user, the port
sudo rc-update add gentstore-website default
sudo rc-service gentstore-website start

# 3. The connector.
sudo install -m 0755 deploy/cloudflared.initd /etc/init.d/cloudflared
sudo install -m 0600 deploy/cloudflared.confd /etc/conf.d/cloudflared
sudoedit /etc/conf.d/cloudflared                # TUNNEL_TOKEN, from the dashboard
sudo rc-update add cloudflared default
sudo rc-service cloudflared start
```

Then, in the Cloudflare Zero Trust dashboard under Networks → Tunnels → the
tunnel → Public Hostname, add the hostname with type `HTTP` and the URL
`127.0.0.1:8000` — the scheme comes from the type, so the URL field carries the
host and the port and nothing else. Write the address numerically rather than
as `localhost`: uvicorn binds `127.0.0.1`, and `localhost` resolves to `::1`
first on a machine with IPv6, which answers a working setup with a 502.

That routing lives in the dashboard, not on this machine — a token-run
connector takes its ingress rules from Cloudflare.

Two things worth being deliberate about:

- **The token is a credential.** It authorises a connector for the tunnel, so
  `/etc/conf.d/cloudflared` is mode 0600. `cloudflared service install` writes
  the token into a world-readable init script instead; `deploy/cloudflared.initd`
  exists to avoid that, and to put the connector under `supervise-daemon`.
- **The site binds the loopback.** The tunnel is the one way in. Nothing else
  on the machine or on the local network can reach uvicorn, so nothing has to
  be firewalled off it.

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

They live under `website/` rather than beside the application's own suite on
`main`: that one runs where FastAPI is not installed, and these need it.
`pytest` from this directory picks up `conftest.py` and finds them.
