# Changelog

Everything worth knowing between one release and the next. Written as the work happens, so that
a release only has to be read off this file rather than reconstructed from `git log` afterwards.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the version
numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Dates are the day the
tag was made.

## [Unreleased]

### Removed

- **1.1.1 is withdrawn**: the release, its asset and its tag are deleted, and
  `gentstore-1.1.1.ebuild` and its `DIST` entry are out of the overlay, so Portage cannot resolve
  to a version that cannot be built. `CHANGELOG.md` keeps the section, marked `[YANKED]` the way
  Keep a Changelog asks — a withdrawn release is a fact about the project, and deleting the record
  of it would only make the version numbers skip for no stated reason. Two tests hold the two
  halves apart: that the marker is a section boundary the parser sees, since an unrecognised
  heading would fold the withdrawn notes into the release above, and that nothing marked
  `[YANKED]` still has an ebuild or a `DIST` entry, since a record is not a mechanism.

### Security

- **`emerge --unmerge '*/*'` passed the launcher's argument check.** The atom shape allows a
  wildcard in either half and said nothing about both at once, so a single command was the whole
  system — a great deal more than the "install, update or remove packages" the authentication
  dialog promises, and reachable without a dialog of its own for as long as polkit's
  `auth_admin_keep` remembers the answer. Nothing Gentstore runs needs it: the one place `*/*` is
  written is `*/*::<overlay>` into `package.mask`, and that goes to the helper.
- **The helper answered a malformed request with a traceback instead of an answer.** `keep` was
  the one field reaching `int()` unchecked, so `{"keep": "abc"}` raised a `ValueError` that
  `main()` does not catch: root printed a stack trace on stderr and no JSON at all, leaving the
  interface with nothing to report but an exit status. It is checked like every other field now,
  and `main()` has a last-resort clause so the "one JSON answer, always" contract holds even for a
  bug nobody has found yet.
- **`cfg_apply` could be aimed outside `/etc/portage` by a caller that first rewrote
  `make.conf`.** The directories it may reach come from `CONFIG_PROTECT`, described as read from
  root-owned files — and one of those files is one this same helper appends lines to on request.
  Where such an entry points is not the interesting part, and a list of blessed prefixes would
  only have broken the systems nobody thought of; what matters is whether somebody other than
  root could have planted the `._cfg` file waiting there. So an entry now has to be a directory
  that only root can write to, every parent included, and the question is asked only when the
  helper really is root — which is the only time the answer means anything.
- **A failed restore could take `/etc/portage` with it.** `restore` renames the configuration root
  aside and then renames the replacement into place; when the second rename failed, the first was
  never undone. It is undone now, before the refusal is reported.
- `replace_line` compiles a pattern the caller supplies, as root, and nothing in the standard
  library can time a regular expression out. The length is bounded now — a bound, not a cure, and
  said so where it is written. Every pattern Gentstore itself sends is `re.escape` around one
  `cat/pkg`.
- A `metadata.xml` is refused above a megabyte rather than parsed. ElementTree resolves no
  external entities but does expand internally defined ones, and `metadata.xml` comes from
  whichever overlay the user added.
- The screenshot tools built their throwaway configuration directory at a fixed name in `/tmp` —
  a name anybody on the machine can create first, as a symbolic link. It carries the uid, is made
  0700, and is checked to be a directory of ours and not a link.

### Fixed

- Deleting the tag broke every link comparing against it — `[1.1.1]`'s own, and `[1.1.2]`'s, which
  compared *from* it. One was noticed and one was not, so `tests/test_release.py` now asks git
  whether every ref the changelog links to still resolves.
- The README states the version **twice** — once as a claim, once inside the installer transcript
  it quotes — and only the first was ever rewritten, so the transcript had been offering 1.0.0 as
  "the release" since 1.1.0. `tools/release.py` now moves every mention in a file together.
- **A version stated twice in the same known form still moved only once.** The fix above covers
  the README's two *different* forms; a file using one form twice was left one duplication away
  from the original bug, because both the check and the rewrite stopped at the first match. They
  see every occurrence now. The test meant to guard this was blind to it for a second reason: it
  skipped any number that was not the current one, and a mention that has drifted is by definition
  not the current one — which is exactly why the stale `1.0.0` sat there unnoticed. It no longer
  filters, so a historical version quoted in one of these three files stops it, which is a
  decision worth stopping for.
- **`tools/release.py bump` could refuse after writing three of the four files.** Every other
  refusal happens before anything is touched; this loop wrote each file as it finished it, so a
  pattern that missed in the last one left the tree stating two versions at once and the changelog
  already closed. It is all worked out first now, and the refusal names which mention drifted
  rather than only which file.
- The README's test count, which said 514 against 554. That one stays hand-maintained: counting
  the suite means running it, and the release runner has neither Portage nor a Qt platform.
- **USE flags of a package from an overlay had no descriptions at all.** `use.desc` and
  `profiles/desc/*.desc` live in the master repository, and they were being looked for beside the
  ebuild, where no overlay carries them. `metadata.xml` and `use.local.desc` are per-repository
  and were always read from the right place.
- **`--lang` said "for this run" and meant "from now on".** One `gentstore --lang en` wrote the
  preference down, so every launch after it was English too. The View menu and the settings dialog
  still mean what they say.
- **The "Add overlay" dialog accepted `svn://` and the launcher then refused the command it had
  just enabled.** Two lists of URL schemes in two files, drifted apart; `svn` is back in the
  launcher's, where the dialog's sync-type list had always assumed it was.
- **A `._cfg` file could arrive on the configuration screen twice.** `CONFIG_PROTECT` is assembled
  from `make.globals`, `make.conf` and every file in `/etc/env.d`, and any of them may name a
  directory that is already inside another; both were walked.
