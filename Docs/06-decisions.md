# 06 — Design decisions

Short records of decisions, with the reason and the alternatives that were rejected. New
decisions are appended at the end; old ones are never deleted — if something changes, we add an
entry saying “supersedes D-xx”.

---

### D-01 · PyQt6 rather than GTK4/PyGObject

**Decision:** PyQt6 with Qt Widgets.

**Reason:** The mock-up is a dense tool-like interface with tables, trees, split panels and
multi-line lists — which is precisely what Qt Widgets is strong at and what GTK4 takes a lot of
work to reach (column views in GTK4 are considerably less convenient than a `QTreeView` with a
model). Qt also comes with a ready-made translation system, a `QProcess` that streams output,
and a `QThreadPool` — three things we need immediately.

**Alternatives:** GTK4 + libadwaita (blends into GNOME better, but has weaker tabular views and
a harder road to the mock-up's dense layout); Qt Quick/QML (prettier animations, but worse for
an interface built on tables and text, plus a second syntax to maintain).

---

### D-02 · Qt Widgets, not QML

**Decision:** Widgets.

**Reason:** The whole interface is text, lists and tables. QML shines with animation and touch;
here it would add a layer for no gain. Widgets also give native text selection and copying,
which matters — the user has to be able to copy an atom or a path into a terminal.

---

### D-03 · English sources, Polish as a translation

**Decision:** every string in the code is in English, inside `tr()`; Polish lives in
`gentstore_pl.ts`.

**Reason:** The standard direction for Qt, and the only one that allows a third language to be
added without rewriting code. The (Polish) wording from the mock-up becomes a ready-made
translation, so none of its carefully chosen phrasing is lost.

**Alternative:** Polish as the source and English as the translation — tempting, because the
mock-up is in Polish, but it inverts the Qt convention and makes outside contributions harder.

---

### D-04 · A separate privileged helper rather than `sudo` on every write

**Decision:** one small `gentstore-helper` program, started by `pkexec`, accepting a closed set
of operations as JSON.

**Reason:** It concentrates all the write logic in one short, reviewable file. Path validation,
backups and write atomicity are enforced on the privileged side, so a bug in the GUI cannot
destroy a file outside `/etc/portage`. It also gives one sensible description in the polkit
dialog instead of a series of cryptic password prompts.

**Alternatives:** `pkexec tee`/`sed` per write (fragile, easy to inject into and to overwrite
with); running the whole GUI as root (rejected — Qt as root is bad practice and far too large an
attack surface).

---

### D-05 · The `portage` API for reading, `emerge` output for operations

**Decision:** metadata, flags, masks, versions and dependencies are read from the `portage`
module; `emerge` is invoked as a process and its output parsed only where the API has no
equivalent (the `-pv` preview, build progress, `--depclean`).

**Reason:** The API is reliable and fast for reading, but resolving dependencies through
`_emerge.depgraph` means using Portage's private, unstable internals — that would tie the
application to one specific version. `emerge -pv`, by contrast, is a stable public interface
that Gentoo makes guarantees about.

---

### D-06 · `core/` with no Qt imports

**Decision:** the `core/` layer is plain Python.

**Reason:** It lets the logic be tested without a graphical environment, and it gives a
diagnostic CLI that can check the backend before a screen exists. It also has a practical side
effect: a “something is displayed wrong” bug can immediately be assigned to a layer.

---

### D-07 · A theme built from tokens in Python, not a hand-written QSS file

**Decision:** `ui/theme/tokens.py` plus a QSS generator.

**Reason:** The same palette is needed in the QSS **and** in code (colouring the log, the diff,
download-size charts). Keeping it in two places guarantees drift. On top of that, the font scale
in Settings requires recomputing the sheet on the fly.

---

### D-08 · GPL-2 as the project licence

**Decision:** GPL-2 (without “or later”), matching Portage.

**Reason:** The application is tightly bound to the Gentoo ecosystem and imports the `portage`
module (GPL-2). The same licence removes any doubt and makes an eventual path into GURU easier.

**Superseded by D-11**, which keeps the licence family and adds “or later”.

---

### D-09 · The documentation directory is named `Docs/`, capitalised

**Decision:** `Docs/`, as the repository owner asked for.

**Reason:** Consistency with what was agreed. Recorded because the convention in most projects
is `docs/`, and when adding tooling (documentation generators, CI) the capital letter has to be
kept in mind.

---

### D-10 · The repository filter narrows the whole screen, not just the list

**Decision:** the repository chosen on the “Search and install” screen — a `::repo` badge,
`name::repo` typed into the query, or the “::gentoo only” switch in hiding mode — also governs
the detail panel, the version line in the results and the atom under the buttons. To that end
`core.packages` takes a `repo` parameter in `details()` and `package_state()`.

**Reason:** The same package in two repositories is an ordinary situation, and with an identical
version number the two copies are indistinguishable. As long as the filter narrowed only the
list, the panel offered versions the chosen repository does not have at all, and `emerge` was
handed an atom without `::repo` and picked by repository priority — that is, not what was on
screen. With a narrowing active the atom is always qualified, even when the package exists in
only one repository, because that is precisely when the qualification is the substance of the
user's decision.

**Deliberately out of scope:** “Add to @world” and uninstalling still use bare `cat/pkg`. Writing
`::repo` into `world` would pin the package to a repository permanently, and that is a stronger
statement than a filter on a screen.

---

### D-11 · GPL-2-or-later, because PyQt6 is GPL-3 · supersedes D-08

