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

"""Searching the ebuild repositories and describing a single package.

The two halves solve very different problems.

*Searching* has to answer within a keystroke over roughly twenty thousand
packages, so it runs against an in-memory :class:`SearchIndex` built once in the
background: one row per ``cat/pkg`` with the description and the repositories
that carry it.

*Describing* happens for one package at a time, when the user clicks it, so it
can afford to ask Portage for everything — every version, its keywords, its slot
and why it might be masked.
"""

from __future__ import annotations

import fnmatch
import logging
import re
import time
from dataclasses import dataclass, field
from enum import StrEnum

from .portage_env import PortageEnv
from .portage_env import env as _default_env
from .worldset import InstalledPackage, installed_cps, installed_for_cp

log = logging.getLogger(__name__)

#: Metadata read for every version shown in the details panel.
_VERSION_KEYS = ("SLOT", "KEYWORDS", "IUSE", "RESTRICT", "EAPI")
#: Metadata that describes the package as a whole.
_PACKAGE_KEYS = ("DESCRIPTION", "HOMEPAGE", "LICENSE")

#: Versions Portage builds straight from a VCS checkout. By convention they end
#: in a run of nines — ``9999``, ``99999999``, ``2.0_pre9999`` — and they carry
#: no keywords at all, which is a different situation from "nobody has tested
#: this yet".
_LIVE_VERSION = re.compile(r"9{4,}$")

_WILDCARD = re.compile(r"[*?\[]")


class Keywording(StrEnum):
    """How a version is keyworded for the *local* architecture.

    Not the same as "installable": a stable version can still be masked, and a
    testing one only needs a line in ``package.accept_keywords``. The reason a
    version cannot be installed lives in :attr:`Version.masking`.
    """

    STABLE = "stable"
    TESTING = "testing"
    LIVE = "live"
    UNKEYWORDED = "unkeyworded"
    UNSUPPORTED = "unsupported"


class UnknownPackageError(LookupError):
    """No repository and no installed entry knows this ``cat/pkg``."""


@dataclass(frozen=True, slots=True)
class Version:
    """One ebuild: a version in a repository."""

    cpv: str
    cp: str
    version: str
    repo: str
    slot: str
    sub_slot: str
    keywords: tuple[str, ...]
    keywording: Keywording
    masking: tuple[str, ...]
    iuse: tuple[str, ...]
    #: Kept as the raw string: RESTRICT is a conditional expression
    #: (``!test? ( test )``), not a flat list, and splitting it would lie.
    restrict: str
    eapi: str
    installed: bool
    #: ``False`` when Portage would not say whether this version is masked.
    #: :attr:`masking` is then empty for want of an answer, not for want of a
    #: reason, and the two must not read the same.
    masking_known: bool = True

    @property
    def atom(self) -> str:
        """The exact atom that installs this ebuild and no other."""
        return f"={self.cpv}::{self.repo}" if self.repo else f"={self.cpv}"

    @property
    def slot_display(self) -> str:
        """``0/2`` when the sub-slot differs from the slot, otherwise ``0``."""
        if self.sub_slot and self.sub_slot != self.slot:
            return f"{self.slot}/{self.sub_slot}"
        return self.slot

    @property
    def is_installable(self) -> bool:
        """True when Portage would accept this version as it stands today.

        ``False`` also when the check itself failed. Offering to install a
        version nobody has managed to ask Portage about is the worse of the two
        wrong answers: the button would work, and ``emerge`` would refuse.
        """
        return self.masking_known and not self.masking


@dataclass(frozen=True, slots=True)
class PackageSummary:
    """One row of the search index — everything a result list needs."""

    cp: str
    description: str
    repos: tuple[str, ...]
    installed: bool

    @property
    def category(self) -> str:
        return self.cp.partition("/")[0]

    @property
    def name(self) -> str:
        return self.cp.partition("/")[2]


