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

"""One run of ``emerge --autounmask``, arranged as a single set of decisions.

:mod:`gentstore.core.emerge_parse` already turns the output into blocks and
lines. What is missing between that and a screen is the part a person needs to
answer *once*: how many changes are there really, which file does each belong
in, who asked for it, and which of them are not the routine ones.

So this module regroups the same lines — it invents nothing, and above all it
does not decide anything Portage has not already decided. The lines are carried
through byte for byte, because they are Portage's proposal and rewriting them
would make the preview a description of something else.

Three things it does add, all of them counting rather than reasoning.

**Deduplication.** The same line can be printed under several ``# required by``
chains. It is one line in one file, so it becomes one entry carrying every
reason.

**Marking what is not routine.** A ``~amd64`` keyword is ordinary Gentoo. A
``**`` keyword means nobody has tested that package on this architecture at all,
and a ``9999`` atom is a live ebuild that builds whatever upstream pushed this
morning. Both are decisions of a different size, and a count of "8 keywords"
that quietly includes them is the kind of summary this project exists not to
write.

**Saying when the answer is provisional.** Portage stops backtracking as soon as
autounmask finds something, and says so::

    In order to avoid wasting time, backtracking has terminated early
    due to the above autounmask change(s).

A conflict reported next to a block of required changes is therefore not a
verdict — it is what the graph looked like before the changes were applied. That
distinction decides whether the screen offers to write anything, and getting it
backwards would refuse to help with precisely the case the feature exists for:
an overlay package whose whole dependency chain still needs keywording.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .emerge_parse import Action, Preview, RequiredEntry

#: The files a plan can ask for, in the order the screen shows them.
#:
#: Keyword first because it is the commonest and the mildest, unmask last
#: because it is the one somebody decided against on purpose. The privileged
#: helper has the same four names and checks them itself; this order is
#: presentation, that list is a boundary.
FILE_ORDER = (
    "package.accept_keywords",
    "package.license",
    "package.use",
    "package.unmask",
)

#: ``**`` — accept the package on an architecture nobody has keyworded it for.
UNKEYWORDED_TOKEN = "**"

#: ``-9999``, ``-99999999`` and the rest of the live-ebuild convention.
_LIVE_VERSION = re.compile(r"-9{4,}(?:-r\d+)?$")

#: Portage's own words for "I stopped early, so this may not be the whole
#: picture". Matched on the distinctive half of the sentence, because the line
#: is wrapped and prefixed with the ``*`` that emerge puts on its own remarks.
_TERMINATED_EARLY = "backtracking has terminated early"

#: ``required by gui-wm/hyprland-0.56.2::hyproverlay`` → the package alone.
_REQUIRED_BY = re.compile(r"^required by\s+(?P<who>.+)$")


@dataclass(frozen=True, slots=True)
class PlannedEntry:
    """One line for ``/etc/portage``, with everything needed to decide on it."""

    #: The line exactly as emerge proposed it. Never rebuilt from its parts.
    entry: RequiredEntry
    #: Who asked, nearest first, deduplicated across repeated blocks.
    reasons: tuple[str, ...] = ()

    @property
    def file(self) -> str:
        return self.entry.file

    @property
    def atom(self) -> str:
        return self.entry.atom

    @property
    def line(self) -> str:
        return self.entry.line

    @property
    def tokens(self) -> tuple[str, ...]:
        """What follows the atom — ``~amd64``, a licence name, USE flags."""
        return self.entry.tokens

    @property
    def repo(self) -> str:
        """The ``::repo`` the atom names, when it names one.

        Autounmask usually does not qualify its atoms, so this is empty more
        often than not; the merge list is where the repository of each package
        actually shows up.
        """
        return self.entry.atom.partition("::")[2]

    @property
    def is_unkeyworded(self) -> bool:
        """``**`` — not "untested on amd64" but "untested anywhere"."""
        return UNKEYWORDED_TOKEN in self.entry.tokens

    @property
    def is_live(self) -> bool:
        """A ``9999`` ebuild: whatever upstream's branch holds right now."""
        return bool(_LIVE_VERSION.search(self.entry.atom.partition("::")[0]))

    @property
    def is_ordinary(self) -> bool:
        """Neither of the two that deserve saying out loud."""
        return not (self.is_unkeyworded or self.is_live)


