"""Gentoo Linux Security Advisories: which ones this system is exposed to.

``glsa-check`` comes with ``app-portage/gentoolkit``, which is not part of a
base install. That makes it the project's standard example of an optional
dependency: when it is missing the panel says which package to install and what
it would do, rather than disappearing or raising.

The output is one advisory per line — ``202501-01 [N] Title ( cat/pkg )`` — with
``[N]`` for "this system might be affected", ``[U]`` for "it is not" and ``[A]``
for "marked as already dealt with".
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from enum import StrEnum

PROGRAM = "glsa-check"
PACKAGE = "app-portage/gentoolkit"


class Exposure(StrEnum):
    AFFECTED = "affected"
    UNAFFECTED = "unaffected"
    APPLIED = "applied"
    UNKNOWN = "unknown"


_FLAGS = {"N": Exposure.AFFECTED, "U": Exposure.UNAFFECTED, "A": Exposure.APPLIED}

#: ``202501-01 [N] Some title ( cat/pkg cat/other )``
_LINE = re.compile(
    r"^(?P<id>\d{6}-\d{2})\s+\[(?P<flag>[A-Z?])\]\s+(?P<title>.*?)\s*"
    r"\(\s*(?P<packages>[^)]*)\)\s*$"
)

#: Escape sequences survive even with a pipe, because glsa-check colours by hand.
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

_NOT_AFFECTED = "This system is not affected by any of the listed GLSAs"


@dataclass(frozen=True, slots=True)
class Advisory:
    """One security advisory."""

    identifier: str
    title: str
    packages: tuple[str, ...]
    exposure: Exposure

    @property
    def url(self) -> str:
        return f"https://security.gentoo.org/glsa/{self.identifier}"

    @property
    def is_affected(self) -> bool:
        return self.exposure is Exposure.AFFECTED


@dataclass(frozen=True, slots=True)
class Report:
    """What ``glsa-check`` said."""

    advisories: tuple[Advisory, ...] = ()
    #: True when glsa-check stated outright that nothing applies.
    declared_clean: bool = False
    raw: str = ""

    @property
    def affected(self) -> tuple[Advisory, ...]:
        return tuple(item for item in self.advisories if item.is_affected)

    @property
    def is_clean(self) -> bool:
        return self.declared_clean or not self.affected


def is_available() -> bool:
    """Whether ``glsa-check`` is installed."""
    return shutil.which(PROGRAM) is not None


def parse(text: str) -> Report:
    """Read ``glsa-check -l affected`` output."""
    clean = _NOT_AFFECTED in text
    advisories = []
    for raw_line in text.splitlines():
        line = _ANSI.sub("", raw_line).strip()
        match = _LINE.match(line)
        if match is None:
            continue
        advisories.append(
            Advisory(
                identifier=match.group("id"),
                title=match.group("title").strip(),
                packages=tuple(match.group("packages").split()),
                exposure=_FLAGS.get(match.group("flag"), Exposure.UNKNOWN),
            )
        )
    return Report(advisories=tuple(advisories), declared_clean=clean, raw=text)