@dataclass(frozen=True, slots=True)
class PackageDetails:
    """Everything the details panel shows for one ``cat/pkg``."""

    cp: str
    description: str
    homepage: tuple[str, ...]
    license: str
    repos: tuple[str, ...]
    versions: tuple[Version, ...]
    installed: tuple[InstalledPackage, ...]
    best_visible: str | None
    download_size: int | None
    #: The repository this description was narrowed to, or ``""`` for all of
    #: them. Everything above — the versions, the best visible one, the
    #: metadata, the download size — is then answered by that repository alone.
    repo: str = ""

    @property
    def category(self) -> str:
        return self.cp.partition("/")[0]

    @property
    def name(self) -> str:
        return self.cp.partition("/")[2]

    @property
    def is_installed(self) -> bool:
        return bool(self.installed)

    def version(self, cpv: str) -> Version | None:
        return next((v for v in self.versions if v.cpv == cpv), None)


# ---------------------------------------------------------------------------
# keywords
# ---------------------------------------------------------------------------


def classify_keywords(keywords: tuple[str, ...], arch: str, version: str) -> Keywording:
    """Map a KEYWORDS list onto what it means for this machine.

    ``-arch`` and ``-*`` both mean the ebuild states it does not work here, so
    they win over anything else in the list.
    """
    if arch and (f"-{arch}" in keywords):
        return Keywording.UNSUPPORTED
    if arch and arch in keywords:
        return Keywording.STABLE
    if arch and f"~{arch}" in keywords:
        return Keywording.TESTING
    if not keywords:
        return Keywording.LIVE if _LIVE_VERSION.search(version) else Keywording.UNKEYWORDED
    if "-*" in keywords:
        return Keywording.UNSUPPORTED
    return Keywording.UNKEYWORDED


# ---------------------------------------------------------------------------
# a single package
# ---------------------------------------------------------------------------


def _split_slot(raw: str) -> tuple[str, str]:
    slot, _, sub = raw.partition("/")
    return slot, sub or slot


def _masking_status(env: PortageEnv, cpv: str, repo: str) -> tuple[tuple[str, ...], bool]:
    """Portage's reasons this version is masked, and whether it would say.

    The per-package clone, not ``env.settings``: ``getmaskingstatus()`` calls
    ``setcpv()`` on the configuration it is given whenever ``LICENSE`` carries a
    USE conditional, and the shared configuration is locked against being
    mutated.

    The second half of the answer is the difference between "no reasons" and
    "no answer". One unreadable ebuild must not empty the version list, but it
    must not pass for an installable version either.
    """
    import portage  # noqa: PLC0415 — slow import, deferred

    try:
        with env.configured(cpv) as settings:
            status = portage.getmaskingstatus(
                cpv, settings=settings, portdb=env.portdb, myrepo=repo or None
            )
    except Exception:  # pragma: no cover - broken ebuild metadata
        log.warning("Could not determine masking status of %s", cpv, exc_info=True)
        return (), False
    return tuple(str(reason) for reason in status), True


