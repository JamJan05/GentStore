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

"""The catalogue of repositories that exist, whether or not this system has them.

Gentoo publishes a list of every known ebuild repository as
``repositories.xml`` — some four hundred and sixty of them, from GURU down to
one person's collection of three ebuilds. This module reads that list, so the
interface can offer "type ``steam``, press enable" instead of "find the URL
yourself and write a ``repos.conf`` section".

**Gentstore does not download it.** ``app-eselect/eselect-repository`` already
fetches and caches the file, and Docs/04-privileges.md §8 says the only network
traffic this application causes is the programs it runs on the user's behalf.
So the cache is read where eselect keeps it, and refreshing it means running
``eselect repository list`` — visibly, in the command log, like everything else.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

log = logging.getLogger(__name__)

#: Where eselect-repository keeps its copy, most likely first. The root-owned
#: one appears when the list was last refreshed by root.
CACHE_PATHS = (
    Path.home() / ".cache" / "eselect-repo" / "repositories.xml",
    Path("/var/cache/eselect-repo/repositories.xml"),
)

#: Quality levels the catalogue uses, from most to least trustworthy.
QUALITY_ORDER = ("core", "stable", "testing", "experimental", "graveyard")


@dataclass(frozen=True, slots=True)
class CatalogueEntry:
    """One repository in Gentoo's published list."""

    name: str
    description: str
    homepage: str
    owners: tuple[str, ...]
    #: ``(sync-type, uri)`` pairs, in the order the catalogue lists them.
    sources: tuple[tuple[str, str], ...]
    quality: str
    status: str

    @property
    def is_official(self) -> bool:
        """Run by Gentoo itself rather than by an individual.

        Not a statement about quality — GURU is official and experimental at
        once — but it is what decides whether the interface warns about ebuilds
        from a stranger running as root at build time.
        """
        return self.status == "official"

    @property
    def preferred_source(self) -> tuple[str, str] | None:
        """The source to offer. Anything anonymous beats an SSH URL."""
        for sync_type, uri in self.sources:
            if not uri.startswith(("git+ssh", "ssh://")):
                return (sync_type, uri)
        return self.sources[0] if self.sources else None

    @property
    def quality_rank(self) -> int:
        try:
            return QUALITY_ORDER.index(self.quality)
        except ValueError:
            return len(QUALITY_ORDER)


@dataclass(frozen=True, slots=True)
class Catalogue:
    """Everything in ``repositories.xml``, ready to search."""

    entries: tuple[CatalogueEntry, ...] = ()
    path: Path | None = None
    fetched: datetime | None = None

    def __len__(self) -> int:
        return len(self.entries)

    @property
    def is_empty(self) -> bool:
        return not self.entries

    def get(self, name: str) -> CatalogueEntry | None:
        return next((entry for entry in self.entries if entry.name == name), None)

    def search(self, query: str, limit: int | None = 60) -> list[CatalogueEntry]:
        """Find repositories by name or description, best match first.

        Ranked the way the package search is: an exact name, then a name that
        starts with the query, then one that contains it, then the description.
        """
        needle = query.strip().lower()
        if not needle:
            return []

        ranked: list[tuple[int, int, str, CatalogueEntry]] = []
        for entry in self.entries:
            name = entry.name.lower()
            if name == needle:
                rank = 0
            elif name.startswith(needle):
                rank = 1
            elif needle in name:
                rank = 2
            elif needle in entry.description.lower():
                rank = 3
            else:
                continue
            # Within a rank, a repository Gentoo vouches for comes first: it is
            # what somebody typing "steam" almost certainly means.
            ranked.append((rank, entry.quality_rank, entry.name.lower(), entry))

        ranked.sort(key=lambda item: item[:3])
        found = [entry for *_ignored, entry in ranked]
        return found[:limit] if limit is not None else found


def cache_path() -> Path | None:
    """The catalogue file eselect keeps, or ``None`` when there is none yet."""
    return next((path for path in CACHE_PATHS if path.is_file()), None)


def _text(element, tag: str) -> str:  # noqa: ANN001 - ElementTree element
    value = element.findtext(tag)
    return " ".join(value.split()) if value else ""


def _owners(element) -> tuple[str, ...]:  # noqa: ANN001
    owners = []
    for owner in element.iterfind("owner"):
        name = _text(owner, "name")
        email = _text(owner, "email")
        if name and email:
            owners.append(f"{name} <{email}>")
        elif name or email:
            owners.append(name or email)
    return tuple(owners)


def parse(path: Path) -> Catalogue:
    """Read one ``repositories.xml``. A broken file gives an empty catalogue."""
    try:
        tree = ElementTree.parse(path)
    except (OSError, ElementTree.ParseError) as exc:
        log.warning("Could not read the repository catalogue %s: %s", path, exc)
        return Catalogue()

    entries = []
    for element in tree.getroot().iterfind("repo"):
        name = _text(element, "name")
        if not name:
            continue
        sources = tuple(
            (source.get("type", ""), " ".join((source.text or "").split()))
            for source in element.iterfind("source")
            if (source.text or "").strip()
        )
        entries.append(
            CatalogueEntry(
                name=name,
                description=_description(element),
                homepage=_text(element, "homepage"),
                owners=_owners(element),
                sources=sources,
                quality=element.get("quality", ""),
                status=element.get("status", ""),
            )
        )

    try:
        fetched = datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:  # pragma: no cover
        fetched = None
    return Catalogue(entries=tuple(entries), path=path, fetched=fetched)


def _description(element) -> str:  # noqa: ANN001
    """The English description; the catalogue carries several languages."""
    for description in element.iterfind("description"):
        if description.get("{http://www.w3.org/XML/1998/namespace}lang", "en") == "en":
            return " ".join((description.text or "").split())
    return _text(element, "description")


def load() -> Catalogue:
    """The catalogue as it stands on this machine."""
    path = cache_path()
    if path is None:
        log.info("No repository catalogue yet; `eselect repository list` fetches one")
        return Catalogue()
    return parse(path)


#: A repository name eselect will accept: the catalogue's own convention.
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_+.-]*$")

#: Schemes worth handing to git, rsync or subversion, and nothing else.
#:
#: An allowlist rather than "does it contain ://", because git reads a URL of
#: the form ``ext::sh -c 'command'`` as *run this command* — and such a string
#: contains "://" perfectly happily if you put one at the end of it. The URL
#: goes on to be synced as root's business, so a URL that is really a command is
#: a way to run a command.
_SCHEME = re.compile(r"^(?:https?|git|ssh|rsync|svn|file)://[^\s]+$")

#: ``git@github.com:user/repo.git`` — git's other spelling of ssh://.
_SCP_LIKE = re.compile(r"^[A-Za-z0-9._-]+@[A-Za-z0-9._-]+:[^\s:]+$")


def is_valid_name(name: str) -> bool:
    return bool(_NAME.match(name))


def is_valid_uri(uri: str) -> bool:
    """Whether this is a URL worth putting in front of ``eselect repository``.

    Deliberately narrower than what git accepts. Whether the far end exists is
    git's business and it will say so in the log; whether the *shape* of the
    string is a URL at all is ours, because the alternative is handing a
    transport helper to a program running with more privileges than the person
    who typed it.

    ``gentstore-launcher`` checks the same thing again on the other side of
    pkexec. This copy is what stops the Add button from offering the command in
    the first place.
    """
    text = uri.strip()
    return bool(_SCHEME.match(text) or _SCP_LIKE.match(text))
