# 05 — Session plan

The work is split into sessions of roughly equal size. Every session:

- ends in a **state that can be run** (or, for purely back-end sessions, checked with the
  command-line diagnostic tool);
- has a clear **completion criterion** — something that can be shown and verified;
- ends with a tick in this file and a short note on what departed from the plan;
- **does not end with a commit** — a commit only follows the repository owner's explicit
  consent.

Legend: ☐ to do · ☑ done

---

## ☑ S0 — Documentation and decisions

Surveying the environment, analysing the mock-up, settling the architecture, writing `Docs/`.

**Settled:** PyQt6 + Qt Widgets · English sources with a `pl` translation · a root helper through
pkexec · the split into the `core` / `models` / `ui` / `runner` layers.

**Verified on the system:** `portage 3.0.81.3`, Python 3.14.6, `dev-python/pyqt6` in the tree
with a `PYTHON_COMPAT` covering `python3_14` (not installed yet), `pkexec`, `eselect`, `emerge`,
`qlist`, `glsa-check` and `dispatch-conf` available. No `cpuid2cpuflags` (the
`app-portage/cpuid2cpuflags` package) — the `CPU_FLAGS_X86` suggestion has to cope with that.

---

## ☑ S1 — The foundation

The project skeleton and an empty but working application.

- `pyproject.toml`, the `gentstore/` package layout, `.gitignore`, the licence (GPL-2, like
  Portage), `README.md`.
- `app.py`: `QApplication`, the Fusion style, the palette, loading the QSS, CLI arguments
  (`--lang`, `--debug`).
- `ui/theme/tokens.py` plus a QSS generator built from the tokens in
  [02-ui-design.md](02-ui-design.md).
- `ui/main_window.py`: the menu, a toolbar with the “::gentoo only” switch, a sidebar with nine
  entries and their badges, a `QStackedWidget` with nine placeholder pages, a status bar.
- The i18n infrastructure: `tr()` everywhere, `retranslate_ui()` as the mandatory pattern,
  `gentstore_pl.ts` / `gentstore_en.ts`, a language switch in the **View** menu that works
  without a restart.
- `settings.py` (QSettings), logging to `~/.local/state/gentstore/gentstore.log`.
- The `Ctrl+1..9` keyboard shortcuts.

**Criterion:** `python -m gentstore` opens a window that looks like the mock-up (with empty
pages), switching pages works, and switching the language changes every string immediately.

**Met.** The window renders as in the mock-up, the nine screens switch via shortcuts and from the
sidebar, and `app.apply_language()` translated the whole window without a restart and without a
single manual `retranslate_ui()` call — confirmed by the test
`test_switching_language_retranslates_the_window`. 6/6 tests pass, `ruff check` clean.

---

## ☑ S2 — The Portage layer (read-only)

The back end without a GUI — the heart of the application.

- `core/portage_env.py`: a shared `portage.config` plus `porttree` / `vartree` / `bintree`, with
  an explicit `reload()`.
- `core/packages.py`: building the search index, searching by name / category / description, the
  version list with keywords and slots, package metadata (description, homepage, LICENSE, SLOT,
  size, originating repository), detecting the installed version.
- `core/worldset.py`: `@world` and the installed list from `vartree`.
- `core/repos.py` (the reading half): the repository list from `repos.conf` plus priorities and
  sync dates.
- The threading adapter `ui/tasks.py` (`QRunnable` + signals) — the single place through which
  the GUI calls `core`.
- The diagnostic tool `python -m gentstore.core.cli search mpv` and friends, for checking the
  back end without a GUI.
- The first tests (`tests/`) covering parsing and searching.

**Criterion:** the CLI tool returns correct data for a few real packages from the system; the
index builds in under about 5 s and does not block.

**Met.** `python -m gentstore.core.cli` has seven commands (`info`, `repos`, `index`, `search`,
`show`, `world`, `installed`), each with a `--json` variant. An index of 21,711 packages from
three repositories builds in **2.4 s**, and a query takes about **5 ms**. 52/52 tests pass,
`ruff check` clean.

---

## ☑ S3 — The “Search and install” screen (without USE flags)

The first screen with real data.

- The `ui/pages/split_page.py` base class (a 352 px list + details).
- A search box with a result counter, repository filters as “pills”, and a result list with the
  repo badge, the description, the version and the state.
- The detail panel: the atom, the repo badge, information about the installed version, the
  description, homepage, LICENSE, SLOT, size, and the version picker.
- The `repo_badge.py` widget.
- The “::gentoo only” filter in mode (a) — hiding in the GUI, together with a note saying “N
  packages from overlays hidden”.
- The action buttons present, but not yet running anything.

**Criterion:** typing “mpv” gives a real list from the system, selecting a package shows real
metadata, and the repository filter works.

**Met.** “mpv” gives 25 results from three repositories; `media-video/mpv` shows the
description, homepage, `LICENSE`, `SLOT=0/2`, 6.9 MiB to download and two versions with their
keywords marked. The repository filters and “::gentoo only” in mode (a) narrow the list to 7
entries with the note “18 packages outside ::gentoo hidden”. 71/71 tests pass, `ruff check`
clean.

---

## ☑ S4 — Privileges and running commands

The moment the application stops being a browser.

- `helper/gentstore_helper.py` with a closed set of operations and path validation
  ([04-privileges.md](04-privileges.md)).
- `data/org.gentoo.gentstore.policy`, installing the helper, `runner/privilege.py` with the
  `sudo` fallback.
- `runner/command.py`: `QProcess`, streaming stdout/stderr, the exit code, interruption through
  `SIGINT` → `SIGTERM`.
- `runner/emerge.py`: `pretend`, `install`, `unmerge`.
- The `log_view.py` widget with coloured lines and auto-scrolling; the log window as a bottom
  panel.