def details(cp: str, env: PortageEnv | None = None, repo: str = "") -> PackageDetails:
    """Collect everything known about one ``cat/pkg``.

    Works for packages that exist only in ``/var/db/pkg`` — an installed package
    whose ebuild has since been removed from the tree still has to be shown, or
    the interface would simply lose track of it.

    *repo* narrows the answer to a single repository. Two repositories carrying
    the same package is normal and mostly harmless, but the moment somebody is
    looking at one of them on purpose, versions from the other are worse than
    noise: the panel would offer a version that the chosen repository does not
    have, and the atom under the buttons would install the wrong ebuild. With
    *repo* set, the versions, the best visible one, the description and the
    download size all come from that repository and nowhere else.

    What is installed is never narrowed. A package is installed or it is not,
    whichever repository its ebuild came from.
    """
    env = env or _default_env()
    portdb = env.portdb
    arch = env.arch

    installed = installed_for_cp(cp, env)
    #: ``(cpv, repo)`` of everything in ``/var/db/pkg`` for this package, plus
    #: the versions whose entry does not record a repository at all — those can
    #: only ever be matched by version number.
    installed_from = {(p.cpv, p.repo) for p in installed}
    installed_anywhere = {cpv for cpv, source in installed_from if not source}

    try:
        candidates = portdb.cp_list(cp)
    except Exception:  # pragma: no cover - malformed category
        candidates = []
    if repo:
        candidates = [c for c in candidates if (getattr(c, "repo", "") or "") == repo]
    if not candidates and not installed:
        raise UnknownPackageError(cp)

    versions: list[Version] = []
    for cpv in candidates:
        # Deliberately not called ``repo``: that name belongs to the parameter,
        # and shadowing it here would quietly narrow everything below to
        # whichever repository happened to come last.
        source_repo = getattr(cpv, "repo", "") or ""
        try:
            slot_raw, keywords, iuse, restrict, eapi = portdb.aux_get(
                cpv, list(_VERSION_KEYS), myrepo=source_repo or None
            )
        except Exception:  # pragma: no cover - unreadable ebuild
            log.warning("Skipping unreadable ebuild %s::%s", cpv, source_repo, exc_info=True)
            continue
        slot, sub_slot = _split_slot(slot_raw)
        keyword_list = tuple(keywords.split())
        masking_reasons, masking_known = _masking_status(env, str(cpv), source_repo)
        versions.append(
            Version(
                cpv=str(cpv),
                cp=cp,
                version=getattr(cpv, "version", "") or "",
                repo=source_repo,
                slot=slot,
                sub_slot=sub_slot,
                keywords=keyword_list,
                keywording=classify_keywords(keyword_list, arch, getattr(cpv, "version", "")),
                masking=masking_reasons,
                masking_known=masking_known,
                iuse=tuple(iuse.split()),
                restrict=restrict,
                eapi=eapi,
                # Two repositories can carry the same version, and only one of
                # them built what is on the disk. Saying "installed" under the
                # other one would promise a rebuild that is not one.
                installed=(str(cpv), source_repo) in installed_from
                or str(cpv) in installed_anywhere,
            )
        )

    best = portdb.xmatch("bestmatch-visible", _repo_atom(cp, repo)) or None
    best_cpv = str(best) if best else None

    source = next((v for v in versions if v.cpv == best_cpv), None)
    if source is None:
        source = versions[-1] if versions else None

    description = homepage = license_ = ""
    if source is not None:
        try:
            description, homepage, license_ = portdb.aux_get(
                source.cpv, list(_PACKAGE_KEYS), myrepo=source.repo or None
            )
        except Exception:  # pragma: no cover
            log.warning("Could not read metadata of %s", source.cpv, exc_info=True)
    elif installed:
        description = installed[-1].description
        license_ = installed[-1].license

    repos = tuple(dict.fromkeys(v.repo for v in versions if v.repo))

    return PackageDetails(
        cp=cp,
        description=description,
        homepage=tuple(homepage.split()),
        license=license_,
        repos=repos,
        versions=tuple(versions),
        installed=installed,
        best_visible=best_cpv,
        download_size=download_size(source.cpv, source.repo, env) if source else None,
        repo=repo,
    )


def _repo_atom(cp: str, repo: str) -> str:
    """``cat/pkg`` or ``cat/pkg::repo`` — what Portage's matchers understand."""
    return f"{cp}::{repo}" if repo else cp


def download_size(cpv: str, repo: str = "", env: PortageEnv | None = None) -> int | None:
    """Bytes that would have to be fetched, or ``None`` when Portage cannot say.

    Live ebuilds and ``RESTRICT=fetch`` packages legitimately have no answer;
    that is reported as unknown rather than as zero.
    """
    env = env or _default_env()
    try:
        sizes = env.portdb.getfetchsizes(cpv, myrepo=repo or None)
    except Exception:
        return None
    if not sizes:
        return None
    return sum(sizes.values())


