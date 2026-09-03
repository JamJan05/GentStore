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


#: What a value written from the interface may be made of.
#:
#: A whitelist, and a short one, because the nine variables in :data:`EDITABLE`
#: all hold the same kind of thing: a list of bare tokens. Flags (``-bindist``,
#: ``X``), keywords (``~amd64``), licence groups (``@FREE``, ``-*``), option
#: strings (``--with-bdeps=y``), locale codes (``pt-BR``), ``make`` options
#: (``-j4``, ``-l4.5``). Every one of those is spelled with these characters.
#:
#: What it leaves out is everything that means something to whatever reads the
#: file: the quotes, the backslash, the backtick, the ``$``, and the line break
#: that would end the assignment early and leave the rest of the value sitting
#: in ``make.conf`` as something else entirely.
#:
#: The cost is that ``MAKEOPTS="-j$(nproc)"`` cannot be *written* from here. It
#: can still be read, shown, and left alone — a value nobody edits is never
#: reformatted — and a shell parser good enough to write that safely is a much
#: larger thing than this file, wrong in ways nobody would notice until it had
#: rewritten somebody's make.conf.
_SAFE_CHARACTERS = "A-Za-z0-9 _+=@,./:~*-"
_SAFE_VALUE = re.compile(f"^[{_SAFE_CHARACTERS}]*$")
_UNSAFE_CHARACTER = re.compile(f"[^{_SAFE_CHARACTERS}]")


class UnsafeValue(ValueError):
    """A value that cannot be written to ``make.conf`` without changing its syntax."""


def unsafe_value(name: str, value: str) -> str | None:
    """Why *value* cannot be written for *name*, or ``None`` when it can.

    Asked before a plan is built, so the interface can say what is wrong while
    the user is still looking at what they typed.
    """
    if "\x00" in value:
        return f"{name} cannot contain a null byte."
    if "\n" in value or "\r" in value:
        return (
            f"{name} has to be one line. A line break would end the assignment "
            f"where it appears, and leave the rest of what you typed in "
            f"make.conf as something Portage would read as its own setting."
        )
    if not _SAFE_VALUE.match(value):
        rejected = sorted(set(_UNSAFE_CHARACTER.findall(value)))
        return (
            f"{name} cannot contain {' '.join(rejected)}. make.conf is read as "
            f"shell, and Gentstore writes only values it can be sure change "
            f"nothing but the variable — letters, digits and "
            f"_ + = @ , . / : ~ * - and spaces. Edit the file by hand for "
            f"anything else."
        )
    return None


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
    """One ``NAME="value"`` line, or a refusal.

    The refusal is the point: this is the only place a value from the interface
    becomes a line of ``make.conf``, so it is where a value that would not stay
    a value has to stop. See :func:`unsafe_value`.
    """
    reason = unsafe_value(name, value)
    if reason is not None:
        raise UnsafeValue(reason)

    if quote not in ("'", '"'):
        # No quote to reuse. :func:`parse` never produces that — it records a
        # bare `MAKEOPTS=-j4` as double-quoted precisely so the rewrite carries
        # one — but this function is callable on its own, and an unquoted value
        # with a space in it is an assignment followed by a command.
        quote = '"' if value == "" or " " in value else ""
    return f"{indent}{name}={quote}{value}{quote}"


def plan_set(conf: MakeConf, name: str, value: str) -> WritePlan:
    """The change that would give *name* the value *value*.

    An existing single-line assignment is replaced in place; a variable the file
    does not mention is appended. An assignment that spans several lines is
    refused rather than guessed at — rewriting somebody's carefully wrapped
    ``USE`` is not a thing to do on their behalf.

    Raises :class:`UnsafeValue` for a value that would not stay a value; ask
    :func:`unsafe_value` first to say so without an exception.
    """
    reason = unsafe_value(name, value)
    if reason is not None:
        raise UnsafeValue(reason)

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