- `core/backup.py` plus a copy of `/etc/portage` before the first change, and a “Backup” section
  in the sidebar.
- Wiring up the S3 buttons: “Pretend”, “Install”, “Uninstall”.

**Criterion:** installing and uninstalling a small package works end to end, with a live log and
the ability to interrupt; the `/etc/portage` copy is created.

**Met as far as it can be without root** — see the note below. Built and tested: the helper (34
tests, including every refusal), the launcher with its allow-list of programs, interruption
through `SIGINT` (verified on a live process), the live log, and `emerge -pv` from the GUI end
to end on real data. 145/145 tests, `ruff check` clean.

---

## ☑ S5 — USE flags

The application's most distinctive feature, so it gets a session of its own.

- `core/useflags.py`: `IUSE`, the current state, the flag's origin (profile / `make.conf` /
  `package.use`), `use.force` / `package.use.force` (locked), `use.mask` (dimmed, with the
  reason), and descriptions from `use.desc`, `use.local.desc` and `metadata.xml`.
- `core/required_use.py`: a parser for `^^ ( … )`, `?? ( … )`, `|| ( … )` and `flag? ( … )`
  expressions, together with validation of the current selection and a readable message saying
  which condition was broken.
- `core/depgraph_hints.py`: extracting the conditional `flag? ( … )` dependencies from
  `DEPEND`/`RDEPEND`/`BDEPEND` → the “Pulls in” list.
