# Changelog

Everything worth knowing between one release and the next. Written as the work happens, so that
a release only has to be read off this file rather than reconstructed from `git log` afterwards.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the version
numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Dates are the day the
tag was made.

## [Unreleased]

### Added

- **Everything Portage wants changed, in one screen and one password.** Installing Hyprland
  meant meeting one refusal at a time: a keyword, then a mask, then a licence, then a USE flag,
  with a full dependency resolution between each. The search screen now has an **Analyse
  requirements** step that runs `emerge --pretend --autounmask` with the options the install
  button would use, and shows everything that came back at once — grouped by the file it belongs
  in, each line with the package that asked for it, each with a checkbox. Applying them is one
  privileged operation and one authentication for the whole set, instead of one per line; for
  that package it is fourteen lines, so it used to be fourteen password prompts for a decision
  made once. The exact files and the exact lines are shown before anything is sent, and after the
  write the analysis runs again by itself, because the plan described the system as it was before
  it was applied.

  Three things are deliberately not folded into the total. `package.unmask` undoes something a
  developer decided on purpose, so it is graded like the block notice grades it and starts
  unticked. A `**` keyword means nobody has tested the package on this architecture at all, and a
  `9999` atom builds whatever upstream pushed this morning; both are marked and both start
  unticked. And when Portage reports a conflict *beside* a block of changes, that conflict was
  worked out before the changes existed — Portage stops resolving as soon as autounmask has
  something to say, and says so — so the lines are still offered and the screen says why the
  conflict may not survive them.

  The `--autounmask` in that command is not decoration. Portage enables autounmask by itself for
  keywords, masks and USE flags, but leaves `--autounmask-license` off unless asked explicitly
  (`_emerge/create_depgraph_params.py`), so the previous preview could never mention a licence —
  the one refusal a user has no way to guess at. `--autounmask-write` and `--autounmask-continue`
  are refused by the launcher: the one program here that writes to `/etc/portage` is the helper,
  after the user has read the lines.

- **The install button waits for that answer.** It stays disabled until an analysis of exactly
  the command it would run comes back with nothing to write and nothing conflicting. The gate is
  the command line itself, so choosing another version or turning binary packages on closes it
  without anything having to remember to. Output that could not be read keeps it shut too: a
  check that failed must not be mistaken for a check that passed.

- **`append_lines` in the privileged helper.** A list of path-and-line pairs, every one of them
  checked exactly as if it had arrived alone, and all of them checked before the first is
  written — one bad entry changes nothing at all. It reaches four files rather than the six
  `append_line` reaches: `make.conf` decides what Portage *does* rather than which packages it
  installs, and `package.mask` adds a restriction rather than lifting one, and neither has ever
  appeared in an autounmask block. The interface keeps the same four names and a test compares
  the two lists. `PROTOCOL_VERSION` is 2, so an interface talking to an older installed helper
  can say so rather than reporting a malformed request. Decision D-18.

### Fixed

- **The package frame reported on runs that were not about that package.** One runner and one log
  panel serve the whole window, so every command ends up back in the search screen. Pressing
  "Update @world" in the toolbar with a package on screen left that update's report inside the
  package's frame — a conflict about the whole system, shown under the name of something the run
  never mentioned. The frame is now filled only by commands the screen itself started.

- **Two kinds of "conflict" that were not one.** `!!!` is not a verdict: an ordinary `@world`
  update resolves the graph, prints its merge list, exits zero and still says
  `!!! The following update(s) have been skipped due to unsatisfied dependencies` on the way past.
  Reading every such line as an unresolved graph announced failure over a run that had worked.
  And `[blocks b ]` is not `[blocks B ]`: Portage writes the letter in lower case when it worked
  the block out for itself and says so in its own summary, `Conflict: 1 block (all satisfied)`.
  Counting those as conflicts would have withdrawn the very lines that make such an install work.
  What counts now is an *unsatisfied* blocker, the slot-conflict banner, or the sentence about
  packages that cannot be installed at the same time.