@dataclass(frozen=True, slots=True)
class PlanGroup:
    """Every entry that belongs in one file under ``/etc/portage``."""

    file: str
    entries: tuple[PlannedEntry, ...] = ()

    def __len__(self) -> int:
        return len(self.entries)

    @property
    def is_unmask(self) -> bool:
        """``package.unmask`` — the one group that undoes somebody's decision.

        A keyword says "not declared stable yet"; a mask says "a developer
        wrote down that this version should not be installed". The screen grades
        its wording off this, the same way
        :mod:`gentstore.ui.widgets.block_notice` does for a single package.
        """
        return self.file == "package.unmask"



@dataclass(frozen=True, slots=True)
class InstallPlan:
    """What one ``emerge --autounmask`` run says has to happen first."""

    groups: tuple[PlanGroup, ...] = ()
    #: Portage's own text for anything it could not resolve, verbatim and
    #: unparsed. Slot conflicts and blockers land here and are deliberately not
    #: taken apart: the project's rule is that what the parser does not
    #: understand stays visible rather than being summarised badly.
    conflicts: tuple[str, ...] = ()
    #: Portage said it stopped backtracking because autounmask found something.
    stopped_early: bool = False
    #: Nothing recognisable came back at all — an empty log, a crash, output in
    #: a shape this parser has never seen. Distinct from "nothing to do", and
    #: the distinction is the whole point: a check that failed must never be
    #: mistaken for a check that passed.
    unreadable: bool = False
    #: Counts off the merge list, for the one-line summary.
    new: int = 0
    updates: int = 0
    rebuilds: int = 0
    downgrades: int = 0
    removals: int = 0

    # -- what the screen asks it -------------------------------------------

    @property
    def entries(self) -> tuple[PlannedEntry, ...]:
        return tuple(entry for group in self.groups for entry in group.entries)

    def __len__(self) -> int:
        return len(self.entries)

    @property
    def can_apply(self) -> bool:
        """Whether there is anything to offer to write.

        Deliberately not "and there are no conflicts". Portage reports a
        conflict alongside required changes because it gave up backtracking the
        moment autounmask had something to say, and the changes are the way
        forward — refusing to offer them here would leave the user exactly where
        they started, retyping keywords one at a time.
        """
        return bool(self.groups)

    @property
    def is_ready(self) -> bool:
        """Portage can build this as the system stands. The install gate.

        Everything has to be true at once: something was understood, nothing is
        waiting to be written, and nothing conflicts. Anything less keeps the
        gate shut, including the case where the answer could not be read.
        """
        return not self.unreadable and not self.groups and not self.conflicts

    @property
    def is_provisional(self) -> bool:
        """There are changes, a conflict, and Portage's word that it gave up early.

        All three, because the middle one alone does not license the claim. A
        conflict reported by a run that resolved the graph properly is a
        conflict; one reported by a run that stopped the moment autounmask had
        something to say was worked out before these lines existed. Portage
        distinguishes the two itself, in as many words, and that sentence is
        what :attr:`stopped_early` records — so the screen says "this may not
        survive" only where Portage has said it might not.
        """
        return bool(self.groups) and bool(self.conflicts) and self.stopped_early

    @property
    def notable(self) -> tuple[PlannedEntry, ...]:
        return tuple(entry for entry in self.entries if not entry.is_ordinary)

    def group(self, file: str) -> PlanGroup | None:
        return next((group for group in self.groups if group.file == file), None)


# ---------------------------------------------------------------------------
# building it
# ---------------------------------------------------------------------------


