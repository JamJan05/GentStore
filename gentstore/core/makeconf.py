"""Reading and changing single variables in ``make.conf``.

``make.conf`` is a shell fragment that belongs to the person who wrote it. It
has their comments in it, their ordering, the note they left themselves three
years ago about why ``MAKEOPTS`` is what it is. So this module never rewrites
the file: it finds the one line that assigns a variable and replaces exactly
that line, or appends one if the variable is not there at all.

Reading is deliberately separate from what Portage reports. ``FEATURES`` and
``USE`` in particular are assembled from the profile, ``/etc/env.d`` and
``make.conf`` together, so "what Portage uses" and "what this file says" are two
different answers and the screen shows both. Confusing them is how somebody ends
up pasting the profile's entire ``USE`` list into their own file.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .cfgfiles import DiffLine, unified
from .confedit import WritePlan
from .portage_env import PortageEnv
from .portage_env import env as _default_env

log = logging.getLogger(__name__)

#: ``NAME="value"`` on a line of its own. Leading whitespace is allowed and
#: kept; anything more exotic is left to the user's editor.
_ASSIGNMENT = re.compile(
    r"^(?P<indent>\s*)(?P<name>[A-Z][A-Z0-9_]*)=(?P<value>.*)$"
)

#: Variables the settings screen offers, in the order it shows them.
EDITABLE = (
    "MAKEOPTS",
    "EMERGE_DEFAULT_OPTS",
    "USE",
    "ACCEPT_KEYWORDS",
    "ACCEPT_LICENSE",
    "VIDEO_CARDS",
    "CPU_FLAGS_X86",
    "FEATURES",
    "L10N",
)


@dataclass(frozen=True, slots=True)
class Assignment:
    """One ``NAME=value`` line, and where it is."""

    name: str
    value: str
    raw: str
    #: 1-based, so it matches what an editor would say.
    line_number: int
    quote: str = '"'
    #: The assignment continues onto further lines; we will not rewrite it.
    continued: bool = False

    @property
    def is_editable(self) -> bool:
        return not self.continued


@dataclass(frozen=True, slots=True)
class MakeConf:
    """The file, as text and as assignments."""

    path: Path
    lines: tuple[str, ...] = ()
    assignments: dict[str, Assignment] | None = None
    exists: bool = True

    def get(self, name: str) -> Assignment | None:
        return (self.assignments or {}).get(name)

    def value(self, name: str, default: str = "") -> str:
        found = self.get(name)
        return found.value if found is not None else default

    def defines(self, name: str) -> bool:
        return name in (self.assignments or {})


def _strip_quotes(text: str) -> tuple[str, str]:
    """``"-j4"`` → ``("-j4", '"')``. Returns the value and the quote used."""
    stripped = text.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in "\"'":
        return stripped[1:-1], stripped[0]
    return stripped, ""


def _strip_comment(text: str) -> str:
    """Drop a trailing ``# …`` that is not inside quotes."""
    quote = ""
    for index, character in enumerate(text):
        if quote:
            if character == quote:
                quote = ""
        elif character in "\"'":
            quote = character
        elif character == "#":
            return text[:index]
    return text


def parse(text: str) -> dict[str, Assignment]:
    """Every single-line assignment in *text*, last one winning.

    Last one because that is what the shell does: a variable set twice ends up
    with the second value, and reporting the first would be a lie the user could
    not see through.
    """
    found: dict[str, Assignment] = {}
    lines = text.splitlines()
    for number, line in enumerate(lines, start=1):
        if line.lstrip().startswith("#"):
            continue
        match = _ASSIGNMENT.match(line)
        if match is None:
            continue

        remainder = match.group("value")
        continued = remainder.rstrip().endswith("\\") or _unbalanced(remainder)
        value, quote = _strip_quotes(_strip_comment(remainder))
        found[match.group("name")] = Assignment(
            name=match.group("name"),
            value=value,
            raw=line,
            line_number=number,
            quote=quote or '"',
            continued=continued,
        )
    return found


def _unbalanced(text: str) -> bool:
    """Whether a quote opens on this line and does not close on it."""
    stripped = _strip_comment(text).strip()
    if not stripped or stripped[0] not in "\"'":
        return False
    return not (len(stripped) >= 2 and stripped[-1] == stripped[0])


def path_for(env: PortageEnv | None = None) -> Path:
    root = Path(env.settings.get("PORTAGE_CONFIGROOT", "/")) if env else Path("/")
    return root / "etc" / "portage" / "make.conf"


def load(env: PortageEnv | None = None, path: Path | None = None) -> MakeConf:
    """Read ``make.conf``. A missing file is a valid, empty answer."""
    target = path or path_for(env)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return MakeConf(path=target, exists=False, assignments={})
    return MakeConf(
        path=target,
        lines=tuple(text.splitlines()),
        assignments=parse(text),
        exists=True,
    )


# ---------------------------------------------------------------------------
# changing one line
# ---------------------------------------------------------------------------


