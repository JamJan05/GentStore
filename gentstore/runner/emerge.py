# GentStore — graphical frontend for Portage
# Copyright (C) 2026  JamJan05
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Building the ``emerge`` command lines Gentstore runs.

Kept in one place and away from the screens, so that "what exactly will this
button run" is a question with a single answer that can be read, tested and put
in front of the user before anything happens. Every screen shows the string
these functions produce before running it.

Three flags are on every command. ``--color=n`` because escape sequences in a
log widget are noise, ``--nospinner`` because the spinner is written with
carriage returns that a log cannot animate, and ``--ignore-default-opts``
because otherwise the command that runs is not the command anybody agreed to.

``emerge`` reads ``EMERGE_DEFAULT_OPTS`` out of ``make.conf`` and puts it in
front of the argument list before deciding what it has been asked to do
(``_emerge/main.py``: ``if "--ignore-default-opts" not in myopts``). So the
string this module builds, the string the window shows, and the string
``gentstore-launcher`` checks against its table can all agree with each other
and still not be the operation Portage carries out — and some of what could
arrive that way is not a matter of degree: ``--root``, ``--config-root`` and
``--sysroot`` in those default options are read early and put straight into the
environment of the ``emerge`` process, which moves the whole operation to
another system.

Not solved by clearing the variable in the environment, because it does not
have to come from the environment. Not solved by validating its contents,
because that would be a second, weaker copy of the table in the launcher. The
command is simply built to ignore it — and the settings screen still edits the
variable, which now means what it says: it applies to the ``emerge`` the user
runs in a terminal, and not to the ones this window runs on their behalf.
"""

from __future__ import annotations

from collections.abc import Iterable

from .command import CommandSpec

#: Kept in this order, and the launcher's table has the same three at the front
#: of every row: the two files are checked against each other by the test suite,
#: and an option that is present in one order and absent in another is exactly
#: the drift that check exists to catch.
_BASE = ("emerge", "--ignore-default-opts", "--color=n", "--nospinner")

#: Forced on every command whose output gets parsed.
#:
#: ``emerge`` formats sizes with the thousands separator of the current locale.
#: On a Polish system that is U+202F — a narrow no-break space, invisible in a
#: terminal and fatal to a naive split. Pinning the locale makes the output the
#: same everywhere, and has the side effect of putting error messages in the
#: language every Gentoo bug report is written in.
PARSE_ENVIRONMENT = {"LC_ALL": "C.UTF-8"}


def _spec(
    arguments: Iterable[str], *, privileged: bool, description: str = ""
) -> CommandSpec:
    return CommandSpec(
        argv=(*_BASE, *arguments),
        privileged=privileged,
        description=description,
        environment=dict(PARSE_ENVIRONMENT),
    )


def pretend(atoms: Iterable[str], *, oneshot: bool = False) -> CommandSpec:
    """``emerge -pv`` — show what would happen. Needs no privileges at all."""
    atoms = tuple(atoms)
    return _spec(
        ("--pretend", "--verbose", *(("--oneshot",) if oneshot else ()), *atoms),
        privileged=False,
        description="pretend",
    )


def _binary(enabled: bool) -> tuple[str, ...]:
    """``--getbinpkg`` when the user asked for binaries.

    Only ever added to commands that install: a preview run must show what
    would happen with the option as it is set, and a sync has no use for it.
    """
    return ("--getbinpkg",) if enabled else ()


def install(
    atoms: Iterable[str], *, oneshot: bool = False, binaries: bool = False
) -> CommandSpec:
    """``emerge -v`` — build and merge.

    ``--oneshot`` is what "install this version without touching @world" means;
    without it the atom is added to ``@world`` and becomes something the system
    keeps up to date, which is a decision the user should make on purpose.
    """
    atoms = tuple(atoms)
    return _spec(
        ("--verbose", *_binary(binaries), *(("--oneshot",) if oneshot else ()), *atoms),
        privileged=True,
        description="install",
    )


#: The autounmask options the analysis carries, and the reason each is there.
#:
#: ``--autounmask`` is not redundant. Portage turns autounmask on by itself for
#: keywords, masks and USE, but ``--autounmask-license`` defaults to ``"n"``
#: unless ``--autounmask`` was asked for explicitly
#: (``_emerge/create_depgraph_params.py``: ``myopts.get("--autounmask-license",
#: "y" if autounmask is True else "n")``). So a preview without it can never
#: mention a licence, which is exactly the refusal a user cannot guess at.
#: ``--autounmask-license=y`` then says so a second time, in the command line
#: the window shows, rather than leaving it to be inferred.
#:
#: Three options are deliberately absent and must stay absent.
#: ``--autounmask-write`` and ``--autounmask-continue`` write to
#: ``/etc/portage`` themselves, and the one program here that writes there is
#: the helper, after the user has seen the lines. ``--ask`` waits for an answer
#: on a terminal this process does not have.
#:
#: ``--autounmask-backtrack=y`` is absent for a different reason: it is
#: disabled by default, ``man emerge`` warns that it can waste a great deal of
#: time with no guarantee of a solution, and the ordinary run already prints
#: everything the user is being asked to accept.
_AUTOUNMASK = ("--autounmask", "--autounmask-license=y")


def analyse(
    atoms: Iterable[str], *, oneshot: bool = False, binaries: bool = False
) -> CommandSpec:
    """``emerge -pv --autounmask`` — everything Portage wants changed, at once.

    The difference from :func:`pretend` is :data:`_AUTOUNMASK`, and the point of
    it is to collect in one run what the user would otherwise meet one refusal
    at a time: a keyword, then a mask, then a licence, then a USE flag.

    The options after that are the ones :func:`install` would carry for the same
    package, because a plan describing a different command from the one the
    button runs is worse than no plan.

    A run that finds something to change **exits non-zero**. That is the answer,
    not a failure: the block of lines it printed is the whole message.
    """
    atoms = tuple(atoms)
    return _spec(
        (
            "--pretend",
            "--verbose",
            *_AUTOUNMASK,
            *_binary(binaries),
            *(("--oneshot",) if oneshot else ()),
            *atoms,
        ),
        privileged=False,
        description="analyse",
    )


def unmerge_pretend(atoms: Iterable[str]) -> CommandSpec:
    """``emerge -pv --unmerge`` — the list that has to be shown before removing.

    Docs/04-privileges.md §6: nothing disappears until the user has seen
    exactly what would disappear.
    """
    return _spec(
        ("--pretend", "--verbose", "--unmerge", *atoms),
        privileged=False,
        description="unmerge pretend",
    )


def unmerge(atoms: Iterable[str]) -> CommandSpec:
    """``emerge --unmerge`` — remove packages that are already installed.

    Not ``--depclean``: this removes exactly what it is given and nothing else.
    Depclean, which decides for itself what is orphaned, belongs to the update
    screen where its list gets a confirmation of its own.
    """
    return _spec(("--unmerge", *atoms), privileged=True, description="unmerge")


def deselect(atoms: Iterable[str]) -> CommandSpec:
    """Take a package out of ``@world`` without uninstalling it."""
    return _spec(("--deselect", *atoms), privileged=True, description="deselect")


def select(atoms: Iterable[str]) -> CommandSpec:
    """Add an installed package to ``@world``."""
    return _spec(("--select", "--noreplace", *atoms), privileged=True, description="select")


def update_world_pretend(*, binaries: bool = False) -> CommandSpec:
    """The preview the system-update screen is built around (session S8).

    Takes the binary option too, so the table says which packages *would*
    arrive prebuilt rather than promising one thing and doing another.
    """
    return _spec(
        (
            "--pretend",
            "--verbose",
            "--update",
            "--deep",
            "--newuse",
            "--changed-use",
            *_binary(binaries),
            "@world",
        ),
        privileged=False,
        description="update pretend",
    )


def update_world(*, binaries: bool = False) -> CommandSpec:
    return _spec(
        ("--verbose", "--update", "--deep", "--newuse", *_binary(binaries), "@world"),
        privileged=True,
        description="update",
    )


def depclean_pretend() -> CommandSpec:
    """``emerge -p --depclean`` — what is no longer needed by anything.

    Always run and shown before the real thing. Depclean decides for itself
    what is orphaned, and it is the one Portage operation that routinely
    surprises people (Docs/04-privileges.md §6).
    """
    return _spec(("--pretend", "--depclean"), privileged=False, description="depclean pretend")


def depclean() -> CommandSpec:
    return _spec(("--depclean",), privileged=True, description="depclean")


def preserved_rebuild() -> CommandSpec:
    """Rebuild whatever still links against a library that just went away."""
    return _spec(("--verbose", "@preserved-rebuild"), privileged=True, description="rebuild")


def sync_all() -> CommandSpec:
    """``emaint sync -a`` — the recommended way to sync every repository."""
    return CommandSpec(
        argv=("emaint", "sync", "-a"), privileged=True, description="sync"
    )
