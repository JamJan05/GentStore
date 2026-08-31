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

"""Gentoo news items — the ones that apply to this system, and which are unread.

Every repository can ship news (GLEP 42): short notes that a coming update needs
a hand, or that something is about to be removed. ``emerge`` counts them and
tells you to go and read them somewhere else, which is where most people stop.

The format is plain text with RFC-822-ish headers, so it is read directly rather
than through Portage's ``NewsManager`` — which answers with a count and keeps
the items themselves to itself.

Relevance is the interesting part. An item with ``Display-If-Installed`` is only
for people who have that package; one with ``Display-If-Profile`` only for that
profile. An item with none of those headers is for everybody.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .portage_env import PortageEnv
from .portage_env import env as _default_env

log = logging.getLogger(__name__)

#: Where Portage records which items have been read.
NEWS_STATE_DIR = Path("/var/lib/gentoo/news")

_HEADER = re.compile(r"^(?P<name>[A-Za-z][A-Za-z0-9-]*):\s*(?P<value>.*)$")


@dataclass(frozen=True, slots=True)
class NewsItem:
    """One news item, with everything needed to decide whether to show it."""

    identifier: str
    repo: str
    title: str
    author: str
    posted: date | None
    body: str
    #: ``Display-If-Installed`` atoms.
    if_installed: tuple[str, ...] = ()
    #: ``Display-If-Profile`` profile paths.
    if_profile: tuple[str, ...] = ()
    #: ``Display-If-Keyword`` architectures.
    if_keyword: tuple[str, ...] = ()
    unread: bool = False
    #: Why this item is being shown: the atom or profile that matched.
    matched: str = ""

    @property
    def is_targeted(self) -> bool:
        """Aimed at particular systems rather than posted to everybody."""
        return bool(self.if_installed or self.if_profile or self.if_keyword)

    @property
    def summary(self) -> str:
        """The first paragraph, for a list that shows one line per item."""
        for paragraph in self.body.split("\n\n"):
            text = " ".join(paragraph.split())
            if text:
                return text
        return ""


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def parse_item(path: Path, identifier: str, repo: str) -> NewsItem | None:
    """Read one ``<id>.<lang>.txt`` file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:  # pragma: no cover - a news file we cannot read
        return None

    headers: dict[str, list[str]] = {}
    lines = text.splitlines()
    index = 0
    for index, line in enumerate(lines):  # noqa: B007 - index is used after the loop
        if not line.strip():
            break
        match = _HEADER.match(line)
        if match:
            headers.setdefault(match.group("name"), []).append(match.group("value").strip())

    def first(name: str) -> str:
        values = headers.get(name)
        return values[0] if values else ""

    return NewsItem(
        identifier=identifier,
        repo=repo,
        title=first("Title") or identifier,
        author=first("Author"),
        posted=_parse_date(first("Posted")),
        body="\n".join(lines[index + 1:]).strip(),
        if_installed=tuple(headers.get("Display-If-Installed", ())),
        if_profile=tuple(headers.get("Display-If-Profile", ())),
        if_keyword=tuple(headers.get("Display-If-Keyword", ())),
    )


def unread_ids(repo: str, state_dir: Path | None = None) -> frozenset[str]:
    """Item identifiers Portage still counts as unread for *repo*."""
    path = (state_dir or NEWS_STATE_DIR) / f"news-{repo}.unread"
    try:
        return frozenset(
            line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    except OSError:
        return frozenset()


def _news_dir(env: PortageEnv, repo: str) -> Path | None:
    location = env.repo_location(repo)
    if not location:
        return None
    directory = Path(location) / "metadata" / "news"
    return directory if directory.is_dir() else None


def _relevance(item: NewsItem, env: PortageEnv, profile: str) -> tuple[bool, str]:
    """Whether this item applies here, and what made it apply."""
    if not item.is_targeted:
        return True, ""

    for atom in item.if_installed:
        if env.vardb.match(atom):
            return True, atom
    for path in item.if_profile:
        if profile == path or profile.startswith(f"{path}/"):
            return True, path
    for keyword in item.if_keyword:
        if keyword.lstrip("~") == env.arch:
            return True, keyword
    return False, ""


def _current_profile(env: PortageEnv) -> str:
    """The profile as the news headers spell it: ``default/linux/amd64/23.0/…``."""
    try:
        target = (Path(env.eroot) / "etc" / "portage" / "make.profile").resolve()
    except OSError:  # pragma: no cover
        return ""
    parts = target.parts
    if "profiles" in parts:
        return "/".join(parts[parts.index("profiles") + 1:])
    return ""


def load(
    env: PortageEnv | None = None,
    *,
    only_relevant: bool = True,
    state_dir: Path | None = None,
) -> tuple[NewsItem, ...]:
    """Every news item on this system, newest first.

    *only_relevant* drops the ones aimed at other architectures and other
    profiles — which on a typical system is most of them.
    """
    env = env or _default_env()
    profile = _current_profile(env)
    items: list[NewsItem] = []

    for repo in env.repo_names:
        directory = _news_dir(env, repo)
        if directory is None:
            continue
        unread = unread_ids(repo, state_dir)
        for entry in sorted(directory.iterdir()):
            if not entry.is_dir():
                continue
            source = entry / f"{entry.name}.en.txt"
            if not source.is_file():
                candidates = sorted(entry.glob(f"{entry.name}.*.txt"))
                if not candidates:
                    continue
                source = candidates[0]

            item = parse_item(source, entry.name, repo)
            if item is None:
                continue
            applies, matched = _relevance(item, env, profile)
            if only_relevant and not applies:
                continue
            items.append(
                NewsItem(
                    **{
                        **{
                            field: getattr(item, field)
                            for field in item.__slots__
                            if field not in ("unread", "matched")
                        },
                        "unread": item.identifier in unread,
                        "matched": matched,
                    }
                )
            )

    items.sort(key=lambda entry: (entry.posted or date.min), reverse=True)
    return tuple(items)


def unread(items: tuple[NewsItem, ...]) -> tuple[NewsItem, ...]:
    return tuple(item for item in items if item.unread)


def state_is_writable(state_dir: Path | None = None) -> bool:
    """Whether this user can mark items read without becoming root.

    ``/var/lib/gentoo/news`` is usually group-writable by ``portage``; when the
    user is not in that group, ``eselect news read`` has to go through pkexec
    like everything else.
    """
    import os  # noqa: PLC0415 — only needed here

    directory = state_dir or NEWS_STATE_DIR
    return directory.is_dir() and os.access(directory, os.W_OK)