@dataclass(frozen=True, slots=True)
class PackageState:
    """The one-line status a result row shows: what is installed, what is offered.

    Deliberately much cheaper than :func:`details` — no per-version metadata, no
    masking reasons — because a result list asks for one of these per visible
    row while the user is still typing.
    """

    cp: str
    installed_version: str | None
    available_version: str | None
    newest_version: str | None

    @property
    def is_installed(self) -> bool:
        return self.installed_version is not None

    @property
    def is_blocked(self) -> bool:
        """No version is installable as things stand.

        Says nothing about *why* — keywords, a mask, a licence. That answer
        needs ``core/masking.py`` and arrives with session S6.
        """
        return self.available_version is None and self.newest_version is not None

    @property
    def has_update(self) -> bool:
        return (
            self.installed_version is not None
            and self.available_version is not None
            and self.available_version != self.installed_version
        )


def package_state(cp: str, env: PortageEnv | None = None, repo: str = "") -> PackageState:
    """Status of one ``cat/pkg``, cheap enough to call while scrolling a list.

    Measured on a full tree: about 0.45 ms per package, so filling the twenty
    or so rows a list shows at once costs under 10 ms. Fetching it for all
    twenty thousand packages up front would cost seven seconds, which is why
    this is not part of :class:`SearchIndex`.

    *repo* narrows the offered versions to one repository, so that a list
    filtered to ``::gentoo`` does not advertise an overlay's newer version on
    a row it is not going to install (see :func:`details`).
    """
    env = env or _default_env()

    installed = [str(cpv) for cpv in env.vardb.cp_list(cp)]
    try:
        cpvs = env.portdb.cp_list(cp)
    except Exception:  # pragma: no cover - malformed category
        cpvs = []
    if repo:
        cpvs = [c for c in cpvs if (getattr(c, "repo", "") or "") == repo]
    best = env.portdb.xmatch("bestmatch-visible", _repo_atom(cp, repo)) if cpvs else ""

    return PackageState(
        cp=cp,
        installed_version=_version_of(installed[-1], cp) if installed else None,
        available_version=_version_of(str(best), cp) if best else None,
        newest_version=_version_of(str(cpvs[-1]), cp) if cpvs else None,
    )


def _version_of(cpv: str, cp: str) -> str:
    """``media-video/mpv-0.41.0`` → ``0.41.0``. Falls back to the whole cpv."""
    return cpv[len(cp) + 1:] if cpv.startswith(cp + "-") else cpv


# ---------------------------------------------------------------------------
# the search index
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IndexEntry:
    """A search-index row. ``fold_*`` fields are pre-lowercased for matching."""

    cp: str
    category: str
    name: str
    description: str
    repos: tuple[str, ...]
    fold_name: str
    fold_cp: str
    fold_description: str

    def to_summary(self, installed: frozenset[str]) -> PackageSummary:
        return PackageSummary(
            cp=self.cp,
            description=self.description,
            repos=self.repos,
            installed=self.cp in installed,
        )


# Match quality, best first. Kept as plain numbers because they are only ever
# used as a sort key.
_RANK_EXACT_CP = 0
_RANK_EXACT_NAME = 1
_RANK_NAME_PREFIX = 2
_RANK_NAME_SUBSTRING = 3
_RANK_CP_SUBSTRING = 4
_RANK_DESCRIPTION = 5