- **A preview reporting a blocker could be summarised as "nothing to do".** Blockers and `!!!`
  lines were parsed and then never shown. Usually that hid nothing, because emerge exits non-zero
  when it prints them and the failure panel takes over — but usually is not always. They appear
  with the configuration changes emerge asked for, and those are now listed with each heading
  above its own lines rather than every heading followed by every body.
- **`packaging/make-overlay.sh` picked the newest release in collation order**, where 1.1.10 sorts
  before 1.1.2 and "last" is therefore not "newest". Nothing has reached two digits yet, which is
  why it read as correct. It uses `sort -V`, the same as the release workflow.
- `packaging/publish-overlay.sh` interpolated `git config user.name` straight into the commit it
  makes, and a checkout with no identity configured — a fresh CI runner, a machine where git was
  never introduced to its owner — made that an empty name and a failure several lines later about
  something else. There is a named fallback.
- **The advice did not stop once it had been taken.** "The installed gentstore-helper is from an
  older version — run `sudo make install-system`" was worked out once and then remembered for the
  life of the process, so somebody who ran it went on being told to for the rest of the session,
  about a file that had by then been replaced. The answer is still remembered, but only for as
  long as the file it describes has not moved. Every test of that code passed `refresh=True`,
  which is why it survived: nothing in the running application does.
- **"All repositories" showed nothing until something was typed into it.** `Catalogue.search`
  answers an empty query with an empty list, which is right for a search and wrong for a panel:
  the screen offered one line of instruction where four hundred and fifty-nine repositories were,
  and a name nobody knows yet cannot be guessed at. It opens on the list now — `Catalogue.browse`,
  ordered the way the search breaks its own ties, best-kept first and Gentoo's own ahead of a
  stranger's within a quality — and the search box narrows it. Fifty rows at a time either way,
  with the count and "type to narrow the list" underneath when there are more, so a catalogue
  smaller than that never has to be searched at all. Repositories already configured go to the end
  rather than heading the list as ::gentoo, official and core, otherwise would.
- **A repository row on the Repositories screen only answered a click on its name.** The row
  highlights as a whole on hover, so the whole row reads as the target — but the click handler
  hung off the name label alone, and a click on the package count, the sync date or the empty
  space to their right did nothing at all. The row handles the click now, the way the rows on the
  configuration-files and update screens already did.
- Smaller corrections with no visible effect: a background task whose receiver vanished mid-flight
  stayed in the pending set for the life of the process; `Command.close()` tore its process down
  by hand and skipped half of what `_teardown()` does; `PortageEnv.configured()` invited nesting
  and would have repointed the outer block's settings if anything had taken it up; a plan for
  something that is not a `cat/pkg` named a directory rather than a file; and a size in plain
  bytes parsed as no size at all.

## [1.1.2] — 2026-08-31

### Fixed

- **The 1.1.1 tarball failed its own test suite**, and so failed to build under `USE=test`. Two
  tests in `tests/test_release.py` read the tree's real `[Unreleased]` section and needed
  something in it — but releasing is precisely what empties that section, so they were red in
  exactly the state every release tarball is cut in, which is also where the ebuild runs the
  suite. The fixture now writes the section it needs instead of borrowing whatever the tree
  happens to hold, so where in the release cycle a checkout sits no longer decides whether the
  tests pass.

## [1.1.1] — 2026-08-31 [YANKED]

**Withdrawn**, and not installable — the tarball failed its own test suite, so the ebuild died in
`src_test` for anybody building with `USE=test`. The release, its asset and its tag are gone, and
the overlay no longer carries the ebuild. Everything below shipped again in 1.1.2, which is the
first release that actually builds. Kept here rather than deleted, because it is still the honest
answer to when any of it arrived.


Nothing in the application changed — hence a patch number. What changed is how a release is made,
which until now was ten steps carried in somebody's head, and 1.1.0 is the release that shows
what that costs: it went out with the README still announcing 1.0.0 and notes claiming "No
functional changes" across twenty-one commits.

### Added

- **A release is a button.** `Actions -> Release -> Run workflow -> the version` rewrites the four
  files that state a version, commits, tags, builds the tarball, publishes the release with this
  file's section as its notes, writes the ebuild and its `Manifest` entry, and republishes the
  overlay branch. `tools/release.py` is the part that owns the numbers and can be run by hand;
  `tests/test_release.py` fails the moment the four disagree. A tag pushed by hand runs the same
  thing minus the rewrite, and refuses a tag whose tree still states the old version. See D-12.
- **The overlay branch republishes itself.** Any push to `main` touching
  `packaging/app-portage/` regenerates it, rather than waiting for somebody to remember
  `publish-overlay.sh`. A release already republished at the end; what that missed was the live
  ebuild, which changes between releases and on its own — and the branch had already drifted from
  the tree by a comment before this existed.
- The live ebuild installs `CHANGELOG.md` alongside the README, so `/usr/share/doc/${PF}/` says
  what changed. The 1.0.0 and 1.1.0 ebuilds cannot: the file postdates both their tarballs, and
  `dodoc` dies on a file that is not there. Every release from here on carries it, and the
  workflow adds the line to the ebuild it generates.
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

[Unreleased]: https://github.com/JamJan05/GentStore/compare/v1.1.2...HEAD
[1.1.2]: https://github.com/JamJan05/GentStore/compare/6dd751f...v1.1.2
[1.1.1]: https://github.com/JamJan05/GentStore/compare/v1.1.0...6dd751f
[1.1.0]: https://github.com/JamJan05/GentStore/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/JamJan05/GentStore/compare/77bafbc...v1.0.0
[0.1.0]: https://github.com/JamJan05/GentStore/commit/77bafbc
