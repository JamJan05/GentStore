# Changelog

Everything worth knowing between one release and the next. Written as the work happens, so that
a release only has to be read off this file rather than reconstructed from `git log` afterwards.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the version
numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Dates are the day the
tag was made.

## [Unreleased]

### Added

- The live ebuild installs `CHANGELOG.md` alongside the README, so `/usr/share/doc/${PF}/` says
  what changed. The release ebuilds cannot: the file postdates both their tarballs, and `dodoc`
  dies on a file that is not there. From 1.2.0 their ebuilds can take the line too.
- `tests/test_packaging.py` checks `dodoc` targets too, against the tree each ebuild actually
  builds from: the live one against this checkout, a release one against its own tag. The
  existing check stopped at `newexe`/`doins`/`domenu`/`doicon`, so a `dodoc` line naming a file
  that is not there — a `die`, not a warning — had nothing watching it.

## [1.1.0] — 2026-08-31

Mostly about conditional licences — the ones a package only owes you once a USE flag is on.
Gentstore got those wrong in a way that looked like it was working.

### Fixed

- **A package masked by a licence *and* a keyword showed no mask at all** — no licence dialog, no
  accept button, no `package.accept_keywords` line, nothing until `emerge` refused in a terminal.
  Portage resolves a conditional `LICENSE` through `settings.setcpv()`, which needs a
  configuration it may write to; Gentstore handed it the shared, locked one, the call raised
  `Configuration is locked.`, and both callers swallowed it into an empty answer. `PortageEnv`
  now lends out a per-package clone under a re-entrant lock.
- **Conditional licences were evaluated against an empty USE**, so every `flag? ( … )` group read
  as false. Building `sci-ml/lmstudio-bin` with `cuda` on showed one licence to accept, and then
  `emerge` refused over `NVIDIA-CUDA`, which Gentstore had never mentioned.
- **The shape of a licence expression was mistaken for licences.** `|| ( MIT GPL-2 ) license(s)`
  was split on whitespace, so `(` and `)` became clickable chips — and tokens that would have
  been written into `package.license`. The structural tokens are dropped; `Block.raw` still
  carries Portage's sentence unaltered, so the shape is still on screen.
- **A masking check that failed was indistinguishable from a package that is fine.** Both came
  back empty, which everything downstream read as "nothing is blocking this": the install button
  worked and `emerge` then refused. A failed check now yields one `UNKNOWN` block, the notice
  reads "Could not be checked", the version picker tags it `unchecked`, and `gentstore show`
  prints `masking unknown`.
- **Change lines were dropped from `emerge`'s output depending on their operator.** The parser
  ended a block by each line's first character, keeping only space, tab, `#` or `>`. Those lines
  are atoms, so `>=cat/pkg-1 flag` survived while `=cat/pkg-1 SOME-EULA` and `=cat/pkg-1 ~amd64`
  did not — licence and keyword blocks were parsed down to their heading and comments, with the
  one line you actually have to write thrown away. A block now ends where `emerge` ends it.

### Added

- **A "licences waiting behind a USE flag" section on Masks and licences.** Every other section
  there is a file that has already been read; this one is the opposite question — what would this
  system refuse next — so it is computed rather than read, and it is the only section with no
  line to remove. Rows name the package's `LICENSE` and then, per flag, the plain sentence:
  turning `rar` on also means accepting `unRAR`. Only licences `ACCEPT_LICENSE` does not already
  cover are listed, in both directions, since `!bindist? ( … )` costs when the flag goes off.
  The scan reads `LICENSE` for every ebuild in every repository — 21716 packages in about three
  seconds on the development machine — so it runs on a worker and says so while it works. Of the
  176 packages carrying a conditional `LICENSE` it reports the 28 that matter.
- **The `/etc/portage` line `emerge` stopped for, on Search and install.** Getting a version past
  Portage's visibility checks does not stop `emerge` refusing over a dependency that needs a
  feature turned on, and that refusal used to arrive as raw text in the terminal pane with
  nothing to press. Each line is now shown with the package that asked for it, wired into the
  existing preview → save → report path; a row's button only shows the line, and nothing is
  written until Save. Read back regardless of exit code, because a run stopped by autounmask
  always exits non-zero. `REQUIRED_USE` conflicts are left out — they still need the flag panel.

### Changed

- **The overlay is a synced repository.** It used to be a directory the installer filled in once,
  with `auto-sync = no`, so a later ebuild reached nobody. Portage now clones the `overlay`
  branch and ebuilds arrive with an ordinary `emerge --sync`. `publish-overlay.sh` generates that
  branch from `packaging/` so the two cannot drift, and refuses to publish a `SRC_URI` ebuild
  whose `DIST` entry is missing. A live install is rebuilt with `@live-rebuild`.
- **The installer installs the release, and asks before doing otherwise.** `9999` sorts above
  every release there will ever be, so accepting the live ebuild quietly made it win for
  everyone, including people who piped the installer somewhere and were never asked. On a
  terminal it now offers the choice after the sync, so it can name the version that actually
  arrived; with no terminal the release wins. `--stable` and `--live` skip the question.
- **Licensed under `GPL-2.0-or-later`.** Gentstore was GPL-2 only, while PyQt6 is distributed by
  Riverbank under the GPL v3 only, and those two are incompatible — the project could not be
  distributed as it stood. The "or any later version" clause is the smallest change that resolves
  it, keeping the licence family Portage is in. `LICENSE` is unchanged and deliberately so: the
  GPL-2 text is still correct, because the permission lives in the file headers rather than in
  the licence body. A distributed build links PyQt6 and is therefore effectively GPL v3. The
  ebuilds declare `LICENSE="GPL-2+"`.

## [1.0.0] — 2026-08-30

Both halves had now run against a live system, which is what the version number was for. Over
28–30 August the application drove 73 privileged invocations through `pkexec` — `emerge`,
`emaint sync`, `eselect news` — and wrote real `package.use`, `package.license` and
`package.accept_keywords` entries through the helper, each preceded by its own `/etc/portage`
backup. The "not yet verified end to end" caveat the documentation had carried since S4 was
replaced with what was actually observed.

### Added

- A release ebuild alongside the live one, pointing at a tarball attached to the GitHub release
  rather than the archive GitHub generates from the tag — the generated one has changed bytes
  under distributions before, and a Manifest that stops matching is everybody's fetch failure at
  once. Keyworded `~amd64` and nothing else: one machine has run this, and it is amd64.

## [0.1.0] — 2026-08-30

The first alpha: a PyQt6 front-end for Portage on Gentoo Linux, covering nine screens — search
and install, USE flags with an explanation of what each one changes, masks and licences,
repositories and overlays, the system update cycle, `._cfg` configuration files, `make.conf`, the
profile, elog messages and the `@world` set.

Built on four rules: the GUI never runs as root, every change to `/etc/portage` is previewed
before it is written, the user's files are appended to rather than overwritten, and package data
comes from the `portage` API rather than from parsing ebuilds. Everything privileged goes through
`pkexec` and two small stdlib-only programs in `/usr/libexec`.

Bilingual (Polish and English) through Qt's own translation system; the documentation and the
source strings are English.

[Unreleased]: https://github.com/JamJan05/GentStore/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/JamJan05/GentStore/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/JamJan05/GentStore/compare/77bafbc...v1.0.0
[0.1.0]: https://github.com/JamJan05/GentStore/commit/77bafbc
