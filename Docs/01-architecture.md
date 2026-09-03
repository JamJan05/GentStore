# 01 — Architecture

## 1. Governing assumptions

1. **The GUI process never runs as root.** Everything that needs privileges goes through a
   separate, short-lived process started by `pkexec`. Details: [04-privileges.md](04-privileges.md).
2. **Package data comes from the Python `portage` API,** not from parsing command output or
   reading ebuilds by hand. We parse `emerge` output only where the API has no equivalent (the
   update preview, build progress).
3. **Nothing happens quietly.** Every modification of `/etc/portage` has three stages the user
   can see: *preview before writing* → *write* → *report: “line X was appended to file Y”*.
4. **We never overwrite the user's files.** Operations on configuration files are always
   “append a line” or “change one specific line”; comments and the formatting of the rest of the
   file stay as they were.
5. **The GUI does not freeze.** No `portage` call and no subprocess blocks the Qt thread.

## 2. Layers

```
┌─────────────────────────────────────────────────────────────┐
│  ui/            widgets, pages, theme, translations         │  Qt Widgets
├─────────────────────────────────────────────────────────────┤
│  models/        Qt models (QAbstractItemModel) + dataclasses│  adapting core → view
├─────────────────────────────────────────────────────────────┤
│  core/          domain logic: portage API, config files     │  plain Python, no Qt import*
├─────────────────────────────────────────────────────────────┤
│  runner/        running commands, privileges, logging       │  QProcess + pkexec
└─────────────────────────────────────────────────────────────┘
```

The dependency rule: `ui → models → core`, `ui → runner`. **`core/` imports nothing from Qt** —
which is what lets the whole domain layer be tested and driven from a command line with no
graphical environment (`python -m gentstore.core.cli`, the diagnostic tool built in S2).

`runner/` is the exception: it rests on `QProcess`, because we need to stream output into the
GUI in real time. Its interface is narrow enough, though, that tests replace it with a stub.

## 3. Directory structure

