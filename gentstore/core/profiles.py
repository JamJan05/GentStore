"""The profile: which one is in use, and what else is on offer.

A Gentoo profile decides the default USE flags, which packages are masked, what
counts as a system package and a good deal besides. Changing it is one of the
few things that alters the whole machine at once, which is why this module only
reads and the screen that uses it insists on saying so before anything happens.

The list comes from ``eselect profile list`` rather than from walking
``profiles/profiles.desc``: eselect is what a person would use, its numbering is
what they would type, and reproducing that numbering ourselves would be a second
opinion that could drift.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: ``  [7]   default/linux/amd64/23.0/desktop/plasma (stable) *``
_LINE = re.compile(
    r"^\s*\[(?P<index>\d+)\]\s+(?P<path>\S+)(?:\s+\((?P<stability>[^)]*)\))?"
    r"(?P<current>\s*\*)?\s*$"
)

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


@dataclass(frozen=True, slots=True)
class Profile:
    """One profile eselect offers."""

    index: int
    path: str
    stability: str = ""
    current: bool = False

    @property
    def is_stable(self) -> bool:
        return self.stability == "stable"

    @property
    def is_deprecated(self) -> bool:
        return "deprecated" in self.stability

    @property
    def family(self) -> str:
        """``default/linux/amd64/23.0`` — the part several profiles share."""
        parts = self.path.split("/")
        return "/".join(parts[:4]) if len(parts) > 4 else self.path

    @property
    def variant(self) -> str:
        """What distinguishes this one from the others in its family."""
        return self.path.removeprefix(self.family).lstrip("/") or "—"


def parse(text: str) -> tuple[Profile, ...]:
    """Read ``eselect profile list`` output."""
    found = []
    for raw in text.splitlines():
        line = _ANSI.sub("", raw)
        match = _LINE.match(line)
        if match is None:
            continue
        found.append(
            Profile(
                index=int(match.group("index")),
                path=match.group("path"),
                stability=(match.group("stability") or "").strip(),
                current=bool(match.group("current")),
            )
        )
    return tuple(found)


def current(profiles: tuple[Profile, ...]) -> Profile | None:
    return next((item for item in profiles if item.current), None)


def search(profiles: tuple[Profile, ...], query: str) -> tuple[Profile, ...]:
    needle = query.strip().lower()
    if not needle:
        return profiles
    return tuple(item for item in profiles if needle in item.path.lower())
