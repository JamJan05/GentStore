# Gentstore documentation

Gentstore — a graphical front-end for Portage on Gentoo Linux (Python 3 + PyQt6).

## Contents

| Document | What is in it |
|---|---|
| [01-architecture.md](01-architecture.md) | Layers, directory structure, threading model, data flow |
| [02-ui-design.md](02-ui-design.md) | Theme tokens, screen inventory, mapping the mock-up onto Qt widgets |
| [03-i18n.md](03-i18n.md) | Polish/English bilingualism — rules, tools, translation workflow |
| [04-privileges.md](04-privileges.md) | The privilege model, the root helper, polkit, writing to `/etc/portage`, backups |
| [05-session-plan.md](05-session-plan.md) | The work split into sessions S1–S12 with completion criteria |
| [06-decisions.md](06-decisions.md) | Design decisions (ADRs) with their reasoning |

## Source material

Two files shaped the project and are **not kept in the repository** (see `.gitignore`):

- `../prompt-gentoo-gui.md` — the full functional brief (requirements 1–7).
- `../Gentoo portage UI prototype.zip` — the UI mock-up (a Claude Design canvas, nine screens,
  the “nocturne” theme).

Everything from them that the code needs has been copied here — the colour and spacing tokens
into [02-ui-design.md](02-ui-design.md), the requirements into the session plan — so working on
the code never means unpacking the archive.

## Project status

**All sessions S0–S12 are finished.**

The sessions: documentation, the foundation, the Portage layer, the “Search and install”
screen, privileges and command execution, USE flags, masks and licences, repositories and
overlays, the system update, configuration files, `make.conf` and the profile, and finally elog
and `@world`. The application starts: the window, the theme, navigation across nine screens and
switching between Polish and English without a restart. The backend reads real data from
Portage and can be checked without the GUI:

```
python -m gentstore.core.cli search mpv
python -m gentstore.core.cli show media-video/mpv
```

The first screen works on real data: searching by name, category and description, repository
filters, a detail panel with versions and keywords. The “Pretend”, “Install” and “Uninstall”
buttons run real commands, and their output goes live into the log panel at the bottom of the
window, which has an “Interrupt” button. Operations that need root go through `pkexec` and two
small programs in `/usr/libexec/gentstore` — see [04-privileges.md](04-privileges.md) and
`make install-system`.

The package screen also has a full **USE flags** panel: every flag with its origin (ebuild /
profile / `make.conf` / per package), the description from the repository and an unfoldable
explanation of exactly what it changes; a `REQUIRED_USE` section validated as you go; and a
preview of the exact line that will go into `/etc/portage/package.use`, before anything is
written.

A blocked package says **why**: for a mask — with the maintainer's note and the file it came
from; for keywords — whether it is “not stable yet”, “untested” or “marked as not working”; for
a licence — which licence has to be read, with the full text and an acceptance scoped to a
single package. The **Masks and licences** screen reads back the whole contents of
`package.accept_keywords`, `package.unmask`, `package.license` and `package.mask` — with the
file each entry lives in, and the option to remove it.

The **Repositories** screen shows the configured repositories together with their `repos.conf`
section verbatim, and lets you search the catalogue of 459 Gentoo repositories — enabling one
is a single click, followed by `eselect repository enable` and `emaint sync -r`. Removing one
says plainly how many installed packages will lose their ebuild; adding a repository from
outside the catalogue gets its own dialog warning that its ebuilds will run as root.

The **System update** screen is six steps, each run separately and described by the command it
will execute: sync, news (only the items that concern this system, with the reason next to
each), a preview in the form of a table (package, old → new version, USE changes, size, binary
or built), the update itself with a live log, `--depclean` with the list shown before anything
is removed, and the move on to the configuration files. Alongside it, a security-warning panel.
A failed build does not disappear into the log: the package, the `build.log` path and a hint
for the usual causes are pulled out of several hundred lines.

The **Configuration files** screen shows every pending `._cfg` file, with the package that left
it and the number of changed lines. On the right the difference, and under it three answers:
keep mine, take the new one, or merge by hand in an editable panel. The version being replaced
always goes to `/etc/config-archive` first.

The **make.conf** screen shows two values for each variable — the one from the file and the one
Portage actually uses — because for `USE` and `FEATURES` they are not the same. A change
replaces one line, with the difference shown beforehand; `MAKEOPTS` gets a suggestion computed
from the core count and the amount of memory. The **Profile** screen lists the profiles from
`eselect`, marks the current one and, before a change, says plainly that the whole machine will
have to be rebuilt afterwards.

The **elog messages** screen collects what packages said during installation — the messages
that scroll past the screen and vanish. The **@world set** screen puts side by side the list of
packages you asked for and everything that is actually installed.

Nine screens, a Settings dialog, restoring an `/etc/portage` backup with a difference shown
before the decision, binary package support and packaging (`make install`, a draft ebuild). The
translation catalogue is complete in both languages, and the behaviour with missing
dependencies and an empty `/etc/portage` has its own set of tests.

What comes next — see the “What is left” section in [05-session-plan.md](05-session-plan.md).

## Working rules

- No git commits without the repository owner's explicit consent.
- Every session ends in a runnable state and with an entry in `Docs/05-session-plan.md` (ticked
  off, plus notes).
- The application speaks Polish and English — there are no hard-coded Polish strings in the
  source.