**Decision:** `GPL-2.0-or-later` — the GNU GPL, version 2 or, at the user's option, any later
version. The per-file headers carry the “or later” permission, `LICENSE` keeps the GPL-2 text
unchanged, and `pyproject.toml` declares the SPDX identifier.

**Reason:** D-08 chose GPL-2 *without* “or later”, which put the project in a licence conflict it
could not distribute out of. PyQt6 is published by Riverbank under the GPL v3 or a commercial
licence — there is no LGPL or GPL-2 variant — and GPL-2-only and GPL-3 are mutually incompatible.
Adding “or later” is the smallest change that resolves this: `portage` (GPL-2) stays compatible,
GURU stays reachable, and the file the repository ships as `LICENSE` is still the right text,
because the “or later” permission lives in the file headers rather than in the licence body.

**Consequence:** the *sources* are GPL-2-or-later, but any build distributed with PyQt6 linked in
is effectively GPL-3, since that is the only version both halves can be conveyed under. The
README says so; nothing in the code has to.

**Alternatives:** relicensing to GPL-3-only (loses compatibility with GPL-2-only code and drifts
from Portage's family for no gain); buying Riverbank's commercial licence (costs money and would
make the project non-free); swapping PyQt6 for PySide6, which is LGPL (a rewrite of every import,
signal and `tr()` call, to fix a problem one clause fixes).

---

### D-12 · The release workflow owns the version number

**Decision:** a release is `Actions -> Release -> Run workflow -> 1.2.0`. `tools/release.py`
rewrites the four files that state a version — `pyproject.toml`, `gentstore/__init__.py`, the
README's version line and `CHANGELOG.md` — in one operation, and
`.github/workflows/release.yml` does everything downstream from the tag: the tarball, the
GitHub release with the changelog section as its notes, the ebuild, its `Manifest` entry, and
the republished `overlay` branch. A tag pushed by hand is picked up too, and then the tree at
that tag has to already state that version or the run refuses.

**Reason:** 1.1.0 is what the manual procedure costs. Ten steps, and two of them went wrong in
ways nothing was watching for: the README still announced 1.0.0 after the release went out, and
the release notes claimed “No functional changes” across twenty-one commits, because they were
written from a session's diff rather than from the record. Both are invisible from inside the
release — you have to go and look at the published page to find them. Neither is possible now:
the numbers are one edit, and the notes are read out of `CHANGELOG.md`, which the workflow
refuses to release empty.

**Consequence:** `CHANGELOG.md`'s `[Unreleased]` section becomes the thing to keep current as the
work happens, because it *is* the release notes. The same reasoning covers the overlay branch,
which is generated and therefore drifts the moment nothing regenerates it: a push touching
`packaging/app-portage/` republishes it, since a release alone would only ever catch up the
release ebuilds and the live one changes on its own. The version number stops being editable by hand
without a test noticing — `tests/test_release.py` fails the moment the four files disagree.

**Alternatives:** a `make release` target (same script, but it still runs on one machine with one
person's credentials, and nothing checks it ran); tagging by hand and letting the workflow react
(kept, as the second trigger, but it cannot rewrite the version because the tag is already cut);
generating the release ebuild from the live one (the two differ by four comment blocks, and a
transformation that pattern-matches prose breaks the first time somebody rewords one — copying
the previous release ebuild is exact, because a release ebuild carries no version of its own).

---

### D-13 · The search index is kept in the runtime directory, not rebuilt every start

**Decision:** `core/index_cache.py` writes the finished `SearchIndex` to
`$XDG_RUNTIME_DIR/gentstore/search-index.json` and reads it back on the next start. It is used
only when `fingerprint()` — the set of repositories, each one's location, and the modification
time of every directory directly inside it — is the same as when it was written. Without
`$XDG_RUNTIME_DIR` the file falls back to `~/.cache/gentstore/`. `GENTSTORE_INDEX_CACHE=0`
builds from Portage every time, and so does `cli --no-cache`.

**Reason:** building the index is 3.1 s on the development machine and reading it is 0.07 s, and
the answer is the same one until the tree changes. It was the longest thing the application did
before it could answer anything, and it did it again for every start of the day.

The runtime directory is the decision inside the decision. It is a tmpfs the system creates at
login and removes when the last session ends, so a cached index cannot outlive the boot that
produced it — the coarse invalidation rule is the operating system's, and nothing here has to
implement it. The fingerprint is the fine one, and it is what makes the `~/.cache` fallback
harmless rather than a second rule to reason about: a sync rewrites `metadata/` and `profiles/`,
a new `cat/pkg` in a local overlay writes its category directory, and either one moves a
timestamp the check reads.

**Consequence:** a description edited in place in an ebuild inside an existing package directory
is not noticed, because no directory above it is written. That is a local-development case, and
it already has an answer: rebuilding the index after a sync deletes the file
(`AppContext.reload_index`). What is *not* cached is the installed set — one `cpv_all()`, re-read
on load, because it changes after every install and the rest of the file does not.

**Alternatives:** pickle instead of JSON (faster to load by tens of milliseconds, and a file
format that executes what it reads, for a saving nobody can feel); Portage's own `md5-cache`
timestamps as the fingerprint (only the main repository keeps one, so every overlay would need
the directory scan anyway); an mtime check on the repository root alone (misses a package added
to a category, which is exactly the local-overlay case the check exists for); keeping the cache
in `~/.cache` only (survives a reboot, which is more than the user asked for and more than the
fingerprint was designed to be the only guard against).