```
Gentstore/
├── Docs/                      # project documentation (this directory)
├── gentstore/
│   ├── __init__.py
│   ├── __main__.py            # entry point: python -m gentstore
│   ├── app.py                 # QApplication, loading the theme and translations, CLI arguments
│   ├── settings.py            # QSettings: language, "::gentoo only" mode, last tab…
│   ├── logging_setup.py       # logging to ~/.local/state/gentstore/
│   ├── sysinfo.py             # Portage version, ARCH, profile, MAKEOPTS — for the window bars
│   │
│   ├── core/
│   │   ├── cli.py             # the diagnostic tool: python -m gentstore.core.cli
│   │   ├── portage_env.py     # one shared portage.config + dbapi (porttree, vartree, bintree)
│   │   ├── packages.py        # searching, atoms, versions, package metadata
│   │   ├── index_cache.py    # the search index kept between runs, and what invalidates it
│   │   ├── useflags.py        # IUSE, use.desc/use.local.desc, metadata.xml, force/mask, flag origin
│   │   ├── required_use.py    # the REQUIRED_USE parser and validator (^^, ??, ||, conditions)
│   │   ├── depgraph_hints.py  # pulling conditional "flag? ( ... )" dependencies out of DEPEND/RDEPEND
│   │   ├── masking.py         # reasons for a block: package.mask, keywords, licence, profile
│   │   ├── licenses.py        # ACCEPT_LICENSE, groups (@FREE…), full licence texts
│   │   ├── repos.py           # repos.conf, sections, "hide a repo from Portage"
│   │   ├── overlays.py        # the repositories.xml catalogue — search, quality, sources
│   │   ├── worldset.py        # /var/lib/portage/world, the installed list
│   │   ├── elog.py            # /var/log/portage/elog — both storage layouts, message classes
│   │   ├── news.py            # GLEP 42: repository news and its relevance here
│   │   ├── glsa.py            # parsing glsa-check -l affected
│   │   ├── cfgfiles.py        # ._cfg0000_* files, CONFIG_PROTECT, diff
│   │   ├── backup.py          # /etc/portage backups: listing, naming, "once per run"
│   │   ├── binrepos.py        # binrepos.conf, PKGDIR — where binary packages come from
│   │   ├── makeconf.py        # reading/editing individual make.conf variables + suggestions
│   │   ├── profiles.py        # the profile list from eselect, the current one, filtering
│   │   ├── confedit.py        # safe writing to /etc/portage (file vs directory, appending lines)
│   │   └── emerge_parse.py    # parsing `emerge -pv`, `--depclean` and a failed build
│   │
│   ├── models/                # QAbstractTableModel / QAbstractListModel + filtering proxies
│   │   ├── packages.py        # the search-result list model
│   │   └── update.py          # the update preview table
│   ├── runner/
│   │   ├── command.py         # QProcess: output stream, exit code, interruption
│   │   ├── privilege.py       # detecting pkexec/sudo/root, paths to the privileged programs
│   │   ├── emerge.py          # building command lines: pretend, install, unmerge, world…
│   │   ├── eselect.py         # eselect repository … and emaint sync -r
│   │   └── helper_client.py   # the root helper client (JSON over stdin)
│   │
│   ├── helper/                   # two privileged programs, stdlib only, no imports from the rest
│   │   ├── gentstore_helper.py   # the only place that writes to /etc/portage
│   │   └── gentstore_launcher.py # runs emerge/eselect/… and can interrupt them
│   │
│   ├── ui/
│   │   ├── main_window.py     # menu, toolbar, sidebar, page stack, status bar
│   │   ├── context.py         # resources shared by the screens: package index, "::gentoo only"
│   │   ├── settings_dialog.py # the Settings dialog
│   │   ├── i18n.py            # untranslated() — a marker for deliberately untranslated text
│   │   ├── tasks.py           # the only seam between synchronous core/ and Qt threads
│   │   ├── pages/             # search, update, repos, masks, cfgfiles, makeconf, elog, world, profile
│   │   │   ├── split_page.py  # the "352 px list + details" base
│   │   │   ├── masks.py       # the "Masks and licences" screen
│   │   │   ├── repos.py       # the "Repositories" screen + the overlay browser
│   │   │   ├── update.py      # the update wizard: six steps + the GLSA panel
│   │   │   ├── cfgfiles.py    # the ._cfg screen: the difference and three decisions
│   │   │   ├── makeconf.py    # the "Portage settings" screen
│   │   │   ├── profile.py     # the "Profile" screen
│   │   │   ├── elog.py        # the "elog messages" screen
│   │   │   ├── world.py       # the "@world set" screen + installed packages
│   │   │   └── search.py      # the "Search and install" screen (USE flags + the block notice)
│   │   ├── widgets/           # log_view, package_list, use_flag_row, block_notice…
│   │   └── theme/
│   │       ├── tokens.py      # colours/spacings/radii from the mock-up
│   │       ├── qss.py         # the style sheet built from the tokens
│   │       ├── palette.py     # QPalette for what QSS does not cover
│   │       └── icons/         # an own set of SVGs, coloured on the fly
│   │
│   └── i18n/
│       ├── gentstore_pl.ts    # the Polish translation (the sources are in English)
│       └── gentstore_en.ts    # an empty pass-through, kept for completeness
│
├── data/
│   ├── org.gentoo.gentstore.policy   # polkit rules
│   ├── gentstore.desktop             # the menu entry
│   └── icons/gentstore.svg           # the application icon
├── packaging/                        # a draft ebuild for a private overlay
├── Makefile                          # make install — the parts that belong to root
├── tools/
│   ├── i18n.py                # refreshing and compiling the translations
│   └── screenshot.py          # rendering the window to PNG via the `offscreen` platform
├── tests/
├── pyproject.toml
└── README.md
```

## 4. Threading model

