# 02 — Interface and theme

The source of truth for the look: the mock-up `../Gentoo portage UI prototype.zip` (a Claude
Design canvas, the **“nocturne”** theme). This document carries over everything from it that the
Qt implementation needs, so that writing code never means going back to the archive — which is
just as well, since the archive is not kept in the repository.

## 1. The character of the interface

A dense, tool-like window in the style of an IDE, not an app store: a dark background, plenty of
fixed-width text, tight spacing, a minimum of decoration. The base font is **12.5 px** —
deliberately small, because the screens show a lot of data at once. Package names, paths,
commands, versions and anything the user might retype into a terminal are set in a
**monospaced** font.

The reference window: **1520 × 960 px**. The minimum size to enforce in code: **1100 × 700**.

## 2. Theme tokens

To be transcribed into `gentstore/ui/theme/tokens.py` as constants, from which the QSS is
generated.

### Base colours

| Token | Value | Used for |
|---|---|---|
| `bg` | `#161826` | the window background, nested panels, code fields |
| `surface` | `#232532` | bars, the sidebar, cards, table headers |
| `text` | `#e9e9ed` | primary text |
| `accent` | `#9184d9` | selection, primary actions, the progress bar |
| `divider` | `#e9e9ed` @ 16 % | separator lines (in Qt: `#3f424d`) |

### The neutral scale

| Token | Value | Typical use |
|---|---|---|
| `neutral-300` | `#cfd3e5` | secondary text in code blocks |
| `neutral-400` | `#b2b6ca` | descriptions, inactive navigation entries |
| `neutral-500` | `#9397ab` | package descriptions in the result list |
| `neutral-600` | `#75798c` | captions, metadata, column headers |
| `neutral-700` | `#595d6c` | dimmed text (masked flags) |
| `neutral-800` | `#3f424d` | borders |
| `neutral-900` | `#292b31` | faint lines inside cards, badge backgrounds |

### The accent scale

| Token | Value | Use |
|---|---|---|
| `accent-200` | `#e7e5fe` | text on an accent background |
| `accent-300` | `#d2cefd` | links, the names of “pulls in” dependencies |
| `accent-700` | `#5d5294` | the border of informational notices |
| `accent-800` | `#423a6a` | the background of badges for repos outside `::gentoo` |
| `accent-900` | `#2b2741` | the background of the active navigation entry |

### Semantic colours

| Meaning | Value | Where |
|---|---|---|
| success / “Saved” | `#74b58c` | the left edge of the confirmation notice, `+` lines in a diff |
| warning | `#d9b072` | unofficial sources, annotations next to repositories |
| error / block | `#d98a72` | masks, GLSAs, `−` lines in a diff |

### Spacing and radii

