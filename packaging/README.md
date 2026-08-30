# Packaging

Two ways to install. They differ in one thing, but a fundamental one: whether Portage knows that
Gentstore exists.

| | `sudo make install` | overlay |
|---|---|---|
| the application code | stays in the working directory | goes into `site-packages` |
| running it | `python -m gentstore` from the repository directory | `gentstore` from anywhere |
| Portage knows about it | no | yes — it is in `@world`, visible in `qlist`, removed with `emerge` |
| updating | `git pull` | `emerge --update` |
| what for | working on the code | using it |

## The overlay

```bash
sudo packaging/make-overlay.sh
emerge --ask app-portage/gentstore
```

### Without a clone

The script runs on its own, which is what the README's one-liner relies on:

```bash
curl -fsSL -O https://raw.githubusercontent.com/JamJan05/GentStore/main/packaging/make-overlay.sh
less make-overlay.sh
sudo bash make-overlay.sh
```

Nothing about the result differs. The ebuild is live, so `git-r3` does the cloning either way;
the only thing a clone was ever needed for is the two files the script cannot generate — the
ebuild and its `metadata.xml`. Without one it downloads them from `raw.githubusercontent.com`
into a `mktemp -d` that a trap removes on exit, and refuses to go on unless what came back
contains an `EGIT_REPO_URI` line. A captive portal's login page is a 200 as far as the shell is
concerned, and it should not be able to become an ebuild.

`GENTSTORE_REF` selects the branch or tag to fetch from (default `main`). `--local` is the one
option that needs a clone, and it says so rather than quietly building from the remote instead.

The piped form — `curl … | sudo bash` — works and is documented, but the two-step version above
is the one to prefer. Everything else in this project refuses to let something reach root
unread; the installer should not be the exception.

### Synced or pinned

By default the overlay is **synced**: `repos.conf` gets `sync-type = git` pointing at the
`overlay` branch, and the first `emaint sync -r gentstore` clones it. Every later ebuild then
arrives with an ordinary `emerge --sync`, and nobody has to come back to this script.

That branch is generated, never hand-edited — `packaging/publish-overlay.sh` rebuilds it from
`packaging/app-portage/` and force-pushes. Portage syncing a git repository treats its root as
the repository root, and the root of this one is the application, so the ebuild tree needs a
branch of its own. Generating it is what stops the two copies drifting; an overlay serving an
ebuild that no longer matches the source is a bug nobody notices until a build fails.

`--no-sync` is the older behaviour: the ebuild is copied in once and `auto-sync = no` tells
Portage to leave it alone. The right choice if you want a package that cannot change under you
until you say so.

### Which version, and how it updates

The accept-keywords file carries two lines — `=app-portage/gentstore-9999 **` for the live
ebuild, which has no keywords at all, and `app-portage/gentstore ~amd64` for the releases, which
a stable system would otherwise refuse. Either works:

```bash
emerge --ask app-portage/gentstore          # the release
emerge --ask =app-portage/gentstore-9999    # the git tip
```

A release updates through `--sync` and then `--update @world`, like anything else. A live
install does not: `9999` never changes, so `--update` sees nothing to do. `git-r3` sets
`PROPERTIES="live"`, which puts the package in Portage's own `@live-rebuild` set:

```bash
emerge --ask @live-rebuild
```

That rebuilds every live package unconditionally. `app-portage/smart-live-rebuild` asks upstream
first and rebuilds only what actually moved.

### What it writes

The script registers the repository in `/etc/portage/repos.conf/gentstore.conf` and writes
`/etc/portage/package.accept_keywords/gentstore`; in `--no-sync` mode it also creates
`/var/db/repos/gentstore` and puts the ebuild there itself. It prints
every file it writes, does not quietly overwrite somebody else's `gentstore.conf` (it stops and
says where to look), and a second run changes nothing. It leaves `emerge` to you — it does not
run it itself.

Undoing it:

```bash
sudo packaging/make-overlay.sh --remove   # the overlay itself
emerge --deselect --unmerge app-portage/gentstore
```

### Where the build comes from

The ebuild is **live** (`git-r3`, empty `KEYWORDS`) — until there is a release there is nothing
to point a tarball at. It clones from `EGIT_REPO_URI`, that is, from GitHub, **not** from your
working directory. Uncommitted changes will not make it into the package.

### When root cannot manage the clone

`git-r3` fetches as the `portage` user, without your credentials. A private repository therefore
ends in the `unpack` phase:

```
fatal: could not read Username for 'https://github.com': terminal prompts disabled
 * ERROR: app-portage/gentstore-9999::gentstore failed (unpack phase)
```

This is not a bug in the ebuild — there was nothing it could reach. Two ways out:

**Make the repository public.** Then a plain `sudo packaging/make-overlay.sh` works, and anybody
can install Gentstore with the same command.

**Build from a local clone:**

```bash
sudo packaging/make-overlay.sh --local
```

`--local` substitutes `EGIT_REPO_URI` in the copy that goes into the overlay — not in the one in
the repository. `grep EGIT_REPO_URI` on the installed ebuild will always tell the truth about
where the code came from. It still builds the **last commit**, not the working tree: `git-r3`
clones a repository, it does not copy files.

Without `--local` the script now checks at the start whether the address can be read without
credentials, and says so straight away — rather than letting you discover it three minutes later
in the `unpack` phase. With `--local` it checks the other direction: whether the `portage` user
can read your directory at all (home directories are often `0700`).

Newer commits:

```bash
emerge --ask --update app-portage/gentstore
```

`git-r3` detects on its own that the branch has moved. The overlay has `auto-sync = no`, so
`emaint sync -a` skips it — rightly, because there is nothing there to sync.

### The Manifest

`thin-manifests = true` in `layout.conf` drops the checksums for ebuilds and auxiliary files,
but **not** the `DIST` lines: a release ebuild carries `SRC_URI`, and Portage refuses a distfile
it cannot verify. So `packaging/app-portage/gentstore/Manifest` holds one `DIST` entry per
release tarball, and `publish-overlay.sh` refuses to publish an ebuild whose entry is missing
rather than shipping an overlay that fails at fetch time.

The entry is generated from the asset **as GitHub serves it** — downloaded back and compared
byte for byte against what was uploaded — because the Manifest has to describe the file a user
receives, not the one on the maintainer's disk.

The live ebuild has no `SRC_URI` at all, so nothing about it appears there.

## What the ebuild installs besides the Python package

| Path | What it is |
|---|---|
| `/usr/libexec/gentstore/gentstore-helper` | writing to `/etc/portage` |
| `/usr/libexec/gentstore/gentstore-launcher` | running `emerge` and friends |
| `/usr/share/polkit-1/actions/org.gentoo.gentstore.policy` | two named polkit actions |
| `/usr/share/applications/gentstore.desktop` | the menu entry |
| `/usr/share/icons/hicolor/scalable/apps/gentstore.svg` | the icon |

That is exactly what `sudo make install` installs. Through the overlay you additionally get the
Python package itself and a `gentstore` command in `/usr/bin`.

The translations (`.qm`) are not kept in the repository — the ebuild generates them in
`python_prepare_all`, that is, **before** the wheel is built. This is not a matter of taste:
under PEP 517 the wheel is built from the source tree, so a directory generated later would not
make it into the package.

The `test` USE flag runs the whole test suite under `QT_QPA_PLATFORM=offscreen`. The tests read
the real Portage tree and the installed package database; if the sandbox cuts something off from
them, `USE="-test"` skips them.

## The state of the ebuild

It has not been through Gentoo review and has not been submitted to any repository. It is here so
that dropping Gentstore into an overlay is a matter of copying rather than of detective work. To
reach the Gentoo tree it lacks at least a keyworded release and a `metadata.xml` with a real
maintainer.