| Kind of work | Mechanism | Notes |
|---|---|---|
| Reading from `portage` (search, metadata, IUSE) | `QThreadPool` + `QRunnable` | The result comes back to the GUI as a signal. Building the package index the first time can take a few seconds. |
| Running commands (`emerge`, `eselect`, `emaint`) | `QProcess`, asynchronously | Output line by line → the log widget. |
| Writing to `/etc/portage` | `QProcess` → `pkexec` → the helper | Short, but asynchronous too — polkit asks for a password. |
| Heavy parsing (repositories.xml, elog) | `QThreadPool` | Results cached in memory. |

The rule: **classes in `core/` are synchronous and know nothing about threads.** Wrapping them
in a `QRunnable` happens one layer up (`models/`, or the thin `ui/tasks.py` adapter). That is
what lets the same function serve both the GUI and the diagnostic CLI.

## 5. Cache and performance

- `portage.config` + `dbapi` are created **once** (`core/portage_env.py`) and shared; they are
  reloaded explicitly after a `sync`, after a `make.conf` change, and after an overlay is
  enabled or disabled.
- The search index (`core/packages.py`, the `SearchIndex` class): a list of `cat/pkg` plus a
  short description plus the repository, built in the background at startup and held in memory;
  searching runs over it, and full metadata is only read once a package is selected. Measured on
  the development machine (21,711 packages, three repositories): **2.4 s** with a cold page
  cache, about 5 ms per query. The index is a **snapshot** — after a `sync` or after enabling an
  overlay it has to be rebuilt. The one exception is the “installed” bit itself:
  `SearchIndex.refresh_installed()` refreshes it separately and cheaply, because it changes
  after every installation.
- That index is also written to disk (`core/index_cache.py`) and read back on the next start:
  **3.1 s to build, 0.07 s to read** on the same machine, so the second run of the day has its
  package list before the window is on screen. The file lives in `$XDG_RUNTIME_DIR/gentstore/`,
  a tmpfs the system clears when the session ends, and it is only used if
  `index_cache.fingerprint()` still matches — the set of repositories, where each one is, and the
  modification time of every directory directly inside it, which is about a millisecond to
  compute. `GENTSTORE_INDEX_CACHE=0` turns the whole thing off; see
  [06-decisions.md D-13](06-decisions.md).
- `repositories.xml` (459 entries) is **not downloaded by us**. `eselect repository` already
  fetches it and keeps it in `~/.cache/eselect-repo/`; we read that copy, and “Refresh” runs
  `eselect repository list` through the runner. The reason is in
  [04-privileges.md §8](04-privileges.md): the only network traffic the application produces
  comes from programs it runs on the user's instruction — visible in the log, rather than a
  quiet background download.
- The installed list: `vartree.dbapi.cpv_all()` — fast, without shelling out to `qlist`.

### Who owns the index

`ui/context.py` (`AppContext`) — one object created by `MainWindow` and handed to every screen
as it is built. It holds the search index and the state of the “::gentoo only” switch. The
reason is the same in both cases: this is data **one place sets and many read**, and pushing it
through the window would tie every screen to the window's internals.

A screen reads nothing from Portage in its constructor. `MainWindow.load_system_info()` — called
after `show()` — sets the `_started` flag and calls `Page.activated()` on the visible screen;
the other screens get the same signal when the user opens them. That keeps the window
constructor cheap and testable, and screens nobody opened cost nothing.

### Reading `emerge` output

Everything Portage knows about a pending update is in the text `emerge -pv` prints; there is no
API for it. `core/emerge_parse.py` reads that text — the same text the user would see in a
terminal — and turns it into table rows. The original stays visible in the log panel, because
whatever the parser misses has to remain readable.

Two things had to be set rather than parsed:

- **The locale.** `emerge` formats sizes with the thousands separator of the current
  `LC_NUMERIC`. On a Polish system that is U+202F — a narrow no-break space, invisible in a
  terminal and fatal to a naïve `split()`. Commands whose output we parse are given
  `LC_ALL=C.UTF-8`; the parser tolerates every separator anyway.