@dataclass(slots=True)
class SearchIndex:
    """An in-memory catalogue of every ``cat/pkg`` in every enabled repository.

    Built once (about three seconds on a cold page cache for a full tree) and
    then queried per keystroke. It is a snapshot: after a sync or after enabling
    a repository the caller rebuilds it. Installations are cheaper — they only
    change which rows are marked as installed, which :meth:`refresh_installed`
    updates on its own.
    """

    entries: tuple[IndexEntry, ...] = ()
    installed: frozenset[str] = frozenset()
    repos: tuple[str, ...] = ()
    built_at: float = 0.0
    build_seconds: float = 0.0
    _by_cp: dict[str, IndexEntry] = field(default_factory=dict, repr=False)

    def __len__(self) -> int:
        return len(self.entries)

    def __post_init__(self) -> None:
        if not self._by_cp:
            self._by_cp = {entry.cp: entry for entry in self.entries}

    # -- building ----------------------------------------------------------

    @classmethod
    def build(cls, env: PortageEnv | None = None, on_progress=None) -> SearchIndex:  # noqa: ANN001
        """Read every repository and return a ready index.

        *on_progress* is called as ``(done, total)`` every few hundred packages.
        It runs on whatever thread builds the index, so a GUI caller must not
        touch widgets from it — emit a signal instead.
        """
        env = env or _default_env()
        portdb = env.portdb
        started = time.monotonic()

        all_cps = sorted(portdb.cp_all())
        total = len(all_cps)
        entries: list[IndexEntry] = []
        step = max(1, total // 100)

        for position, cp in enumerate(all_cps, start=1):
            try:
                cpvs = portdb.cp_list(cp)
            except Exception:  # pragma: no cover - malformed category
                continue
            if not cpvs:
                continue
            newest = cpvs[-1]
            repo = getattr(newest, "repo", "") or ""
            try:
                description = portdb.aux_get(newest, ["DESCRIPTION"], myrepo=repo or None)[0]
            except Exception:  # pragma: no cover - unreadable ebuild
                description = ""
            category, _, name = cp.partition("/")
            entries.append(
                IndexEntry(
                    cp=cp,
                    category=category,
                    name=name,
                    description=description,
                    repos=tuple(dict.fromkeys(getattr(c, "repo", "") or "" for c in cpvs)),
                    fold_name=name.lower(),
                    fold_cp=cp.lower(),
                    fold_description=description.lower(),
                )
            )
            if on_progress is not None and position % step == 0:
                on_progress(position, total)

        if on_progress is not None:
            on_progress(total, total)

        elapsed = time.monotonic() - started
        log.info("Search index built: %d packages in %.2f s", len(entries), elapsed)
        return cls(
            entries=tuple(entries),
            installed=installed_cps(env),
            repos=env.repo_names,
            built_at=time.time(),
            build_seconds=elapsed,
        )

    def refresh_installed(self, env: PortageEnv | None = None) -> None:
        """Re-read ``/var/db/pkg``. Cheap; call it after an install or unmerge."""
        self.installed = installed_cps(env or _default_env())

    # -- querying ----------------------------------------------------------

    def get(self, cp: str) -> PackageSummary | None:
        entry = self._by_cp.get(cp)
        return entry.to_summary(self.installed) if entry is not None else None

    def search(
        self,
        query: str,
        *,
        repos: tuple[str, ...] | None = None,
        only_installed: bool = False,
        match_description: bool = True,
        limit: int | None = 500,
    ) -> list[PackageSummary]:
        """Find packages, best match first.

        Understands three shapes of *query*, all case-insensitive:

        * plain text — matched against the package name, then ``cat/pkg``, then
          the description;
        * a ``cat/pkg`` fragment — anything containing ``/``;
        * a glob — anything containing ``*``, ``?`` or ``[``, matched against the
          full ``cat/pkg`` so that ``media-*/*`` behaves the way Portage users
          expect.

        A trailing ``::repo`` narrows the search to that repository, exactly as
        it does in an atom.
        """
        text, query_repo = split_repo_suffix(query.strip())
        wanted_repos = set(repos) if repos else None
        if query_repo:
            wanted_repos = {query_repo} if wanted_repos is None else wanted_repos & {query_repo}

        needle = text.lower()
        matcher = _glob_matcher(needle) if _WILDCARD.search(needle) else None
        if not needle and matcher is None and wanted_repos is None and not only_installed:
            return []

        results: list[tuple[int, int, str, PackageSummary]] = []
        for entry in self.entries:
            if wanted_repos is not None and not wanted_repos.intersection(entry.repos):
                continue
            is_installed = entry.cp in self.installed
            if only_installed and not is_installed:
                continue

            if matcher is not None:
                if not matcher(entry.fold_cp) and not matcher(entry.fold_name):
                    continue
                rank = _RANK_NAME_PREFIX
            elif not needle:
                rank = _RANK_CP_SUBSTRING
            else:
                rank = _rank(entry, needle, match_description)
                if rank is None:
                    continue

            results.append(
                (
                    rank,
                    len(entry.name),
                    entry.cp,
                    PackageSummary(
                        cp=entry.cp,
                        description=entry.description,
                        repos=entry.repos,
                        installed=is_installed,
                    ),
                )
            )

        # Rank first, then the shorter name — within one rank a shorter name is
        # the closer match — and finally cat/pkg, so the order is stable.
        results.sort(key=lambda item: (item[0], item[1], item[2]))
        if limit is not None:
            results = results[:limit]
        return [summary for *_, summary in results]


def _rank(entry: IndexEntry, needle: str, match_description: bool) -> int | None:
    """Score one entry against a plain-text needle, or ``None`` for no match."""
    if "/" in needle:
        if entry.fold_cp == needle:
            return _RANK_EXACT_CP
        return _RANK_CP_SUBSTRING if needle in entry.fold_cp else None
    if entry.fold_name == needle:
        return _RANK_EXACT_NAME
    if entry.fold_name.startswith(needle):
        return _RANK_NAME_PREFIX
    if needle in entry.fold_name:
        return _RANK_NAME_SUBSTRING
    if needle in entry.fold_cp:
        return _RANK_CP_SUBSTRING
    if match_description and needle in entry.fold_description:
        return _RANK_DESCRIPTION
    return None


def split_repo_suffix(query: str) -> tuple[str, str]:
    """Split ``foo::guru`` into ``("foo", "guru")``.

    Public because the search screen needs the same answer: a typed ``::repo``
    narrows the details panel exactly as a repository pill does.
    """
    text, separator, repo = query.partition("::")
    return (text, repo.strip()) if separator else (query, "")


def _glob_matcher(pattern: str):  # noqa: ANN202 - returns a closure
    regex = re.compile(fnmatch.translate(pattern))
    return lambda value: regex.match(value) is not None


# ---------------------------------------------------------------------------
# atoms
# ---------------------------------------------------------------------------


def matching_cps(name: str, index: SearchIndex) -> tuple[str, ...]:
    """Every ``cat/pkg`` whose package name is exactly *name*, case-insensitive.

    More common than it looks: ``portage`` alone is ``acct-group/portage``,
    ``acct-user/portage`` and ``sys-apps/portage``.
    """
    needle = name.lower()
    return tuple(entry.cp for entry in index.entries if entry.fold_name == needle)


def resolve_cp(text: str, index: SearchIndex | None = None) -> str | None:
    """Turn user input into a ``cat/pkg``, or ``None`` if it is not one.

    Accepts a bare ``cat/pkg``, a full atom such as ``>=media-video/mpv-0.40``
    and — when an *index* is available — a plain package name, provided exactly
    one package carries it. An ambiguous name is deliberately *not* resolved to
    an arbitrary winner; :func:`matching_cps` gives the caller the choices to
    put in front of the user.
    """
    from portage.dep import dep_getkey, isvalidatom  # noqa: PLC0415 — slow import

    candidate = split_repo_suffix(text.strip())[0]
    if isvalidatom(candidate):
        key = dep_getkey(candidate)
        if key:
            return str(key)
    if "/" in candidate or index is None:
        return None
    matches = matching_cps(candidate, index)
    return matches[0] if len(matches) == 1 else None