- **Closing the window during a long read crashed on the way out.** A background task that
  finished while Qt was tearing down found its signal object already destroyed on the C++ side
  and raised inside a `QRunnable`, which Qt turns into an abort. Building the package index takes
  seconds, so closing the window in that time was enough. The guard for this was already there
  and already documented; it wrapped the emit, while the failure was one line above it, in
  reading the signal off an object that no longer existed. The signal is now named rather than
  passed, so the lookup happens inside the same `try`.

- **The directory the preview promised is now actually created.** Gentoo's recommended form for
  `package.use` and its neighbours is a directory with one file per package, and the panel has
  always said so before writing: *"Neither package.unmask nor a directory of that name exists
  yet. Gentoo recommends the directory form, so that is what will be created."* Nothing created
  it. The path check requires a target's parent to be a directory already, so on a system that
  had never unmasked anything the write was refused with a message about a directory the user
  had just been told would appear — and unmasking is exactly what somebody installing from an
  overlay is most likely to be doing first.

  The path check is unchanged. A separate step creates that one directory, and only where the
  path resolves to exactly `/etc/portage/<name>/<file>` for one of the `package.*` names, with
  nothing there yet in any form. `make.conf` is excluded by name — it is the one file on that
  list, and a directory of that name would leave Portage reading an empty directory where its
  main configuration file belongs. A symlink in the way is left for the path check to refuse.


## [1.3.5] — 2026-09-04

### Added

- **The package list is ready when the window is.** Building the search index — every `cat/pkg`
  in every repository, with a description for each — is 3.1 s on this machine, and it happened
  again on every start, which is the longest anybody waited for anything here. The finished index
  is now written to `$XDG_RUNTIME_DIR/gentstore/` and read back in 0.07 s, so only the first run
  after a boot pays for it. The runtime directory is a tmpfs the system clears when the session
  ends, which is the coarse invalidation rule; the fine one is a fingerprint of the repositories —
  which are configured, where they are, and when each of their directories was last written —
  checked in about a millisecond before the file is used, so a sync, an enabled overlay or a new
  ebuild in a local repository all rebuild rather than answer from yesterday. The diagnostic CLI
  reads the same file, so `cli search` is as quick from the shell.
  `GENTSTORE_INDEX_CACHE=0`, or `--no-cache`, builds from Portage every time.

- **The project has a page.** <https://www.gentstore.dev> — every screen at full size, the
  installation in order, and what each principle costs in practice, in Polish and English. It is
  built from the `Web` branch of this repository, which carries the site and nothing else, and a
  release now tells it which version it is instead of leaving the number to be noticed later. The
  README and the repository's own Website field link to it; nothing in here pointed at it before.

### Security

- **The helper wrote lines into any file under `/etc/portage`.** `/etc/portage` is not a
  directory of inert settings: `bashrc` is sourced by every merge, `package.env` names files in
  `env/` that set any variable a build sees, `postsync.d` holds programs run after a sync. A line
  appended to one of those is code running as root later on, bought with one authentication that
  said “change the Portage configuration”. `append_line`, `replace_line` and `remove_line` now
  reach the six files the interface actually writes — the five `package.*` names and `make.conf`
  — and nothing else. A list of what Gentstore writes rather than of what looks dangerous, which
  is the half that also covers the files nobody has thought of.

- **The launcher allowed combinations of options nothing here builds.** A set of permitted
  options permits every combination of its members: `--unmerge` and `@world` were both on the
  list and neither is wrong on its own, but together they are a command that removes the system,
  and `--depclean` with a package beside it is a different operation from the one the update
  screen previews. Replaced with a table of the eleven whole command lines `runner/emerge.py`
  builds, matched token by token. A package set can no longer appear where a package is expected.

- **Polkit asked once and remembered.** `auth_admin_keep` remembers, for a few minutes, that this
  user authenticated for this action — not that this window may carry on — so anything else
  running as that user reached the same two programs inside that window with no dialog of its
  own. Both actions are now `auth_admin`. A six-step update asks six times, which is what a
  six-step update is.

- **`ROOT=/mnt/gentoo` described one system and would have changed another.** Portage honours
  `ROOT`, `PORTAGE_CONFIGROOT`, `SYSROOT` and `EPREFIX`, so the window described whatever they
  pointed at; nothing privileged followed, because the helper's root is a constant and the
  launcher's child gets a fixed environment. Privileged operations are now refused outright while
  any of the four points somewhere else, with a message saying why. Reading a chroot still works.