- **The order of the status letters.** `emerge` marks a downgrade with **two** letters (`UD`),
  so checking for `U` before `D` would report every downgrade as an update.

## 6. The flow of a typical operation (example: changing USE flags)

```
UI: the user toggles the "vulkan" checkbox
      ↓
core/required_use.py  →  live validation, a message if a condition is broken
      ↓
core/confedit.py      →  building the change plan:
                          {op: "append_line",
                           file: "/etc/portage/package.use/mpv",
                           line: "media-video/mpv vulkan -jack"}
      ↓
UI: the "Will be written" panel shows the file + the exact line   ← PREVIEW
      ↓  [the user clicks Save]
core/backup.py        →  a request for an /etc/portage backup
runner/helper_client  →  pkexec gentstore-helper  (JSON on stdin)
      ↓
helper: path validation → backup → atomic write → JSON report
      ↓
UI: "Appended the line `media-video/mpv vulkan -jack`
     to the file `/etc/portage/package.use/mpv`"                  ← REPORT
      ↓
core/portage_env.py   →  invalidate() and recompute the package's state
```

The same three-beat pattern (preview → write → report) applies to `package.accept_keywords`,
`package.unmask`, `package.license`, `package.mask`, `repos.conf` and `make.conf`. It is
implemented by one shared widget, `ui/widgets/write_preview.py`, so that it looks identical
everywhere.

### Where a USE flag's value comes from

Five layers, weakest first: the ebuild default (`+flag` in `IUSE`) → the profile → `USE` in
`make.conf` → `/etc/portage/package.use` → `USE` in the environment. Above all of them,
`use.force` and `use.mask` (and their per-package variants) take the flag away from the user
entirely — we show those as **locked** rather than hiding them.

Two traps in Portage's data, both caught only on a real tree:

- **A single layer can mention a flag twice, with opposite signs.** Portage flattens the profile
  stack by concatenation, so `configdict["defaults"]["USE"]` for `media-video/mpv` contains both
  `sdl` and `-sdl` — one profile enables it, a later one disables it. **The last one wins**, so
  we keep the layers as lists and scan them from the end. A set gave the answer “sdl is enabled”
  for the whole system.
- **`configdict["env"]["USE"]` is not the environment.** It is a computed value; used as the
  highest-priority layer it would attribute everything to “the environment”. We read
  `os.environ["USE"]`.

Every flag also carries a `baseline` — the value it would have **without** `package.use`. The
difference between that and the current state is exactly what has any business going into the
file; writing out a flag the profile sets anyway looks innocent and is not — profiles change,
and a year later such a line quietly pins a value nobody chose.

## 7. Handling “file or directory”

`/etc/portage/package.use` (and its siblings) can be a **file** or a **directory**.
`core/confedit.py` settles that once and offers a uniform API:

- a directory → write to `<directory>/<package-name>` (the package name without the category,
  e.g. `mpv`);
- a file → append the line to the end of the existing file;
- neither exists → we create a **directory** (Gentoo's recommendation) and a file inside it.

In every case the user sees the destination path *before* the write, so there are no surprises.

## 8. Dependencies

Required at runtime:

- `dev-lang/python` ≥ 3.12 (the target environment: 3.14)
- `sys-apps/portage` (the `portage` module — shipped with Portage)
- `dev-python/pyqt6` (Qt Widgets; `PYTHON_COMPAT` covers `python3_14`)
- `app-admin/eselect` with the `repository` module (`app-eselect/eselect-repository`)
- `sys-auth/polkit` (for `pkexec`); the fallback is `sudo`

Optional, detected at runtime and disabling a feature when absent:

- `app-portage/gentoolkit` (`glsa-check`, `equery`)
- `app-portage/cpuid2cpuflags` (the `CPU_FLAGS_X86` suggestion)
- `dispatch-conf` / `etc-update` (shipped with Portage)

A missing optional dependency has to produce a readable message in the GUI (“install
`app-portage/gentoolkit` to enable GLSA scanning”), not an exception.