- A generator for the “what does this flag give you” explanation — assembled from the
  description, the dependency list and a “without this flag…” sentence, all through `tr()` (the
  templates are ours, the data is Portage's).
- The `use_flag_row.py` widget with an unfoldable detail panel.
- A `REQUIRED_USE` section with live validation (✓ / ✗ next to each condition).
- `core/confedit.py` plus the `write_preview.py` widget: preview the line → write through the
  helper → report.

**Criterion:** for `media-video/mpv` every flag shows with the correct origin and description,
ticking `vulkan` shows a real `media-libs/vulkan-loader` under “Pulls in”, `REQUIRED_USE`
validation reacts immediately, and saving creates exactly one correct line in
`/etc/portage/package.use/mpv`.

**Met.** 47 flags for `media-video/mpv` with the correct origin and description; unfolding
`vulkan` shows `media-libs/vulkan-loader[X?,wayland?]` and `dev-util/vulkan-headers`; breaking
`|| ( cli libmpv )` immediately blocks the write with an explanation; and the write plan is
exactly `media-video/mpv jack -vulkan` in `/etc/portage/package.use/mpv`. The whole write path —
plan → JSON → a real helper subprocess — is tested against a temporary directory. 213/213 tests,
`ruff check` clean.

---

## ☑ S6 — Masks, keywords and licences

- `core/masking.py`: identifying the reason for a block — `package.mask` (with the maintainer's
  text and comment), missing keywords, `~arch`, a profile mask, a licence.
- `core/licenses.py`: `ACCEPT_LICENSE`, licence groups (`@FREE`, `@BINARY-REDISTRIBUTABLE`…),
  loading the full licence text from `licenses/`.
- The block notice in the package detail panel (S3), with the reason, an explanation and an
  action.
- The “Masks and licences” screen with unfoldable entries.
- Writes: `package.accept_keywords`, `package.unmask`, `package.license` — each through the same
  three beats of preview → write → report.
- A licence reader with scrolling and an “Accept” button, making clear that the acceptance covers
  one package rather than the whole licence group.

**Criterion:** a masked package on the system shows the real reason; unmasking `~arch` appends
the correct line and, after a refresh, the package can be installed.

**Met.** `acct-group/croc` shows its mask together with Sam James's note and the path
`profiles/package.mask`; `dev-libs/zydis-9999` — a missing keyword and the line
`=dev-libs/zydis-9999 **`; `app-admin/vault-1.18.4` — a `BUSL-1.1` licence block, the reader with
the full text (3,403 characters) and the line `=app-admin/vault-1.18.4 BUSL-1.1` in
`package.license`. The “Masks and licences” screen reads back 14 existing entries from this
system and allows them to be removed. 248/248 tests, `ruff check` clean.

---

## ☑ S7 — Repositories and overlays

- `core/repos.py` (finished): fetching and parsing `repositories.xml`, caching in
  `~/.cache/gentstore/`, searching by name and description, the enabled status.
- The “Repositories” screen: a repo list with checkboxes, priority, URL, package count and sync
  date.
- An overlay browser with a search box (the scenario “type `steam` → one click → `steam-overlay`
  enabled and synced”).
- `eselect repository enable` + `emaint sync -r` through the runner, showing the created
  `/etc/portage/repos.conf/<name>.conf` file and its full contents.
- Adding an overlay from outside the list (`eselect repository add <name> git <url>`) with a
  warning about the unofficial source.
- Removing an overlay (`eselect repository remove -f`) with a warning about the packages
  installed from it.
- The “::gentoo only” switch in mode (b): a `*/*::<repo>` entry in
  `/etc/portage/package.mask/<repo>` plus a warning about which packages will stop receiving
  updates. Each overlay is enabled and disabled separately.

**Criterion:** GURU can be enabled and synced from the GUI; both modes of the “::gentoo only”
switch work and show exactly what they change.

**Met as far as it can be without root.** The catalogue of 459 repositories is searchable by name
and description; “Refresh” runs `eselect repository list` through the runner — 461 lines in the
log and the catalogue reloaded, the whole command → log → reload chain verified live. The enable
path builds `eselect repository enable <name>` + `emaint sync -r <name>` and is shown in the
confirmation dialog before it runs. Mode (b) of the “::gentoo only” switch produces the plan
`*/*::guru` → `/etc/portage/package.mask/guru`, with a warning about how many installed packages
will stop receiving updates. 294/294 tests, `ruff check` clean.

---

## ☑ S8 — The system update

The largest single functional session.

- A wizard screen with six steps, each runnable separately, with its state and its command.
- Step 1 — `emaint sync -a` with a log.
- Step 2 — `core/news.py`: unread news items, marking those that concern installed packages,
  marking items as read.
- Step 3 — `core/emerge_parse.py`: parsing `emerge -pvuDN --changed-use @world` into a table
  (package, old → new version, USE changes, size, binary source or compilation, reason) plus a
  summary.
- Step 4 — `emerge -vuDN @world` with a progress bar (package number / package count) and
  interruption.
- Step 5 — `--depclean --pretend` with the list and the reasons, a confirmation, then
  `@preserved-rebuild`.
- Step 6 — moving on to the configuration files screen (S9).
- The GLSA panel: `glsa-check -l affected` with a list and a fix (with a readable message when
  `gentoolkit` is missing).
- Handling failure: finding the `build.log`, extracting the fragment with the error, and hints
  for the usual cases (a block, a slot conflict, a missing USE flag, an unaccepted licence).

**Criterion:** the full update cycle runs from the GUI, the preview table matches the output of
`emerge -pvuDN`, and interrupting mid-run works cleanly.

**Met as far as it can be without root.** The unprivileged steps ran live: the preview
(`emerge -pv` → 8 rows in the table, with sizes and versions matching the output), `--depclean -p`
(16 packages, with the remove button appearing only after the check), the GLSA panel (3,838
advisories analysed, 0 affecting this system), and the news (32 unread, each with the reason it
is relevant, plus a badge in the sidebar). Interruption was verified in S4 on a live process.
343/343 tests, `ruff check` clean.

---

## ☑ S9 — Configuration files (`._cfg`)

- `core/cfgfiles.py`: finding `._cfg0000_*` files (taking `CONFIG_PROTECT` and
  `CONFIG_PROTECT_MASK` into account), linking them to a package, and counting the changed
  lines.
- The `diff_view.py` widget.
- A screen with the list and the diff preview.
- The “Apply the new one” / “Keep the old one” / “Merge by hand” actions (the last one — calling
  an editor, or a simple three-way editor in the window), archiving the previous version to
  `/etc/config-archive`.

**Criterion:** after an update that leaves a `._cfg` behind, both decisions work correctly, and
the `._cfg` file only disappears once a decision has been made.

**Met.** Both decisions — and the third one, merging — were tested through the real helper
against a temporary directory: “take the new one” replaces the file and archives the previous
version, “keep mine” removes only the candidate, and “save the merge” writes the content from the
editor. In every case the `._cfg` file disappears only after the decision. The screen was
verified against a prepared `/etc` with two pending files: the difference, the `+2 −1` counters,
and the sidebar badge. 373/374 tests — one deliberately red, see below.

---

## ☑ S10 — `make.conf` and the profile

- `core/makeconf.py`: reading variable values while preserving each line's position in the file;
  replacing a single line without touching the rest.
- The “Portage settings” screen: `MAKEOPTS`, `USE`, `ACCEPT_KEYWORDS`, `ACCEPT_LICENSE`,
  `VIDEO_CARDS`, `CPU_FLAGS_X86`, `FEATURES`, `EMERGE_DEFAULT_OPTS` with suggestions (among them
  a `MAKEOPTS` suggestion from the core count, and `CPU_FLAGS_X86` from `cpuid2cpuflags` if it is
  present).
- A diff preview before the write plus the write through the helper (`replace_line`).
- The “Profile” screen: `eselect profile list`, marking the current one, and setting the chosen
  one with a warning about the consequences.

**Criterion:** changing `MAKEOPTS` shows a correct diff and writes one line, leaving the comments
in `make.conf` alone.

**Met.** Clicking the `-j15 -l28` suggestion produces a diff with one line removed and one added,
the comment “Two jobs per core was too many…” stays in context, and the write plan is a
`replace_line` with the pattern `^\s*MAKEOPTS=`. The profile screen reads 54 profiles from
`eselect profile list` through the runner and marks the current one. 406/407 tests — one
deliberately red (a stale copy of the helper, see S9).

---

## ☑ S11 — elog, `@world`, installed packages

- `core/elog.py`: reading `/var/log/portage/elog/`, splitting it into entries (package, date,
  kind, text), colouring `einfo`/`ewarn`/`eerror`.
- The “elog messages” screen with a list and the text; automatically showing new messages after a
  finished installation or update.
- The “@world set” screen: the list from `/var/lib/portage/world`, removing an entry (with an
  explanation that this does not uninstall the package), and next to it the installed list with a
  filter, version, size and repository.

**Criterion:** messages appear by themselves after an installation, and removing an entry from
`@world` changes what `--depclean --pretend` does.

**Met as far as it can be without root.** The elog screen reads 140 real entries from this
machine's `summary.log`, each with its class and phase, with filters and a sidebar badge; it
reloads itself after every finished command. The `@world` screen shows 29 entries alongside 1,022
installed packages. Removing an entry builds `emerge --deselect <atom>` — a privileged command,
so it was not executed; the confirmation dialog says plainly that it uninstalls nothing.
426/427 tests.

---

## ☑ S12 — Binary packages, polish, release

- Binary package support: the `--getbinpkg` switch, editing `binrepos.conf`, marking in the
  update preview which packages will arrive as binaries and which will be compiled.
- Restoring an `/etc/portage` copy from the GUI (with a diff before the restore).
- The Settings dialog: language, font scale, how privileges are raised, the form of the backup,
  and how many copies to keep.
- A full i18n pass: bringing `gentstore_pl.ts` to 100 %, and a test that detects strings without
  `tr()`.
- Packaging: `gentstore.desktop`, the icon, installing the helper and the polkit file, a draft
  ebuild for a private overlay.
- `README.md`: dependencies, installation, running it, screenshots.
- The final review: behaviour with the optional dependencies missing, with an empty
  `/etc/portage`, with no network, and when interrupted at every step.

**Criterion:** a clean installation on a second Gentoo system works from the README with no
manual corrections.

**Met as far as it can be verified here.** The README reduces installation to four commands
(`emerge`, `git clone`, `tools/i18n.py compile`, `sudo make install`); `make install` puts down
the helper, the launcher, the polkit policy, the `.desktop` entry and the icon, and
`desktop-file-validate` passes. Behaviour when things are missing is tested separately: an empty
`/etc/portage`, no `glsa-check`, no `cpuid2cpuflags`, no overlay catalogue, no `pkexec` and no
`sudo`, and no installed helper — 23 tests in `tests/test_degradation.py`. What cannot be checked
here: **the clean installation on a second machine itself**, because there is only one.
455/455 tests, `ruff check` clean, the translation catalogue at 100 % (406 messages).

---

## What is left

The S0–S12 plan is done. What could not be closed out from this session, and what naturally
follows:

**For the repository owner to verify**

- **The privileged path, live.** `pkexec` needs an interactive authentication agent, so no write
  to `/etc/portage` and no `emerge` that installs anything has been run end to end. Everything
  around it is tested, including the helper protocol against a real subprocess. The minimal
  run-through: `python -m gentstore` → `app-misc/hello` → *Install* → *Uninstall*, then change a
  USE flag and *Save*.
- **A clean installation on a second machine**, following the README.

**Natural next steps**

- A release: a tag, a tarball, and an ebuild pointing at it instead of at `git-r3`.
- Binary packages currently have a switch and a preview; editing `binrepos.conf` from the GUI
  lives in `core/binrepos.py` (`plan_add`, `plan_remove`) and is waiting for a screen.
- The “Repositories” screen could show binhosts alongside ordinary repositories.
- The screenshots in the README are refreshed by `tools/readme_shots.py` (described in
  [02-ui-design.md](02-ui-design.md) §9). Two of them — the update preview and the `._cfg` files
  — only show anything on a machine that has pending updates or a pending `._cfg`; on a
  freshly updated system they come out as empty panels. It is worth taking a full set on a real
  graphical session at release time. The pictures currently in the repository were also taken
  with the interface in Polish, from when this documentation was Polish too.

## Order and dependencies

```
S1 ─► S2 ─► S3 ─┬─► S4 ─┬─► S5 ─► S6
                │       ├─► S7
                │       └─► S8 ─► S9
                └─────────► S10, S11
                                  └─► S12
```

S4 (privileges) is the bottleneck: without it, no session that writes anything makes sense. S10
and S11 are largely independent of S5–S9 and could be moved, should something in the middle turn
out to be bigger than it looks.

## Implementation notes

*(filled in after each session: what went differently from the plan, which decisions had to
change)*

- **S0** — no departures. A note for later: `dev-python/pyqt6` has to be installed before S1
  (`emerge --ask dev-python/pyqt6`).

- **S1** — the scope was completed in full, plus four things added along the way:

  1. **`gentstore/ui/tasks.py` came into being already** (the plan had it in S2). It was needed
     because initialising `portage` takes a few seconds and froze the window at startup.
  2. **`gentstore/sysinfo.py`** — unplanned, but without it the menu bar and the status bar would
     have had to show dummies. It reads the Portage version, ARCH, the profile, the sync date,
     `MAKEOPTS`, `FEATURES` and the size of `@world`. In S2 it moved to the shared handle from
     `core/portage_env.py`.
  3. **`tools/screenshot.py`** — renders the window to PNG through the `offscreen` platform. It
     lets layout changes be inspected without starting a graphical session; useful in every
     subsequent session and for the README pictures.
  4. **`tests/test_smoke.py`** — 6 tests, run off-screen.

  Changes from the original design:

  - `MainWindow.load_system_info()` is called explicitly after `show()` rather than from the
    constructor — a constructor that quietly starts I/O is hard to test.
  - The sidebar width **adapts** to the longest label (capped at 1.6 × 206 px). At 130 % scale
    and in Polish, a fixed 206 px was cutting off “Aktualizacja systemu”.
  - `sysinfo.collect()` is cached and guarded by a lock — Portage's configuration objects do not
    tolerate parallel initialisation.

  Three bugs caught only on the running application, worth remembering:

  - A `QRunnable` with no reference held could be collected by the GC before it managed to
    deliver its result — hence the `_pending` registry and `setAutoDelete(False)` in `tasks.py`.
  - A worker thread still running as the process shut down ended in a hard `abort`. Hence
    `wait_for_tasks()` called after `app.exec()`.
  - `QMenuBar` measures a corner widget once, at the moment it is installed. The label with the
    system information, filled in later, kept the width it had before being filled and showed a
    single truncated letter — it has to be reinstalled after the text changes.

- **S2** — the scope was completed in full. Departures and things worth remembering:

  1. **We do not use the global `portage.settings` / `portage.db`.** They are built when the
     module is imported, they cannot be reloaded, and modifying them would leak into every other
     piece of code in the process. `core/portage_env.py` calls `portage.create_trees()` and keeps
     its own set, so `reload()` really does read the configuration afresh.
  2. **The index is built from `cp_list()`, not from a loop over repositories.**
     `portdbapi.cp_list(cp)` returns one entry per (version, repository) pair, and each carries a
     `.repo` attribute — that one call gives both the version list and the repository assignment.
  3. **`aux_get()` without `myrepo=` lies about a package that lives in two repositories.** For
     `dev-libs/zydis-4.1.1` (present in both `::gentoo` and `::guru`) it returns the metadata of
     the higher-priority repository, regardless of which cpv it was given. We pass
     `myrepo=cpv.repo` everywhere.
  4. **`::gentoo` has priority `-1000`, while overlays have `None`** — that is, an overlay *beats*
     the main tree. We take the order from `repositories.prepos_order`, so that it agrees with
     what `emerge` itself does.
  5. **A package name can be ambiguous.** `portage` is `acct-group/portage`, `acct-user/portage`
     and `sys-apps/portage`. In that case `resolve_cp()` **does not guess** — it returns `None`,
     and `matching_cps()` gives a list to show the user.
  6. **`RESTRICT` stays a raw string**, because it is a conditional expression
     (`!test? ( test )`) rather than a flat list — splitting it into tokens would be a lie. `IUSE`
     and `KEYWORDS` we do split.
  7. **Live versions are recognised by an ending of four nines** (`9999`, `2.0_pre9999`). Missing
     keywords on a live version means something different from missing keywords on an ordinary
     one — hence the separate `Keywording.LIVE` value.

  Added beyond the plan:

  - **`ui/tasks.ProgressReporter`** — a progress channel passed *into* a `core` function as an
    ordinary `callable`. That lets `SearchIndex.build()` report progress while `core` still knows
    nothing about Qt.
  - **`SearchIndex.refresh_installed()`** — after an installation there is no need to rebuild the
    whole index; reading `/var/db/pkg` is enough (0.03 s).
  - **`gentstore/sysinfo.py` moved to `core/portage_env`,** as noted in S1. While at it,
    `repos.repository()` no longer counts packages by default — counting costs 0.2 s per
    repository, and the status bar does not need it.

  The result ordering changed along the way: on an equal match the **shorter** package name wins,
  and only then alphabetical order. Without that, `mpv*` put `mpvpaper` before `mpv`.

- **S3** — the scope was completed in full. Things worth remembering:

  1. **The version and state in a list row are read lazily.** The index does not know the best
     visible version, and `xmatch("bestmatch-visible")` costs 0.32 ms per package — seven seconds
     for the whole tree, 10 ms for twenty visible rows. `PackageListModel` asks for
     `package_state()` only when it draws a row, and remembers the answer.
  2. **`AppContext`** (`ui/context.py`) — unplanned but necessary: the index is built once and
     shared between screens, and the “::gentoo only” state is set by the toolbar and read by the
     screens. It is passed to `create_page()`, so no screen reaches into the window's internals.
  3. **`Page.activated()`** instead of work in the constructor. `set_page()` calls that hook only
     after `load_system_info()`, so merely creating the window still reads nothing from Portage —
     the same principle that moved I/O out of the constructor in S1. It cut the tests from 24 s
     to 3 s, because they stopped building a real index for every window.
  4. **Mode (b), “mask in Portage”, deliberately does not filter the list.** Only mode (a)
     filters. If the screen hid packages in mode (b) as well, the user would be seeing the effect
     of a change that has not been written yet.
  5. **Live versions go at the end of the version picker.** Strict version ordering would push
     `9999` to the front of almost every package, and a live ebuild is almost never what somebody
     is looking for.
  6. **`::repo` appears in the command only when the package is in more than one repository.**
     Otherwise it is noise nobody would have typed in a terminal.

  Added beyond the plan:

  - **`ui/widgets/flow_layout.py`** — Qt has no wrapping layout, and at 130 % scale the filter and
    version pills do not fit on one line.
  - **`tests/test_i18n.py`** — see the bug below.
  - **`tools/screenshot.py`** gained `--query` and **its own configuration directory**. The
    second of those was a bug fix: the tool was writing the window size, the last screen and the
    state of the switches into the user's real settings (`~/.config/Gentstore`).

  One bug worth remembering:

  - **`QT_TRANSLATE_NOOP(CONTEXT, …)` with a variable in the context position is invisible to
    `lupdate`.** After the first real run of `tools/i18n.py update`, all nine screen names ended
    up as `type="vanished"`, `lrelease` skipped them, and the sidebar started speaking English
    next to a Polish menu. The fix: a literal `"Pages"` in every call. The safeguard:
    `tests/test_i18n.py`.

- **S4** — the scope was completed, with one significant caveat about verification (at the end).

  The biggest departure from the plan: **there are two privileged programs, not one.** The plan
  assumed `pkexec emerge …`, but that does not work the way it needs to, for two reasons:

  1. **A named polkit action refers to a specific program path.**
     `org.gentoo.gentstore.run-emerge` has to point at something we installed; `pkexec emerge`
     would use the generic `org.freedesktop.policykit.exec` action, and the authentication dialog
     would say “an application is trying to run a program as another user” instead of “installing
     and updating packages”.
  2. **Root cannot be interrupted from an unprivileged process.** The kernel will not let the GUI
     send `SIGINT` to an `emerge` running as root — so the “Interrupt” button from the plan could
     not have worked at all. The solution: the launcher reads its own `stdin` and the signal
     leaves from inside the root process. End of stream counts as `abort`, so a build does not
     outlive the interface.

  The rest of the decisions worth remembering:

  3. **The backup travels in the same call as the change** (`ensure_backup` in the request),
     not a separate one. One password prompt instead of two and — more importantly — no “the
     change went in, the copy did not” state.
  4. **`write_file`/`delete_file` require an `expect` field** with the file's exact current
     content. Without it, “write the whole file” would silently overwrite somebody else's
     changes.
  5. **The permitted directory in the helper is a constant in the code**, not an argument and not
     an environment variable — either would be a way to redirect a write elsewhere. Tests replace
     it after importing, which the installed program cannot do.
  6. **`Escalation("direct")`** — when the application is running as root after all, privileged
     operations simply work instead of asking for a password that would change nothing. The
     startup warning still appears.

  Three bugs caught only on the running application:

  - **`QProcess.processEnvironment()` returns an empty environment on a fresh process.** Setting
    it back took `PATH` away from the child — Portage immediately started complaining about
    missing `bzip2` and `zstd`, though both are installed. You have to start from
    `QProcessEnvironment.systemEnvironment()`.
  - **Changing the translation extractor halfway through the project.** `tools/i18n.py` picked
    “the first one available”, and on the same day `dev-python/pyqt6` appeared on the system it
    jumped from `lupdate` to `pylupdate6`. The catalogue got every message twice (an old
    `vanished` one and a new `unfinished` one). The fix: the extractor pinned hard, with no
    fallback, plus a test for duplicates.
  - **`window.tr("…")` is invisible to the extractor.** I wrote the “running as root” warning in
    `app.py`; it compiled, it worked, and it would have stayed English for ever. Moved into
    `MainWindow`, where `self.tr()` makes sense. A test walking the AST now catches every
    `anything.tr("…")`.

  Added beyond the plan: the `Makefile` (`make install-system`), the startup warning when running
  as root, and the `Ctrl+L` shortcut for the log.

  **What could NOT be verified.** The privileged path — `pkexec` → launcher/helper — **was not
  run live**, because it requires both programs to be installed in `/usr/libexec/gentstore` and
  an administrator password, and this session has no root. Everything around it was verified: the
  command-line assembly (test), the allow-list of programs (test), the helper's JSON protocol
  against a real subprocess (test), interruption on a real process (test), and the entire
  unprivileged `emerge -pv` path from click to log. To close out the S4 criterion, this is
  needed:

  ```bash
  sudo make install-system
  python -m gentstore          # Search → app-misc/hello → Install → Uninstall
  ```

- **S5** — the scope was completed in full. Things worth remembering:

  1. **A USE layer can mention a flag twice, with opposite signs.** Portage flattens the profile
     stack by concatenation, so `configdict["defaults"]["USE"]` for mpv contains both `sdl` and
     `-sdl`. **The last one wins.** Keeping the layer in a set gave “sdl is enabled” for the whole
     system — a bug that only surfaced with the first real write plan (`-sdl` in a line nobody
     wanted).
  2. **`configdict["env"]["USE"]` is not the environment**, it is a computed value. Used as the
     highest-priority layer it would attribute every flag to “the environment”. We read
     `os.environ["USE"]`.
  3. **Every flag carries a `baseline`** — its value without `package.use`. Only the difference
     goes into the file, so we never write out flags the profile sets anyway.
  4. **We look for an existing entry across the whole `package.use` directory**, not just in the
     file named after the package — otherwise the same package would get a second entry in a
     second file.
  5. **Entries with a version restriction (`>=media-video/mpv-0.40 X`) are left alone.** Somebody
     wrote them deliberately; quietly rewriting them would be exactly the kind of surprise this
     project exists to prevent.
  6. **Our own `REQUIRED_USE` parser rather than `portage.dep.check_required_use`.** Portage
     answers with a single boolean, and the interface needs the answer “which condition did you
     break, and what would satisfy it”. The parser reproduces mpv's expression byte for byte.
  7. **Locked flags (`use.force` / `use.mask`) never go into the file** and are never described as
     “changed by you” — they beat `package.use`, so such a line would do nothing while looking as
     though it did.
  8. **`use.local.desc` is 770 KB**, so we scan it by the `cat/pkg:` prefix (about 10 ms) and
     remember the result, rather than parsing the whole thing.

  **What could NOT be verified:** `pkexec` itself — the authentication dialog needs the user's
  graphical session and cannot be answered from here. Everything short of it is verified: the
  write plan, turning the plan into a JSON request, crossing the process boundary and the
  helper's decision — against a temporary directory, with a real subprocess
  (`test_a_plan_becomes_exactly_one_line_in_package_use` and its neighbours).

- **S6** — the scope was completed in full. Things worth remembering:

  1. **Portage gives the licence reason as a sentence**, not as a list: `'BUSL-1.1 license(s)'`.
     We extract the names from there, with `getMissingLicenses()` as the fallback — and there is a
     test checking that both ways into Portage say the same thing.
  2. **`getmaskingreason(..., return_location=True)`** gives the maintainer's note and the file it
     came from. It is the most useful thing on the whole screen, so it is shown verbatim, only
     without the leading `#`.
  3. **Every fix is pinned to a version** (`=cat/pkg-version`). `cat/pkg` would accept every
     future version too — which is exactly how `/etc/portage` turns into a file nobody looks at.
  4. **Two fixes are marked as not recommended** and get a red button: `-arch` (the ebuild says
     outright that it does not work) and lifting a mask. For `-arch` we say plainly that the line
     will silence Portage but will not make the package build.
  5. **`locate()` gained an `entry` parameter.** The file name in a directory comes from
     `cat/pkg`, but the search for an existing entry comes from the atom: in
     `package.accept_keywords` the entries are versioned, so one cannot stand in for the other.
  6. **Licence groups nest** (`@FREE` is made of other groups), so membership is resolved through
     `expandLicenseTokens` rather than by reading `license_groups` literally.
  7. **The action button never writes.** It shows the line in the same `write_preview` as the USE
     flags — there is one three-beat pattern for the whole application.

  The “Masks and licences” screen came out differently from what the plan assumed (“unfoldable
  entries”): instead of a list of blocked packages it shows **what the user has already
  accepted** — the contents of `package.accept_keywords`, `package.unmask`, `package.license` and
  `package.mask`, with the file each entry lives in and the option to remove it. The list of
  blocked packages is already in the search screen (a “blocked” marker next to the version), while
  the other list — what has accreted in `/etc/portage` over the years — was nowhere to be seen.

  **What could NOT be verified:** as in S4 and S5, `pkexec` itself. The write and removal plans
  are tested, and so is the passage through the helper (`tests/test_useflags.py`), but the
  authentication dialog needs the user's graphical session.

- **S7** — the scope was completed in full. Things worth remembering:

  1. **`repositories.xml` is fetched by `eselect`, not by us.** The plan said “fetch and cache in
     `~/.cache/gentstore/`”, but `app-eselect/eselect-repository` already does that and keeps it
     in `~/.cache/eselect-repo/`. Fetching it ourselves would break the rule from
     [04-privileges.md §8](04-privileges.md) — the only network traffic the application produces
     comes from programs run on the user's instruction. “Refresh” is a visible command in the log.
  2. **`eselect repository enable` writes to a single `eselect-repo.conf`**, not to a file per
     repository as the plan assumed. We show the real file and the real section — that is what
     the user will see if they go looking.
  3. **Mode (b) of “::gentoo only” is per overlay** and lives on the Repositories screen. Masking
     a whole repository is `*/*::<name>` in `package.mask/<name>`; the toolbar switch now says
     where that is done, instead of only showing the shape of the entry.
  4. **`confedit.locate()` gained a `file_name` parameter.** `*/*::guru` concerns no package, so
     the file name cannot come from `cat/pkg`.
  5. **The catalogue ranking favours repositories Gentoo vouches for** — on an equal match, `core`
     comes before `experimental`. Somebody typing “kde” is almost certainly looking for `::kde`,
     not for an overlay with a Plasma theme.

  One bug caught on the screen:

  - **`write_preview` had `package.use` hard-coded.** When masking a repository the panel claimed
    that “package.use is a directory, so the entry will go into a separate file”, while it was
    writing to `package.mask`. The file name now comes from the plan.

  **What could NOT be verified:** enabling and removing a repository live — both go through
  `pkexec`. Everything else is verified: building the command lines (tests), the confirmation
  dialogs with real numbers (`::guru` → 3 installed packages, `::steam-overlay` → 1), the mask
  plan, and the full command → log → reload chain on `eselect repository list`.

- **S8** — the scope was completed in full. Things worth remembering:

  1. **`emerge` formats sizes with the thousands separator of the current locale.** On this system
     that is U+202F — a narrow no-break space, indistinguishable from an ordinary one in a
     terminal, and `split()` falls over on it. Commands whose output we parse are given
     `LC_ALL=C.UTF-8`; the parser tolerates every separator anyway, because the user's
     `EMERGE_DEFAULT_OPTS` can change it again.
  2. **`emerge` marks a downgrade with two letters: `UD`.** Checking `U` before `D` reported every
     downgrade as an update — which is precisely the direction nobody wants to miss. There is a
     test for it.
  3. **`%n` in the text does not make a plural.** The extractor decides from the shape of the
     call: `self.tr("%n new", "", count)` inside a dict literal came out as an ordinary string
     with one form. In Polish that is the correct ending for one third of the values. Worse,
     reworking the call is not enough, because `pylupdate6` merges and keeps the old entry; it has
     to be deleted from the `.ts` first. A new test makes sure every message with `%n` has plural
     forms.
  4. **Our own GLEP 42 reader rather than `portage.news.NewsManager`.** The manager answers with a
     count and keeps the items to itself, whereas the most important piece of information is
     **why** a given item concerns this machine: `Display-If-Installed`, `Display-If-Profile`,
     `Display-If-Keyword`. Every row shows it.
  5. **Marking news as read is sometimes privileged and sometimes not.** `/var/lib/gentoo/news` is
     writable by the `portage` group; anyone in it does this without a password. We check access
     and pick the mode accordingly, rather than asking for a password that would change nothing.
  6. **`--depclean` never moves without showing the list.** The remove button appears only after
     `--depclean -p`, and the confirmation lists the atoms.
  7. **Failure has a place of its own.** Out of several hundred lines of a failed `emerge` we
     extract the package, the `build.log` path and the last lines before the error, plus a
     sentence of advice for nine typical situations (a block, a slot conflict, a missing USE flag,
     a keyword, a mask, a licence, `REQUIRED_USE`, a missing dependency, no disk space).

  A departure from the plan: **there are seven entries in the step list, not six.** The GLSA panel
  got its own entry, without a number and visually separated — the plan called it a “panel”, and
  it had nowhere to live in a wizard made of six steps.

  **What could NOT be verified:** steps 1, 4 and 5 in their executing form — `emaint sync -a`,
  `emerge -vuDN @world` and `--depclean` all go through `pkexec`. This system is fully up to date
  (`@world` gives 0 packages), so the preview table was verified with a real `emerge -pv` for
  `media-video/mpv` — the same command through the same runner and parser, only with a different
  argument.

- **S9** — the scope was completed in full. Things worth remembering:

  1. **`cfg_apply` had to reach outside `/etc/portage`** — `._cfg` files land all over `/etc`. It
     is the only helper operation that leaves the configuration directory, and the list of
     permitted directories is read by the helper **on its own** from `make.globals`, `make.conf`
     and `/etc/env.d/` (files owned by root), not from the request. The parser recognises only
     `CONFIG_PROTECT=` as a standalone assignment.
  2. **The third decision: `merge`.** The plan spoke of “a simple three-way editor in the window”;
     what came out is simpler and more honest — an editable panel filled with the new version,
     and on save the helper is given `decision: "merge"` and the content. The result has the same
     shape as “take the new one”, archiving of the previous version included.
  3. **Qt does not understand `#RRGGBBAA`.** Neither in style sheets nor in rich text — and rather
     than reject it, it reads it as something else. A red removal and a green addition were coming
     out as two identical olive stripes. The transparency tokens are now written as `rgba(...)`.

  Two real bugs only surfaced in a full test run — both about cleanup, and both had existed since
  earlier sessions:

  - **A `Command` destroyed with a running process brought the process down.** The object
    disappeared (the window closed, the GC collected it) and the `finished` signal arrived at
    something that was no longer there. `Command.close()` was added — interrupt, wait up to 3 s,
    disconnect — called from the window's `closeEvent`. Incidentally: closing the window also
    stops a privileged build, because the launcher treats a closed stdin as `abort`.
  - **The result of a background task could arrive at a destroyed widget.** `run_async` now wraps
    both callbacks so that a result for a recipient that no longer exists is simply dropped. An
    unhandled exception in a slot is not an error in PyQt, it is a process `abort`.

  **A stale copy of the helper — added after the session.** Changing `gentstore_helper.py` in this
  session invalidated the copy in `/usr/libexec/gentstore/`, and that is not cosmetic: **the old
  helper refuses operations the new one allows.** Verified: for `cfg_apply` on a `._cfg` file in
  `/etc`, the installed copy refuses with `outside_root`, because it does not yet know about
  protected directories. The message is true and completely incomprehensible.

  The fix is on the user's side (`sudo make install-system`), but **the application has to notice
  and say so**, hence:

  - `runner/privilege.installed_status()` compares the installed copy against the source;
  - the window says in the status bar at startup that the installed program is older, and what to
    do about it;
  - every helper refusal then gets a note with the real reason.

  The S7 test was badly framed while we were at it: it checked a property of the **machine**
  (whether somebody had reinstalled after the last change) rather than of the code. It was
  replaced by tests that the code **can recognise** the mismatch and that it explains it.

- **S10** — the scope was completed in full. Things worth remembering:

  1. **“What Portage uses” and “what this file says” are two different answers.** `FEATURES` and
     `USE` are composed of the profile, `/etc/env.d` and `make.conf` at once. Every row shows both
     values, because confusing them ends with the profile's entire `USE` list pasted into one's
     own file — and a system that stops keeping up with profile updates.
  2. **Multi-line assignments are refused, not guessed at.** Somebody's carefully wrapped
     `USE="… \` is not something we rewrite on their behalf; the row says outright that it will
     not touch it.
  3. **The replacement pattern is anchored** (`^\s*NAME=`), so that a mention of the variable in a
     comment or in another variable's value cannot be the line that gets replaced.
  4. **Quoting style and indentation are left as they were.** `MAKEOPTS='-j4'` stays in single
     quotes.
  5. **The `MAKEOPTS` suggestion is bounded by memory, not just by the core count.** One job per
     core is the usual advice, and it is exactly how a 28-core machine with 32 GB ends a chromium
     build out of memory. We suggest `min(cores, RAM/2 GiB)` and say why that number.
  6. **`cpuid2cpuflags` is not installed** on this machine, so the `CPU_FLAGS_X86` suggestion names
     the package and leaves the field alone — exactly as the plan required for optional
     dependencies.

  Two things caught by the tests rather than by eye:

  - **The AST-based i18n test paid off again.** A variable row was calling `self._page.tr(…)` —
    four strings would have landed in the wrong context or fallen out of the catalogue. The third
    time that test has earned its keep.
  - **The diff legend had been written for one screen** (“the version the package brought”). With
    `make.conf` we compare a file against itself, so `DiffView` now takes captions for both sides.

- **S11** — the scope was completed in full. Things worth remembering:

  1. **Portage has two elog storage layouts**, depending on `PORTAGE_ELOG_SYSTEM`: one growing
     `summary.log` (`save_summary`, which is what this machine uses) or a file per package
     (`save`). We read both at once, because the setting can be changed at any moment and a system
     that has used both has messages in both places.
  2. **From a long `summary.log` we read only the tail.** Above 4 MB we seek to the end and
     discard the first, half-cut entry — rather than showing a fragment.
  3. **An entry's severity is the worst of its blocks.** One entry can carry a note, a warning and
     a quality notice at once; the left edge of the row carries the worst one, so that the message
     page can be scanned without reading any of them.
  4. **Removing from `@world` is `emerge --deselect`, not editing the file.** And the dialog says
     plainly that this uninstalls nothing — “remove” reads as “delete”, and that difference is
     what the whole of `--depclean` rests on.

  A departure from the plan: **messages do not switch the screen by themselves.** The plan said
  “automatically show new messages after a finished installation”; the elog screen reloads after
  every command and updates the sidebar badge, but it does not tear the user away from what they
  are doing. Interrupting somebody's work with a window they did not ask for is worse than a
  number on a bar that cannot be missed.

- **S12** — the scope was completed in full. Things worth remembering:

  1. **A constant used as a default argument freezes at import time.**
     `make_backup(keep=BACKUP_KEEP)` stopped reacting to changes in `BACKUP_KEEP` — caught by the
     S4 test that replaced that constant. The default is now `None`, with the value read inside
     the function.
  2. **`untranslated()` instead of exceptions in the test.** The “every user-visible string goes
     through `tr()`” test correctly pointed at eleven places — and all eleven were deliberate
     (language names, commands, program names, a literal `package.mask` entry). Instead of a list
     of exceptions in the test, a marker function was created: the code itself says that this is
     intended, and a reviewer sees it too, not just the test.
  3. **An archive as the second form of backup** (`tar.gz`) — unpacked with `filter="data"`,
     because an archive is the only form of backup that somebody other than this program could
     have written.
  4. **Restoring got its own dialog with a difference.** “Restore the newest” is not a decision
     that can be made sensibly: the copies are named after dates, and the only way to tell them
     apart is to see what going back to each would undo.
  5. **`--getbinpkg` reaches the preview too**, not only the installation — otherwise the table
     would promise something other than what step four does.

  **What could NOT be verified** (beyond what is listed under S4–S11): a clean installation on a
  second Gentoo system. There is one machine, and testing an installation by overwriting a working
  system would be exactly what this application exists to prevent.

  **The environment:** through S1–S3 `dev-python/pyqt6` was not installed and the application ran
  from a PyQt6 wheel in a temporary venv. During S4 the repository owner installed
  `dev-python/pyqt6` (6.11.1), and from that point the tests and the screenshots go through the
  **system** Qt. Tests and linting still need `dev-python/pytest` and `dev-python/ruff` — for now
  a venv in a temporary directory stands in for them.