- **A value typed into the settings screen could change the syntax of `make.conf`.** It went
  between two quotes as it stood, so a line break wrote a second assignment and a quote ended the
  first. Values are now limited to what the nine editable variables actually hold — flags,
  keywords, licence groups, option strings, locale codes, `make` options. The cost is that
  `MAKEOPTS="-j$(nproc)"` can no longer be written from the screen; it can still be read, shown
  and left alone.

- **`EMERGE_DEFAULT_OPTS` went round the launcher's whole table.** `emerge` reads that variable
  out of `make.conf` and puts it in front of the argument list before working out what it has
  been asked to do, so the command Gentstore built, the command the window showed and the
  command the launcher checked could all agree with each other and still not be the operation
  Portage carried out. Some of what could arrive that way is not a matter of degree: `--root`,
  `--config-root` and `--sysroot` in those options are read early and put straight into the
  environment of the `emerge` process, which moves the whole operation to another system — and
  the variable is one the settings screen itself edits. Every command now carries
  `--ignore-default-opts`, and the launcher requires it rather than tolerating it.
  `EMERGE_DEFAULT_OPTS` still applies to the `emerge` you run in a terminal, which is what it
  was always supposed to mean.

- **The helper took any single line for `make.conf`.** The path check said which file; nothing
  said which line, and `make.conf` is the one file on that list whose contents decide what
  Portage *does* rather than which packages it installs — `PORTAGE_BASHRC` names a script
  sourced during every merge, `ROOT` and `PORTAGE_CONFIGROOT` move the whole operation. The
  settings screen refused to type those, and that was all that was stopping them; the helper
  reads its request from stdin and is not in a position to assume what wrote it. It now requires
  an assignment to one of the nine variables the screen offers, with a value from the same small
  character set. `replace_line` carried the sharpest version — it checked that its pattern found
  exactly one line and never looked at what was going in its place, so a request could say “find
  the line matching `USE=`” quite honestly and hand over `ROOT="/somewhere"`.

- **The two privileged programs asked `PATH` which Python they were.** `#!/usr/bin/env python3`
  for something started as root, where pkexec sanitises the environment and `sudo` has a
  secure_path — never the easy hole it looks like, and one fewer thing between the dialog and what
  runs. The ebuild now calls `python_fix_shebang`, which pins the exact interpreter the package
  was built for.

### Fixed

- **Picking a `::repo` narrowed the metadata but not the configuration.** Every `aux_get` already
  carried `myrepo=`, but the per-package configuration beside it came from `setcpv(mydb=portdb)`,
  which takes no repository and gets whichever one Portage ranks higher. A package chosen from
  `::guru` could be described with `::guru`'s `IUSE` and `::gentoo`'s repository-level
  `package.use` — and the second half decides where the flags in the window sit. The metadata is
  now fetched with `myrepo=` and handed to `setcpv()` as a mapping, which is the branch Portage's
  own `Package` objects go through.

### Changed

- The package announces itself as `Development Status :: 4 - Beta`. One machine, amd64 only, and
  an ebuild keyworded `~amd64`: `5 - Production/Stable` was claiming more than the keyword does.

- **The documentation describes the privileged half as it is now.** `Docs/04-privileges.md` says
  which files the helper writes and which lines it will take for `make.conf`, why every step asks
  for a password, and what `--ignore-default-opts` is for. `Docs/06-decisions.md` gained four
  entries for the decisions those two passes made, including the ones deliberately not made.

  One of those corrections is worth reading if you went looking for something: the backup section
  said the alternative form is a `tar.zst` in `/var/backups/gentstore/`. It is a `tar.gz`, and it
  goes to `/etc` beside the directories. The ten-copy limit is also a default and not a rule —
  it is a setting between 1 and 100, which is why a machine can hold more than ten of them and
  nothing be wrong.

## [1.3.1] — 2026-09-03

### Changed