`space-1 = 3 px`, `space-2 = 6 px`, `space-3 = 8 px`, `space-4 = 11 px`, `space-6 = 17 px`,
`space-8 = 22 px` (the mock-up's values rounded to whole pixels — Qt counts in integers anyway).

`radius-sm = 4 px`, `radius-md = 8 px`, `radius-lg = 14 px`.

### Typefaces

- The interface: **Inter**, falling back to `system-ui` / the system's default sans.
- Fixed width: the system's default monospace (Qt: `QFontDatabase.systemFont(FixedFont)`).
  The mock-up says `ui-monospace`; on Gentoo that will practically always land on something
  sensible.

## 3. The window skeleton

```
┌──────────────────────────────────────────────────────────────── 29 px ─┐
│ File  Repositories  Package  System  View  Help     portage 3.0.81 · … │  QMenuBar
├──────────────────────────────────────────────────────────────── 38 px ─┤
│ ⟳ Sync │ ↑ Update @world │ ⑂ Overlays │ ▤ Log ║ ☐ ::gentoo only        │  QToolBar
│                                            [a) hide │ b) mask]         │
├────────── 206 px ──────────┬────────────────────────────────────────────┤
│ MANAGEMENT                 │                                            │
│  🔍 Search and install     │                                            │
│  ↑  System update       37 │              QStackedWidget                │
│  ⑂  Repositories           │              (9 pages)                     │
│  🛡  Masks and licences  2 │                                            │
│  ▤  Configuration files  4 │                                            │
│  ⚙  make.conf              │                                            │
│  ✉  elog messages       12 │                                            │
│  ▣  @world set             │                                            │
│  👤 Profile                │                                            │
│  ───────────────────────   │                                            │
│  Backup                    │                                            │
│  /etc/portage.bak-…        │                                            │
│  Restore…                  │                                            │
├────────────────────────────┴──────────────────────────────────── 26 px ─┤
│ status left                                            status right     │  QStatusBar
└────────────────────────────────────────────────────────────────────────┘
```

The active navigation entry: an `accent-900` background, a 2 px `accent` left edge, `text`
coloured text. An inactive one: a transparent background, `neutral-400` text, `neutral-900` on
hover. The count badge: an `accent-800` background, `accent-200` text, an 8 px radius.

Icons: Phosphor Icons in the mock-up. In the application — icons from the system theme via
`QIcon.fromTheme()`, with a fallback SVG set in `data/icons/` (so that the look does not depend
on which icon theme the user has).

## 4. Screen inventory

| id | Name | Layout | Session |
|---|---|---|---|
| `search` | Search and install | a 352 px result list + a detail panel | S3, S5 ☑ |
| `update` | System update | a 352 px list of 6 steps + a step panel | S8 |
| `repos` | Repositories | a 512 px repo list + details and the overlay browser | S7 ☑ |
| `mask` | Masks and licences | one column, a list of entries from /etc/portage | S6 ☑ |
| `cfg` | Configuration files | a 352 px `._cfg` list + a diff | S9 ☑ |
| `makeconf` | make.conf | one column: variable cards + a diff | S10 ☑ |
| `elog` | elog messages | a 352 px entry list + the text | S11 ☑ |
| `world` | @world set | `@world` at 560 px + the installed list | S11 ☑ |
| `profile` | Profile | one column, the profile list | S10 ☑ |

The recurring pattern: **a narrow list on the left (352 px) + details on the right**.
Implemented in S3 as `ui/pages/split_page.py`: a fixed-width list frame, a separator line and a
scrollable detail panel. A subclass fills in only `list_layout` and `detail_layout`.

The detail panel **does not scroll horizontally** — the content adapts to the width. That takes
one trick: a `QLabel` reports the width of its longest line as its minimum, so a long command or
description can push the panel wider than the window. Labels that are meant to shrink get a
horizontal size policy of `Ignored` (`_let_it_shrink()` in `search.py`).

## 5. Reusable elements

To be implemented once, in `gentstore/ui/widgets/`:

**`write_preview.py` — “Will be written”** *(S5)*
A header (“Will be written” + “a preview before saving”), the file path in small monospace, the
line itself framed on a `bg` background, a primary “Save” button and a secondary “Discard
changes”, and after the write a green “Saved” notice with the full message. Used on six screens
— this is the visual realisation of the “nothing quietly” principle from
[01-architecture.md](01-architecture.md).

**`log_view.py` — the command log**
A header with the command and metadata, 11.5 px monospace body, coloured lines (ordinary
`neutral-300`, warning `#d9b072`, error `#d98a72`, success `#74b58c`), auto-scrolling that stops
when the user scrolls up by hand. A variant with a progress bar and an “Interrupt” button for
`emerge`.

**`diff_view.py` — a diff of two files** *(S9)*
A `− old` / `+ new` legend, lines on a faint semantic-coloured background. Shared between the
configuration-files screen and the `make.conf` change preview.

**A note about colours:** transparency is written as `rgba(r, g, b, a)`, **not** as
`#RRGGBBAA`. Neither Qt's style sheets nor its rich text understand eight-digit hex — and rather
than reject it, they read it as something else. That is why a red removal and a green addition
came out as two identical olive stripes.

**`use_flag_row.py` — a USE flag row** *(S5)*
A 15 px checkbox, the name in bold monospace (with a `*` in the accent colour when it is
required), an origin badge (`profile` / `make.conf` / `per package` / `off by default`), a
one-line description, and a “What does this flag change?” link that unfolds a panel with: a
longer explanation, a **“Pulls in”** column (a list of atoms in `accent-300`), a **“Without this
flag”** column, and a footer saying where the description came from (`use.desc`, `metadata.xml`,
`DEPEND`).

**`block_notice.py` — the block notice** *(S6)*
A `shield-warning` icon coloured by the severity of the problem (amber for the routine ones, red
for a mask and for `-arch`), a title in plain language, and next to it Portage's raw words. For
`package.mask` — the maintainer's note **verbatim**, in a monospace frame, together with the
path of the file it came from. Below that an explanation, and for a licence a row of pills that
open the reader. The action button **writes nothing** — it shows `write_preview.py` with the
line ready.

**`licence_dialog.py` — the licence reader** *(S6)*
The full text from `licenses/<name>`, scrollable, with the acceptance button **below** the text.
At the bottom, a sentence saying that the acceptance covers one package — not `ACCEPT_LICENSE`
and not the group.

**`repo_badge.py` — the repository badge** *(S3)*
`::gentoo` → a `neutral-900` background, `neutral-400` text. An overlay → an `accent-800`
background, `accent-200` text. One glance is enough to tell the official from the unofficial.
Besides the widget, the module offers `draw_badge()`, so that the list delegate draws exactly
the same badge.

**`package_list.py` — the result list** *(S3)*
A `QListView` + a `QStyledItemDelegate`. A row fits four pieces of information into about 70 px:
`category/name`, the repo badge on the right, the description and a “version + state” line. It
is drawn, not assembled from widgets — a widget per row would rule out showing hundreds of
results. The font sizes are fractions of the row height, so the list scales along with the rest
of the interface.

**`flow_layout.py` — a wrapping layout** *(S3)*
Qt has none, and it is needed in two places: the repository filters and the version picker. At
130 % scale `::steam-overlay` alone takes up a third of the list panel, so a plain `QHBoxLayout`
was cutting off the last pill.

## 6. The “::gentoo only” switch

An element in the toolbar, because it concerns the whole application. Off: a `neutral-800`
border. On: an `accent` border, with two modes appearing next to it:

- **a) hide in the GUI** — a filter applied to the search results and the update preview;
  Portage is untouched, overlays keep syncing;