def format_line(name: str, value: str, quote: str = '"', indent: str = "") -> str:
    return f'{indent}{name}={quote}{value}{quote}'


def plan_set(conf: MakeConf, name: str, value: str) -> WritePlan:
    """The change that would give *name* the value *value*.

    An existing single-line assignment is replaced in place; a variable the file
    does not mention is appended. An assignment that spans several lines is
    refused rather than guessed at — rewriting somebody's carefully wrapped
    ``USE`` is not a thing to do on their behalf.
    """
    existing = conf.get(name)
    if existing is not None and not existing.is_editable:
        return WritePlan("none", conf.path, existing.raw, _kind(conf), previous=existing.raw)

    quote = existing.quote if existing is not None else '"'
    indent = _indent_of(existing.raw) if existing is not None else ""
    line = format_line(name, value, quote, indent)

    if existing is None:
        return WritePlan("append_line", conf.path, line, _kind(conf))
    if existing.raw == line:
        return WritePlan("none", conf.path, line, _kind(conf), previous=existing.raw)
    return WritePlan(
        "replace_line",
        conf.path,
        line,
        _kind(conf),
        previous=existing.raw,
        # Anchored to the start of the line so a mention of MAKEOPTS inside a
        # comment or another variable's value cannot be the one replaced.
        match=rf"^\s*{re.escape(name)}=",
    )


def _kind(conf: MakeConf):  # noqa: ANN202 - TargetKind, imported lazily
    from .confedit import TargetKind  # noqa: PLC0415 - avoids a cycle at import

    return TargetKind.EXISTING if conf.exists else TargetKind.SINGLE_FILE


def _indent_of(raw: str) -> str:
    return raw[: len(raw) - len(raw.lstrip())]


def preview(conf: MakeConf, plan: WritePlan) -> tuple[DiffLine, ...]:
    """The file before and after, so the change can be seen in its context."""
    before = [f"{line}\n" for line in conf.lines]
    after = list(before)

    if plan.op == "replace_line" and plan.previous is not None:
        for index, line in enumerate(conf.lines):
            if line == plan.previous:
                after[index] = f"{plan.line}\n"
                break
    elif plan.op == "append_line":
        after.append(f"{plan.line}\n")
    else:
        return ()

    return unified(before, after, str(conf.path), str(conf.path))


# ---------------------------------------------------------------------------
# suggestions
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Suggestion:
    """A value the machine can work out for itself."""

    value: str
    #: Key the interface turns into an explanation.
    reason: str = ""
    #: What is missing, when nothing could be suggested.
    missing: str = ""

    @property
    def is_available(self) -> bool:
        return bool(self.value)


#: Rule of thumb from the handbook: a parallel compile wants about this much
#: memory per job, and running out of it is far more painful than a slow build.
GIB_PER_JOB = 2


def _total_memory_gib() -> float | None:
    try:
        with open("/proc/meminfo", encoding="utf-8") as stream:
            for line in stream:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / (1024 * 1024)
    except (OSError, ValueError, IndexError):  # pragma: no cover - not Linux
        return None
    return None


def suggest_makeopts() -> Suggestion:
    """``-jN -lN`` from the number of cores, capped by how much memory there is.

    Cores alone is the usual advice and it is what most people set. It is also
    how a 28-core machine with 32 GB runs out of memory halfway through a
    ``chromium`` build, so the memory limit is applied and said out loud.
    """
    cores = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count()
    cores = cores or 1
    memory = _total_memory_gib()

    if memory is None:
        return Suggestion(f"-j{cores} -l{cores}", reason="cores")

    by_memory = max(1, int(memory // GIB_PER_JOB))
    if by_memory < cores:
        return Suggestion(f"-j{by_memory} -l{cores}", reason="memory")
    return Suggestion(f"-j{cores} -l{cores}", reason="cores")


CPUID_PROGRAM = "cpuid2cpuflags"
CPUID_PACKAGE = "app-portage/cpuid2cpuflags"


def suggest_cpu_flags() -> Suggestion:
    """``CPU_FLAGS_X86`` as ``cpuid2cpuflags`` reports it.

    An optional dependency, so its absence is an answer rather than an error:
    the screen names the package to install and leaves the field alone.
    """
    import shutil  # noqa: PLC0415 — only needed here
    import subprocess  # noqa: PLC0415

    if shutil.which(CPUID_PROGRAM) is None:
        return Suggestion("", missing=CPUID_PACKAGE)
    try:
        completed = subprocess.run(  # noqa: S603 - a fixed program name
            [CPUID_PROGRAM], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):  # pragma: no cover
        return Suggestion("", missing=CPUID_PACKAGE)

    for line in completed.stdout.splitlines():
        name, _, value = line.partition(":")
        if name.strip() == "CPU_FLAGS_X86":
            return Suggestion(value.strip(), reason="cpuid")
    return Suggestion("", missing=CPUID_PACKAGE)


def effective(name: str, env: PortageEnv | None = None) -> str:
    """What Portage actually uses for *name*, profile and env.d included."""
    env = env or _default_env()
    return env.settings.get(name, "") or ""