- **Nothing ran the test suite except this machine and the ebuild on a user's.** That is what
  1.1.1 cost: a release whose own tests failed, so `emerge` with `USE=test` died in `src_test` for
  everybody who tried it, and nothing in between had looked. Two workflows now do. `tests.yml`
  runs `ruff` and the suite on `ubuntu-latest` for every push and pull request, in about two
  minutes — `pip install portage` makes that possible, since Portage publishes to PyPI, so the
  pure functions that need `portage.versions` work on a host with no Gentoo on it.
  `tests-gentoo.yml` runs the whole suite nightly inside a `gentoo/stage3` container with a
  repository snapshot mounted from `gentoo/portage`, which is the only place the tests that read a
  real tree can run at all.
- **A test could pass by skipping for the wrong reason.** The gate in front of every "against the
  real system" test knew one way a host can fail to be Gentoo — the module missing — and four
  modules had their own copy of it. `pip install portage` is the other way: the import succeeds
  and then answers every question with nothing, so `assert 0 > 100` fails and reads like a broken
  test rather than a host with no packages. One fixture in `tests/conftest.py` now, and it skips
  on both.
- **The README's pictures are the application as it is now.** Every one of them dated from before
  1.0.0 — the interface was Polish then, and the Repositories screen in them no longer exists.
  Retaken in English, with two for repositories rather than one, since the screen now answers two
  questions in two tabs, and the Settings dialog added to the table: it was already being
  generated and shown nowhere. `config-files.png` is the exception and stays as it was, because
  this machine has no `._cfg` waiting and the honest shot is an empty panel.
  `tools/readme_shots.py` drives the new screen — its old `_search.setText("kde")` would now type
  into the Configured tab's filter and photograph an empty list — and `overlay-filter.png`, which
  nothing has referred to since 0.1.0, is gone.

### Fixed

- **The window called itself "python 3.14" and wore the compositor's fallback icon.** On Wayland a
  panel identifies a window by its `app_id` and nothing else — there is no `WM_CLASS` to fall back
  on — and Qt, given no desktop file name to work from, built one out of the reversed organisation
  domain and the basename of `/proc/self/exe`, which for anything started through a Python entry
  point is the interpreter. The surface announced itself as `org.gentoo.gentstore.python3`, Plasma
  went looking for a desktop entry of that name and found none, so the window had neither a label
  nor an icon to show. Both the entry and the icon have shipped since 1.0.0; nothing connected
  either of them to the window. `setDesktopFileName` settles the `app_id`, and the application now
  sets its own window icon for the session that fails to find the entry anyway — looking the file
  up along `XDG_DATA_DIRS` itself, because with Fusion on a session that exposes no icon theme
  Qt's search paths are `:/icons` alone and the file sitting in `hicolor` is invisible to
  `QIcon.fromTheme`. X11 was never affected: there the class name comes from `applicationName`, so
  it has read `Gentstore` all along.

## [1.3.0] — 2026-09-01

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

### Changed

- **The Repositories screen is one list with two tabs, not a list and a panel underneath it.**
  "Configured" and "Available" are the same question asked at different times, and they now have
  the same shape: one search box serves whichever tab is open, and picking a row fills the right
  side. Picking a configured repository additionally shows **what it brings** — the packages that
  come from it and nowhere else, read out of the search index, forty of them with a way through to
  the package screen for the rest and a click on any one of them opening it there. Picking an
  available one shows who runs it, where it syncs from, the two commands enabling it would run,
  and — for a repository Gentoo does not run — what trusting it means, in place of the bare
  "Enable" button the old rows carried. The catalogue browser that used to sit below the details,
  off the bottom of the screen for any repository with a long `repos.conf` section, is gone: it is
  the "Available" tab now, and the list pane scrolls, which it did not before.

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

[Unreleased]: https://github.com/JamJan05/GentStore/compare/v1.3.5...HEAD
[1.3.5]: https://github.com/JamJan05/GentStore/compare/v1.3.1...v1.3.5
[1.3.1]: https://github.com/JamJan05/GentStore/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/JamJan05/GentStore/compare/v1.1.2...v1.3.0
[1.1.2]: https://github.com/JamJan05/GentStore/compare/6dd751f...v1.1.2
[1.1.1]: https://github.com/JamJan05/GentStore/compare/v1.1.0...6dd751f
[1.1.0]: https://github.com/JamJan05/GentStore/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/JamJan05/GentStore/compare/77bafbc...v1.0.0
[0.1.0]: https://github.com/JamJan05/GentStore/commit/77bafbc