- **b) mask in Portage** — a real change: a `*/*::<repo>` entry in
  `/etc/portage/package.mask/<repo>`. Once that mode is chosen, the bar shows a literal preview:
  `+ /etc/portage/package.mask/guru → */*::guru`, and the write itself goes through the usual
  three beats of preview → write → report.

## 7. Styling in Qt

The theme is realised through **QSS generated from `tokens.py`** (an f-string), not a
hand-written CSS file — that way a colour changes in one place. The sheet is loaded once, in
`app.py`.

In addition:
- `QApplication.setStyle("Fusion")` — a predictable base regardless of the system theme.
- The `QPalette` is set from the tokens, so that widgets QSS does not cover (context menus,
  tooltips) are dark too.
- Colours are **never written into page code** — only CSS classes and tokens.

## 8. Accessibility and practice

- Full keyboard navigation: `Ctrl+1..9` switches pages, `Ctrl+F` focuses the search box,
  `Ctrl+L` jumps to the log, `Esc` closes unfolded panels.
- The 12.5 px base font is small — the Settings dialog offers a scale slider
  (100 % / 115 % / 130 %), implemented via `QApplication.setFont` and recomputing the QSS.
- Read-only fields holding commands and paths have to be selectable with the mouse
  (`QLabel.setTextInteractionFlags(TextSelectableByMouse)`) so that they can be copied.
- Every button that executes a command has a tooltip with the exact command that will run.

## 9. Screenshots

The pictures in `Docs/screenshots/` are taken off-screen (`QT_QPA_PLATFORM=offscreen`), in a
1520×960 window — and 1520×1000 for the screens with a step list and a table. They need no
graphical session and do not disturb the settings of a running application: the script points
`XDG_CONFIG_HOME` at a temporary directory.

| File | What it shows | Where it comes from |
|---|---|---|
| `search-and-install.png` | the query `mpv`, with a package selected | automatic |
| `use-flags.png` | `media-video/mpv`, the `vulkan` flag unfolded | automatic |
| `repository-filter.png` | `dev-libs/zydis` narrowed to `::guru` | automatic |
| `repositories.png` | the configured repositories + the catalogue, searching for `kde` | automatic |
| `update.png` | step 3 with the preview table filled in | **needs a system with pending updates** |
| `config-files.png` | a pending `._cfg` with its difference | **needs a system with a pending `._cfg`** |
| `settings.png` | the Settings dialog | automatic |

Refreshing the set:

```bash
python tools/i18n.py compile      # the catalogues have to be built for a non-English shot
python tools/readme_shots.py      # or --only <name>, --out <directory>, --lang pl
```

The script runs one real command — `emerge -pvuDN --changed-use @world` — and only in
`--pretend` mode; it writes nothing anywhere. The two shots marked above depend on the state of
the machine: on a system that is up to date and has no pending `._cfg`, they come out as empty
panels. When that happens it is better to keep the previous files than to put a picture that
shows nothing into the README.

The pictures currently in the repository were taken with the interface in Polish, from when the
documentation was Polish too. `--lang` now defaults to `en`, so the next refresh brings them
into line with this documentation.
