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

"""Reading ``emerge``'s own output back.

Everything Portage knows about a pending update is in the text ``emerge -pv``
prints, and there is no API for it. So this module reads that text — the same
text the user could run in a terminal — and turns it into rows a table can show.

The point is not to replace the output but to make it sortable and countable:
which packages, from which version to which, what changed about their USE flags,
how much has to be downloaded, and how much of it is a binary package rather
than a compile. The log panel still shows the original underneath, because
anything this parser does not understand has to remain visible.

The one thing that has to be arranged rather than parsed is the locale.
``emerge`` formats sizes with the thousands separator of whatever ``LC_NUMERIC``
is in force — on a Polish system that is U+202F, a narrow no-break space, which
is invisible and breaks any naive split. The commands run with ``LC_ALL=C.UTF-8``
so the output is predictable, and the parser tolerates the separators anyway.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum


class Action(StrEnum):
    """What ``emerge`` intends to do with a package."""

    NEW = "new"
    NEW_SLOT = "new-slot"
    UPDATE = "update"
    DOWNGRADE = "downgrade"
    REBUILD = "rebuild"
    UNINSTALL = "uninstall"
    BLOCKED = "blocked"
    #: Listed for context but not touched — ``--tree`` output and blockers.
    NOMERGE = "nomerge"


#: ``[ebuild  N     ] `` — the fixed-width block that opens every row.
#:
#: ``++`` rather than ``+``, and the extra character is the whole of the fix.
#: ``[^\]]`` is a superset of ``[a-z-]``, so on a line that opens a bracket and
#: never closes it the two quantifiers can divide the letters between them in as
#: many ways as there are letters, and the engine tries all of them before
#: giving up. Every line of ``emerge`` output goes through this, and an ebuild's
#: ``pkg_pretend()`` — which Portage runs during ``--pretend`` — can print
#: whatever it likes: 64k of lowercase after a ``[`` took six seconds.
#:
#: Possessive, so *kind* takes the whole run and never hands any of it back.
#: That is not a narrowing: greedy already took the longest run, and anything
#: the old pattern could match by backtracking, ``[^\]]*`` can match instead.
_ROW = re.compile(r"^\[(?P<kind>[a-z-]++)(?P<flags>[^\]]*)\]\s+(?P<rest>.*)$")

#: ``USE="a -b" PYTHON_TARGETS="python3_14"`` — one or more VAR="…" groups.
_VARIABLE = re.compile(r'(?P<name>[A-Z][A-Z0-9_]*)="(?P<value>[^"]*)"')

#: The characters a size may be written with, separators included.
#:
#: This used to be half of a regular expression — a lazy run of digits and
#: separators beside a ``\s*`` that matches the same spaces — and the overlap
#: made it cubic: the lazy run expands, the ``\s*`` divides the spaces with it,
#: and ``search`` starts the whole thing again at every position in the string.
#: A thousand characters took more than six seconds, and a merge row with no
#: quotation mark in it hands this function its entire tail.
#:
#: A backwards walk instead. It is longer to read and it cannot backtrack,
#: which for a string that arrives from an ebuild is the trade worth making.
#:
#: The bare ``B`` is spelled out because _UNITS has an entry for it: emerge
#: prints KiB and up in practice, but a list that cannot name a unit the table
#: beside it claims to understand is a trap for whoever reads the two together.
_SIZE_CHARACTERS = frozenset("0123456789,.\xa0\u202f ")

#: Longest first, so that ``KiB`` is found before the ``B`` inside it.
_SIZE_UNITS = ("TiB", "GiB", "MiB", "KiB", "B")

#: ``[1.0]`` — the version being replaced.
_OLD_VERSION = re.compile(r"\[([^\]]+)\]")

#: ``Total: 8 packages (8 new, 2 upgrades), Size of downloads: 14164 KiB``
_TOTAL = re.compile(r"^Total:\s+(?P<count>\d+)\s+package")

_UNITS = {"B": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3, "TiB": 1024**4}

#: Blocks emerge prints when it wants /etc/portage changed before it will go on.
_CHANGE_HEADINGS = (
    "The following USE changes are necessary to proceed",
    "The following keyword changes are necessary to proceed",
    "The following mask changes are necessary to proceed",
    "The following license changes are necessary to proceed",
)

#: Printed nowhere else than inside the "has unmet requirements" refusal
#: (``_emerge/depgraph.py``: ``_show_unsatisfied_dep``), so it is part of that
#: message rather than a block of its own — but it is still listed among the
#: headings, because it ends whatever block came before it just as they do.
_REQUIRED_USE_HEADING = "The following REQUIRED_USE flag constraints are unsatisfied"

_REQUIRED_CHANGE_HEADINGS = (*_CHANGE_HEADINGS, _REQUIRED_USE_HEADING)

#: The ways ``emerge`` says it cannot satisfy a dependency at all.
#:
#: Four branches of a single ``if`` in one function — ``_emerge/depgraph.py``:
#: ``_show_unsatisfied_dep`` — and five sentences, because the last branch has a
#: second wording for ``--usepkgonly``. They are kept together here for the same
#: reason they are together there: a reader checking three of them against
#: Portage has no way to tell that they missed one.
#:
#: They are what a refusal *looks like* when autounmask has already been asked
#: and has nothing to offer. The consequence matters more than the wording: a
#: run carrying one of these printed no lines to write and no blocker row, so
#: everything else about it reads exactly like a run with nothing to do.
_REFUSAL_BANNERS = (
    # REQUIRED_USE: the package's own flags contradict each other.
    "The ebuild selected to satisfy ",
    # A USE dependency no candidate can meet — a flag that was renamed or
    # removed, most often in an ebuild from an overlay.
    "there are no ebuilds built with USE flags to satisfy ",
    # Masked, and in a way ``--autounmask`` will not lift.
    "All ebuilds that could satisfy ",
    # Nothing anywhere provides the atom: the usual reading is a repository
    # that is not enabled on this system.
    "there are no ebuilds to satisfy ",
    "there are no binary packages to satisfy ",
)

#: ``The following USE changes are …`` — the word that says which file.
_CHANGE_KIND = re.compile(r"^The following (?P<kind>\S+) changes are necessary")

#: Where each kind of change is written. Keyed by emerge's own word for it.
_REQUIRED_CHANGE_FILES = {
    "USE": "package.use",
    "keyword": "package.accept_keywords",
    "mask": "package.unmask",
    "license": "package.license",
}


@dataclass(frozen=True, slots=True)
class UseChange:
    """One flag as ``emerge -pv`` reports it."""

    flag: str
    enabled: bool
    #: ``*`` — differs from how the package is currently built.
    changed: bool = False
    #: ``%`` — the flag did not exist in the installed version.
    added: bool = False
    #: ``(…)`` — forced or masked, so not the user's to change.
    forced: bool = False

    @property
    def display(self) -> str:
        text = self.flag if self.enabled else f"-{self.flag}"
        return f"({text})" if self.forced else text

    @property
    def is_interesting(self) -> bool:
        """Worth putting in a narrow column: only what actually changed."""
        return self.changed or self.added


@dataclass(frozen=True, slots=True)
class MergeRow:
    """One line of the merge list."""

    action: Action
    kind: str
    flags: str
    cpv: str
    cp: str
    version: str
    slot: str = ""
    repo: str = ""
    old_version: str = ""
    use: tuple[UseChange, ...] = ()
    variables: dict[str, str] = field(default_factory=dict)
    size: int | None = None
    note: str = ""
    raw: str = ""

    @property
    def is_binary(self) -> bool:
        """Coming from a binary package rather than being compiled."""
        return self.kind == "binary"

    @property
    def is_satisfied_block(self) -> bool:
        """``[blocks b ]`` rather than ``[blocks B ]``.

        Portage writes the letter in lower case when it worked the block out for
        itself and in upper case when it could not
        (``_emerge/resolver/output.py``: ``if blocker.satisfied``). Both rows
        look alike at a glance and mean opposite things — one is a note about a
        conflict that has been handled, the other is the reason nothing can be
        installed — so the difference is one letter and worth a name.
        """
        return self.action is Action.BLOCKED and "b" in self.flags

    @property
    def changed_use(self) -> tuple[UseChange, ...]:
        return tuple(item for item in self.use if item.is_interesting)

    @property
    def version_change(self) -> str:
        """``1.0 → 2.0`` for an update, just the version otherwise."""
        if self.old_version and self.old_version != self.version:
            return f"{self.old_version} → {self.version}"
        return self.version


@dataclass(frozen=True, slots=True)
class RequiredEntry:
    """One line emerge is asking for, in the shape a writer can use."""

    #: The file under ``/etc/portage`` it belongs in.
    file: str
    atom: str
    tokens: tuple[str, ...] = ()
    #: The ``# required by`` lines emerge printed above it, markers stripped.
    #: This is the "why", and it is the half that says whose fault it is —
    #: often a dependency the user has never heard of.
    required_by: tuple[str, ...] = ()

    @property
    def line(self) -> str:
        return " ".join([self.atom, *self.tokens])


@dataclass(frozen=True, slots=True)
class RequiredChange:
    """A block of ``/etc/portage`` changes emerge is asking for."""

    heading: str
    lines: tuple[str, ...]

    @property
    def file(self) -> str:
        """The file this block wants a line in, or ``""`` when there is none.

        REQUIRED_USE constraints land here too and deliberately get nothing:
        they are not a configuration change but the package's own flags
        contradicting each other, and no line in ``/etc/portage`` settles that.
        """
        match = _CHANGE_KIND.match(self.heading)
        return _REQUIRED_CHANGE_FILES.get(match.group("kind"), "") if match else ""

    @property
    def entries(self) -> tuple[RequiredEntry, ...]:
        """The lines themselves, each carrying the comments printed above it."""
        target = self.file
        if not target:
            return ()
        found: list[RequiredEntry] = []
        context: list[str] = []
        for raw in self.lines:
            line = raw.strip()
            # The "(see ... in the portage(5) man page)" pointer is emerge
            # talking to the reader, not a line to write anywhere.
            if not line or line.startswith("("):
                continue
            if line.startswith("#"):
                context.append(line.lstrip("#").strip())
                continue
            atom, *tokens = line.split()
            found.append(RequiredEntry(target, atom, tuple(tokens), tuple(context)))
            context = []
        return tuple(found)


@dataclass(frozen=True, slots=True)
class Refusal:
    """One dependency ``emerge`` said it could not satisfy, in its own words.

    Kept whole and unparsed on purpose. What Portage prints under the banner is
    the only explanation there is — which versions it looked at, which flag each
    one is missing, who asked for the dependency — and none of it fits a field.
    """

    #: The sentence that opens the message, stripped of leading whitespace.
    banner: str
    #: Everything printed under it, up to whatever came next. Verbatim.
    lines: tuple[str, ...] = ()

    @property
    def text(self) -> tuple[str, ...]:
        return (self.banner, *self.lines)


@dataclass(frozen=True, slots=True)
class Preview:
    """Everything ``emerge -pv`` said, in a shape a table can use."""

    rows: tuple[MergeRow, ...] = ()
    total: int | None = None
    download_size: int | None = None
    required_changes: tuple[RequiredChange, ...] = ()
    #: Lines beginning with ``!!!`` — conflicts, mostly.
    problems: tuple[str, ...] = ()
    #: Dependencies emerge refused outright. See :data:`_REFUSAL_BANNERS`.
    refusals: tuple[Refusal, ...] = ()
    raw: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.merges

    @property
    def merges(self) -> tuple[MergeRow, ...]:
        """Rows that represent actual work."""
        return tuple(
            row
            for row in self.rows
            if row.action not in (Action.NOMERGE, Action.BLOCKED)
        )

    @property
    def blockers(self) -> tuple[MergeRow, ...]:
        return tuple(row for row in self.rows if row.action is Action.BLOCKED)

    @property
    def unsatisfied_blockers(self) -> tuple[MergeRow, ...]:
        """The blockers that are actually in the way.

        A run can list a block and still be perfectly installable — Portage says
        so itself, in the summary line: ``Conflict: 1 block (all satisfied)``.
        Anything deciding whether the graph resolved has to ask for these rather
        than for :attr:`blockers`, or it calls a working plan a conflict.
        """
        return tuple(row for row in self.blockers if not row.is_satisfied_block)

    @property
    def binary_count(self) -> int:
        return sum(1 for row in self.merges if row.is_binary)

    def count(self, action: Action) -> int:
        return sum(1 for row in self.merges if row.action is action)

    @property
    def needs_configuration(self) -> bool:
        """Emerge will not proceed until ``/etc/portage`` is changed."""
        return bool(self.required_changes)


# ---------------------------------------------------------------------------
# the pieces
# ---------------------------------------------------------------------------


def parse_size(text: str) -> int | None:
    """``1 445 KiB`` → bytes. Tolerates every thousands separator seen in the wild.

    Written as a scan rather than as a pattern — see :data:`_SIZE_CHARACTERS`.
    The unit is a suffix, so it is found by asking whether the text ends with
    one; the number is the run of digits and separators in front of it, so it is
    found by walking back until something else turns up. Both are one pass, and
    neither can be made to reconsider.
    """
    text = text.strip()
    for unit in _SIZE_UNITS:
        if text.endswith(unit):
            break
    else:
        return None

    head = text[: len(text) - len(unit)]
    cut = len(head)
    while cut and head[cut - 1] in _SIZE_CHARACTERS:
        cut -= 1
    if cut == len(head):
        return None

    digits = re.sub(r"[\xa0\u202f ,]", "", head[cut:])
    try:
        value = float(digits)
    except ValueError:
        return None
    return int(value * _UNITS.get(unit, 1))


def parse_use(value: str) -> tuple[UseChange, ...]:
    """``X* -foo% (-bar)`` → structured flags.

    ``*`` means the flag differs from the installed build, ``%`` that it is new
    in this version, and brackets that the profile decides it rather than the
    user. Those three marks are the whole reason ``--changed-use`` output is
    worth reading rather than glancing at.
    """
    changes = []
    for token in value.split():
        text = token
        forced = text.startswith("(") and text.endswith(")")
        if forced:
            text = text[1:-1]
        changed = added = False
        while text and text[-1] in "*%":
            if text[-1] == "*":
                changed = True
            else:
                added = True
            text = text[:-1]
        if not text:
            continue
        enabled = not text.startswith("-")
        changes.append(
            UseChange(
                flag=text.lstrip("-"),
                enabled=enabled,
                changed=changed,
                added=added,
                forced=forced,
            )
        )
    return tuple(changes)


def _action_of(kind: str, flags: str) -> Action:
    if kind == "blocks":
        return Action.BLOCKED
    if kind == "uninstall":
        return Action.UNINSTALL
    if kind == "nomerge":
        return Action.NOMERGE
    letters = set(flags)
    # D before U, and that order is the whole point: emerge marks a downgrade
    # with *both* letters — `[ebuild     UD ]` — so checking U first reports
    # every downgrade as an upgrade, which is the one direction nobody wants to
    # be surprised by.
    if "D" in letters:
        return Action.DOWNGRADE
    if "U" in letters:
        return Action.UPDATE
    if "S" in letters:
        return Action.NEW_SLOT
    if "R" in letters:
        return Action.REBUILD
    if "N" in letters:
        return Action.NEW
    return Action.REBUILD


def _split_atom(atom: str) -> tuple[str, str, str]:
    """``cat/pkg-1.2:0/2::gentoo`` → cpv, slot, repo."""
    rest, _, repo = atom.partition("::")
    cpv, _, slot = rest.partition(":")
    return cpv, slot, repo


def _cp_and_version(cpv: str) -> tuple[str, str]:
    from portage.versions import catpkgsplit  # noqa: PLC0415 — slow import

    # Blocker rows carry a range operator (`<sys-apps/portage-3.0.9`) that
    # catpkgsplit will not touch; the atom still has to display as a name.
    parts = catpkgsplit(cpv.lstrip("<>=!~"))
    if parts is None:
        return cpv, ""
    category, name, version, revision = parts
    full = version if revision == "r0" else f"{version}-{revision}"
    return f"{category}/{name}", full


def parse_row(line: str) -> MergeRow | None:
    """Parse one ``[ebuild …]`` line, or return ``None`` if it is not one."""
    match = _ROW.match(line)
    if match is None:
        return None

    kind = match.group("kind")
    flags = match.group("flags").strip()
    rest = match.group("rest")

    note = ""
    if "(" in rest and kind == "blocks":
        atom, _, tail = rest.partition("(")
        note = tail.rstrip().rstrip(")")
        rest = atom.strip()

    atom, _, tail = rest.partition(" ")
    cpv, slot, repo = _split_atom(atom)
    cp, version = _cp_and_version(cpv)

    old_version = ""
    variables: dict[str, str] = {}
    size = None
    if tail:
        # The replaced version comes before the variables and is the only thing
        # in square brackets, so it is safe to look for it first.
        bracket = _OLD_VERSION.search(tail.split('"')[0])
        if bracket:
            old_version = _split_atom(bracket.group(1))[0]
        variables = {
            found.group("name"): found.group("value")
            for found in _VARIABLE.finditer(tail)
        }
        size = parse_size(tail.rsplit('"', 1)[-1])

    return MergeRow(
        action=_action_of(kind, flags),
        kind=kind,
        flags=flags,
        cpv=cpv,
        cp=cp,
        version=version,
        slot=slot,
        repo=repo,
        old_version=old_version,
        use=parse_use(variables.get("USE", "")),
        variables=variables,
        size=size,
        note=note.strip(),
        raw=line.rstrip(),
    )


def _is_refusal(stripped: str) -> bool:
    """Whether *stripped* opens one of emerge's "I cannot" messages.

    Anchored on the prefix as well as the sentence. Portage writes these with
    ``writemsg``, so they arrive on stderr and can turn up interleaved anywhere
    in a merged log; what does not vary is that the line is either an ``!!!``
    remark or an ``emerge:`` one.
    """
    if not (stripped.startswith("!!!") or stripped.startswith("emerge:")):
        return False
    return any(banner in stripped for banner in _REFUSAL_BANNERS)


def parse_pretend(text: str) -> Preview:
    """Read the whole of an ``emerge -pv`` run."""
    rows: list[MergeRow] = []
    problems: list[str] = []
    required: list[RequiredChange] = []
    refusals: list[Refusal] = []
    total = download = None

    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        row = parse_row(line)
        if row is not None:
            rows.append(row)
            index += 1
            continue

        # Before the ``!!!`` branch: two of the four refusals are ``!!!`` lines,
        # and filing them as one more problem would throw away the explanation
        # printed underneath — which, for a refusal, is the entire message.
        if _is_refusal(stripped):
            block, index = _collect_refusal(lines, index + 1)
            refusals.append(Refusal(banner=stripped, lines=block))
            continue

        if stripped.startswith("!!!"):
            problems.append(stripped)
            index += 1
            continue

        heading = next(
            (h for h in _REQUIRED_CHANGE_HEADINGS if stripped.startswith(h)), None
        )
        if heading is not None:
            block, index = _collect_block(lines, index + 1)
            required.append(RequiredChange(heading=stripped, lines=block))
            continue

        match = _TOTAL.match(stripped)
        if match:
            total = int(match.group("count"))
            _, _, size_part = stripped.partition("Size of downloads:")
            download = parse_size(size_part) if size_part else None

        index += 1

    return Preview(
        rows=tuple(rows),
        total=total,
        download_size=download,
        required_changes=tuple(required),
        problems=tuple(problems),
        refusals=tuple(refusals),
        raw=text,
    )


def _collect_block(lines: list[str], start: int) -> tuple[tuple[str, ...], int]:
    """The lines under a heading, up to the blank line that closes the block.

    Where the block ends is decided by the blank line emerge puts after it and
    by the things that can only be the start of something else — never by what
    the line's first character looks like. The entries in these blocks are
    atoms, and an atom starts with whatever its operator happens to be:
    ``>=cat/pkg-1``, ``=cat/pkg-1``, ``<cat/pkg-2``, or a bare ``cat/pkg``. A
    rule written in terms of the first character kept the ``>=`` lines and
    dropped every other one — which is to say, it dropped the licence and
    keyword lines, the two the user is most often asked to write.
    """
    collected = []
    index = start
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            if collected:
                break
            index += 1
            continue
        starts_something_else = (
            parse_row(line) is not None
            or stripped.startswith("!!!")
            or _is_refusal(stripped)
            or _TOTAL.match(stripped)
            or any(stripped.startswith(h) for h in _REQUIRED_CHANGE_HEADINGS)
        )
        if starts_something_else:
            break
        collected.append(line.rstrip())
        index += 1
    return tuple(collected), index


def _collect_refusal(lines: list[str], start: int) -> tuple[tuple[str, ...], int]:
    """Everything printed under a refusal banner, kept as it was printed.

    A wider net than :func:`_collect_block`, and it has to be. The blocks that
    function reads are lists of atoms closed by the first blank line; a refusal
    is prose with blank lines *inside* it — the REQUIRED_USE message alone puts
    two of them between the package, the constraint it broke and the expression
    that constraint came from. So the end is decided by what starts next
    instead: another refusal, a merge row, a totals line, or a block of changes
    to write. A second blank line in a row ends it too, since by then emerge has
    stopped talking about this dependency.

    ``The following REQUIRED_USE flag constraints are unsatisfied`` is
    deliberately not one of the boundaries. Portage prints that heading in one
    place only, inside this message, and stopping at it would drop the one line
    that says *which* constraint was broken.
    """
    collected: list[str] = []
    index = start
    blanks = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            blanks += 1
            if blanks > 1:
                break
            collected.append("")
            index += 1
            continue
        blanks = 0

        starts_something_else = (
            parse_row(line) is not None
            or _is_refusal(stripped)
            or _TOTAL.match(stripped)
            or any(stripped.startswith(h) for h in _CHANGE_HEADINGS)
        )
        if starts_something_else:
            break
        collected.append(line.rstrip())
        index += 1

    while collected and not collected[-1]:
        collected.pop()
    return tuple(collected), index


# ---------------------------------------------------------------------------
# depclean
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Depclean:
    """What ``emerge -p --depclean`` proposes to remove."""

    atoms: tuple[str, ...] = ()
    installed: int | None = None
    required: int | None = None
    to_remove: int | None = None
    raw: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.atoms


_ALL_SELECTED = re.compile(r"^All selected packages:\s*(?P<atoms>.*)$")
_COUNT = re.compile(r"^(?P<label>[A-Za-z ]+):\s+(?P<value>\d+)\s*$")

_COUNT_FIELDS = {
    "Packages installed": "installed",
    "Required packages": "required",
    "Number to remove": "to_remove",
}


def parse_depclean(text: str) -> Depclean:
    """Read ``emerge -p --depclean``.

    The list is taken from the ``All selected packages:`` line rather than from
    the per-package blocks above it: that line is the authoritative set, and the
    blocks are the explanation of how each entry got there.
    """
    atoms: tuple[str, ...] = ()
    counts: dict[str, int] = {}

    for line in text.splitlines():
        stripped = line.strip()
        match = _ALL_SELECTED.match(stripped)
        if match:
            atoms = tuple(match.group("atoms").split())
            continue
        count = _COUNT.match(stripped)
        if count:
            field_name = _COUNT_FIELDS.get(count.group("label").strip())
            if field_name:
                counts[field_name] = int(count.group("value"))

    return Depclean(atoms=atoms, raw=text, **counts)


# ---------------------------------------------------------------------------
# failures
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Failure:
    """What went wrong, and where to read more."""

    #: The package that failed, when emerge named one.
    package: str = ""
    #: The build log emerge pointed at.
    log_path: str = ""
    #: The most useful lines of output, in order.
    excerpt: tuple[str, ...] = ()
    #: Key the interface turns into a suggestion; empty when there is none.
    hint: str = ""


_FAILED_PACKAGE = re.compile(r"^\s*\*?\s*ERROR:\s+(?P<cpv>\S+?)(?:::\S+)?\s+failed")
_LOG_PATH = re.compile(r"(/var/tmp/portage/\S+/temp/build\.log|/var/log/portage/\S+\.log)")

#: Ordered: the first pattern that matches decides the suggestion, so the more
#: specific situations come before the general ones.
_HINTS = (
    ("blocked", re.compile(r"\[blocks [Bb]", re.MULTILINE)),
    ("slot-conflict", re.compile(r"Multiple package instances within a single package slot")),
    ("use-change", re.compile(r"The following USE changes are necessary")),
    ("keyword-change", re.compile(r"The following keyword changes are necessary")),
    ("mask-change", re.compile(r"The following mask changes are necessary")),
    ("licence-change", re.compile(r"The following license changes are necessary")),
    ("required-use", re.compile(r"REQUIRED_USE flag constraints are unsatisfied")),
    ("missing-dependency", re.compile(r"emerge: there are no ebuilds to satisfy")),
    ("out-of-space", re.compile(r"No space left on device")),
)

#: How many lines around the error to keep.
_EXCERPT_LINES = 40


def find_failure(text: str) -> Failure | None:
    """Pick the useful parts out of a failed run.

    A failed ``emerge`` prints hundreds of lines and the answer is in about six
    of them. This finds the package, the build log and the last stretch of
    output before things stopped, and matches the whole against a handful of
    situations common enough to be worth a sentence of advice.
    """
    lines = text.splitlines()
    hint = next((name for name, pattern in _HINTS if pattern.search(text)), "")

    package = ""
    error_at = None
    for index, line in enumerate(lines):
        match = _FAILED_PACKAGE.match(line)
        if match:
            package = match.group("cpv")
            error_at = index
            break

    log_match = _LOG_PATH.search(text)
    log_path = log_match.group(1) if log_match else ""

    if error_at is None and not hint and not log_path:
        return None

    if error_at is not None:
        start = max(0, error_at - 5)
        excerpt = lines[start: error_at + _EXCERPT_LINES]
    else:
        # No ERROR line: a refusal rather than a build failure. The tail is
        # where emerge explains itself.
        excerpt = lines[-_EXCERPT_LINES:]

    return Failure(
        package=package,
        log_path=log_path,
        excerpt=tuple(line.rstrip() for line in excerpt if line.strip()),
        hint=hint,
    )