def _reason(raw: str) -> str:
    """``required by cat/pkg-1.2::repo`` → ``cat/pkg-1.2::repo``.

    The ``(argument)`` marker at the end of a chain is emerge telling itself
    that this one came from the command line. It means nothing to somebody
    reading a window, so it goes; the package name it is attached to stays,
    because that is the thing the user actually typed.
    """
    match = _REQUIRED_BY.match(raw.strip())
    who = match.group("who") if match else raw.strip()
    return who.replace("(argument)", "").strip()


def _reasons(entry: RequiredEntry) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for raw in entry.required_by:
        cleaned = _reason(raw)
        if cleaned:
            seen.setdefault(cleaned, None)
    return tuple(seen)


def _merge(entries: list[RequiredEntry]) -> list[PlannedEntry]:
    """One :class:`PlannedEntry` per distinct line, reasons unioned.

    Keyed on the whole line rather than on the atom: ``=cat/pkg-1 ~amd64`` and
    ``=cat/pkg-1 **`` are two different requests about one package and must not
    collapse into each other.
    """
    order: list[str] = []
    lines: dict[str, RequiredEntry] = {}
    reasons: dict[str, dict[str, None]] = {}

    for entry in entries:
        key = f"{entry.file}\0{entry.line}"
        if key not in lines:
            order.append(key)
            lines[key] = entry
            reasons[key] = {}
        for reason in _reasons(entry):
            reasons[key].setdefault(reason, None)

    return [PlannedEntry(entry=lines[key], reasons=tuple(reasons[key])) for key in order]


def _conflicts(preview: Preview) -> tuple[str, ...]:
    """Portage's unresolved-graph output, in its own words.

    Two sources, because Portage uses two shapes for the same news: the ``!!!``
    lines it prints for a slot conflict, and the ``[blocks B ]`` row it puts in
    the merge list for a blocker. A run can carry either, or both.
    """
    found: list[str] = list(preview.problems)
    for row in preview.blockers:
        line = row.raw.strip()
        if line:
            found.append(line)
    return tuple(found)


def _is_unreadable(preview: Preview) -> bool:
    """Whether anything at all was understood.

    A parse that found no merge rows, no totals, no required changes and no
    problems has not established that there is nothing to do — it has
    established nothing. The one outcome that must never follow from it is an
    open install gate.
    """
    return not (
        preview.rows
        or preview.required_changes
        or preview.problems
        or preview.total is not None
    )


def from_preview(preview: Preview) -> InstallPlan:
    """Regroup one parsed ``emerge --autounmask`` run into a single plan."""
    by_file: dict[str, list[RequiredEntry]] = {}
    for change in preview.required_changes:
        for entry in change.entries:
            by_file.setdefault(entry.file, []).append(entry)

    # FILE_ORDER first, then anything the parser learns about later — so a new
    # kind of block shows up on screen rather than being silently dropped.
    names = [name for name in FILE_ORDER if name in by_file]
    names += [name for name in by_file if name not in FILE_ORDER]

    groups = tuple(
        PlanGroup(file=name, entries=tuple(_merge(by_file[name]))) for name in names
    )

    return InstallPlan(
        groups=groups,
        conflicts=_conflicts(preview),
        stopped_early=_TERMINATED_EARLY in preview.raw,
        unreadable=_is_unreadable(preview),
        new=preview.count(Action.NEW) + preview.count(Action.NEW_SLOT),
        updates=preview.count(Action.UPDATE),
        rebuilds=preview.count(Action.REBUILD),
        downgrades=preview.count(Action.DOWNGRADE),
        removals=preview.count(Action.UNINSTALL),
    )


def from_output(text: str) -> InstallPlan:
    """Read an ``emerge --autounmask`` run straight from its output."""
    from .emerge_parse import parse_pretend  # noqa: PLC0415 — one import, one place

    return from_preview(parse_pretend(text))
