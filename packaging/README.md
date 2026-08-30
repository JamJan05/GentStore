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

The script creates a local overlay in `/var/db/repos/gentstore`, puts the ebuild in it,
registers the repository in `/etc/portage/repos.conf/gentstore.conf` and appends
`=app-portage/gentstore-9999 **` to `/etc/portage/package.accept_keywords/gentstore`. It prints
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

### There is no Manifest, and none is needed

There is no `SRC_URI` anywhere in the overlay, so there are no files to checksum.
`thin-manifests = true` in `layout.conf` settles the matter: `ebuild ... manifest` is not needed
for anything. Should a release ebuild with a tarball ever appear — then it will be.

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
