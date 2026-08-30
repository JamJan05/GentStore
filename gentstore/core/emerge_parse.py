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
_ROW = re.compile(r"^\[(?P<kind>[a-z-]+)(?P<flags>[^\]]*)\]\s+(?P<rest>.*)$")

#: ``USE="a -b" PYTHON_TARGETS="python3_14"`` — one or more VAR="…" groups.
_VARIABLE = re.compile(r'(?P<name>[A-Z][A-Z0-9_]*)="(?P<value>[^"]*)"')

#: ``1445 KiB`` at the end of a row, with any of the separators a locale may use.
_SIZE = re.compile(r"(?P<number>[\d   ,.]+?)\s*(?P<unit>[KMGT]?iB)\s*$")

#: ``[1.0]`` — the version being replaced.
_OLD_VERSION = re.compile(r"\[([^\]]+)\]")

#: ``Total: 8 packages (8 new, 2 upgrades), Size of downloads: 14164 KiB``
_TOTAL = re.compile(r"^Total:\s+(?P<count>\d+)\s+package")

_UNITS = {"B": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3, "TiB": 1024**4}

#: Blocks emerge prints when it wants /etc/portage changed before it will go on.
_REQUIRED_CHANGE_HEADINGS = (
    "The following USE changes are necessary to proceed",
    "The following keyword changes are necessary to proceed",
    "The following mask changes are necessary to proceed",
    "The following license changes are necessary to proceed",
    "The following REQUIRED_USE flag constraints are unsatisfied",
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
class Preview:
    """Everything ``emerge -pv`` said, in a shape a table can use."""

    rows: tuple[MergeRow, ...] = ()
    total: int | None = None
    download_size: int | None = None
    required_changes: tuple[RequiredChange, ...] = ()
    #: Lines beginning with ``!!!`` — conflicts, mostly.
    problems: tuple[str, ...] = ()
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
    """``1 445 KiB`` → bytes. Tolerates every thousands separator seen in the wild."""
    match = _SIZE.search(text.strip())
    if match is None:
        return None
    digits = re.sub(r"[   ,]", "", match.group("number"))
    try:
        value = float(digits)
    except ValueError:
        return None
    return int(value * _UNITS.get(match.group("unit"), 1))


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


def parse_pretend(text: str) -> Preview:
    """Read the whole of an ``emerge -pv`` run."""
    rows: list[MergeRow] = []
    problems: list[str] = []
    required: list[RequiredChange] = []
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
        raw=text,
    )


def _collect_block(lines: list[str], start: int) -> tuple[tuple[str, ...], int]:
    """The indented lines under a heading, up to the next blank-separated block."""
    collected = []
    index = start
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            if collected:
                break
            index += 1
            continue
        if not line.startswith((" ", "\t", "#", ">")):
            break
        collected.append(line.rstrip())
        index += 1
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
