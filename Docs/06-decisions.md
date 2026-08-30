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
