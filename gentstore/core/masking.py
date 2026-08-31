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

"""Why a package will not install, and what one line would change that.

``emerge`` says "masked by: ~amd64 keyword" and expects the reader to know what
that implies, where the fix goes and what they are agreeing to. Four different
situations hide behind that one sentence, and they are not equally serious:

``~arch keyword``
    Nobody has declared the version stable yet. Very common, usually fine, and
    the ordinary way to run newer software on Gentoo.
``missing keyword``
    Nobody has tested it on this architecture at all — including every live
    ebuild, which never carries keywords by design.
``-arch`` / ``-*``
    The ebuild states it does not work here. Not something to click past.
``package.mask``
    A person decided this version should not be installed, and wrote down why.
    That comment is the single most useful thing on the screen, so it is fetched
    and shown verbatim.
``licence``
    The system's ``ACCEPT_LICENSE`` does not cover one of the package's
    licences — see :mod:`gentstore.core.licenses`.

Each one maps to a different file under ``/etc/portage``, which is the other
half of what this module produces. There is a sixth answer, ``unknown``, for
when Portage will not say: it maps to no file and no fix, and exists so that a
failed check cannot be mistaken for a clean one.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import StrEnum

from . import licenses
from .portage_env import PortageEnv
from .portage_env import env as _default_env

log = logging.getLogger(__name__)


class BlockKind(StrEnum):
    TESTING_KEYWORD = "testing-keyword"
    MISSING_KEYWORD = "missing-keyword"
    UNSUPPORTED_ARCH = "unsupported-arch"
    PACKAGE_MASK = "package-mask"
    LICENCE = "licence"
    OTHER = "other"
    #: Portage refused to answer. Not "installable" and not any known block —
    #: the one state where Gentstore has nothing to tell the user but says so.
    UNKNOWN = "unknown"


#: Portage's own wording, which is what these patterns have to match.
_TESTING = re.compile(r"^~(\S+) keyword$")
_MISSING = re.compile(r"^missing keyword$")
_UNSUPPORTED = re.compile(r"^(-\S+) keyword$")
_LICENCE = re.compile(r"^(.+) license\(s\)$")
_MASKS = frozenset({"package.mask", "profile"})
#: ``getmaskingstatus`` keeps the shape of the ``LICENSE`` expression in its
#: message — ``|| ( MIT GPL-2 ) license(s)`` says the two are alternatives, and
#: a USE conditional whose flag is off leaves an empty ``( )`` behind. Useful to
#: read, and the raw line keeps it, but these are not licences: left in, they
#: become chips the user is invited to click and tokens written into
#: package.license.
_STRUCTURE = frozenset({"||", "(", ")"})


@dataclass(frozen=True, slots=True)
class Fix:
    """The one line that would lift a block."""

    #: The file under ``/etc/portage`` it belongs in.
    file: str
    atom: str
    tokens: tuple[str, ...]
    #: ``False`` when the change is possible but ill-advised.
    advisable: bool = True
    #: Key the interface turns into a sentence; empty when there is nothing to add.
    caution: str = ""

    @property
    def line(self) -> str:
        return " ".join([self.atom, *self.tokens])


@dataclass(frozen=True, slots=True)
class Block:
    """One reason a version cannot be installed."""

    kind: BlockKind
    #: Portage's own words, kept so the interface can always fall back to them.
    raw: str
    #: The keyword involved, for keyword blocks: ``~amd64``, ``-amd64``, ``-*``.
    keyword: str = ""
    #: The licences that are not accepted, for licence blocks.
    licences: tuple[str, ...] = ()
    #: The maintainer's note from ``package.mask``, verbatim.
    comment: str = ""
    #: The file that note came from.
    location: str = ""

    @property
    def is_serious(self) -> bool:
        """Whether clicking past this is a bad idea rather than routine."""
        return self.kind in (BlockKind.UNSUPPORTED_ARCH, BlockKind.PACKAGE_MASK)


@dataclass(frozen=True, slots=True)
class Blockage:
    """Everything standing between a version and being installed."""

    cpv: str
    cp: str
    repo: str
    blocks: tuple[Block, ...]

    @property
    def is_blocked(self) -> bool:
        return bool(self.blocks)

    @property
    def primary(self) -> Block | None:
        """The one to lead with.

        Ordered by how much thought it deserves, not by how Portage listed
        them: a package that is both hard-masked and untested is a hard-mask
        story first.
        """
        order = {
            BlockKind.UNKNOWN: 0,
            BlockKind.PACKAGE_MASK: 1,
            BlockKind.UNSUPPORTED_ARCH: 2,
            BlockKind.LICENCE: 3,
            BlockKind.MISSING_KEYWORD: 4,
            BlockKind.TESTING_KEYWORD: 5,
            BlockKind.OTHER: 6,
        }
        return min(self.blocks, key=lambda b: order[b.kind], default=None)


def _classify(raw: str) -> Block:
    text = raw.strip()

    match = _TESTING.match(text)
    if match:
        return Block(BlockKind.TESTING_KEYWORD, text, keyword=f"~{match.group(1)}")

    if _MISSING.match(text):
        return Block(BlockKind.MISSING_KEYWORD, text, keyword="**")

    match = _UNSUPPORTED.match(text)
    if match:
        return Block(BlockKind.UNSUPPORTED_ARCH, text, keyword=match.group(1))

    match = _LICENCE.match(text)
    if match:
        names = tuple(t for t in match.group(1).split() if t not in _STRUCTURE)
        return Block(BlockKind.LICENCE, text, licences=names)

    if text in _MASKS:
        return Block(BlockKind.PACKAGE_MASK, text)

    return Block(BlockKind.OTHER, text)


def inspect(cpv: str, repo: str = "", env: PortageEnv | None = None) -> Blockage:
    """Work out why *cpv* cannot be installed. An empty result means it can.

    ``getmaskingstatus`` is given the per-package clone rather than the shared
    configuration: it calls ``setcpv()`` itself whenever ``LICENSE`` carries a
    USE conditional, and the shared object is locked against exactly that.

    A failure here yields one :attr:`BlockKind.UNKNOWN` block, not an empty
    result. One unreadable ebuild still must not take the panel down with it,
    but "Portage would not answer" and "nothing is in the way" are opposite
    answers, and returning the second for the first is what kept this whole
    class of bug off the screen.
    """
    import portage  # noqa: PLC0415 — slow import, deferred

    env = env or _default_env()
    try:
        with env.configured(cpv) as settings:
            statuses = portage.getmaskingstatus(
                cpv, settings=settings, portdb=env.portdb, myrepo=repo or None
            )
    except Exception:  # pragma: no cover - broken ebuild metadata
        log.warning("Could not determine why %s is masked", cpv, exc_info=True)
        return Blockage(
            cpv=cpv, cp=_cp_of(cpv), repo=repo, blocks=(Block(BlockKind.UNKNOWN, ""),)
        )

    blocks = [_classify(str(status)) for status in statuses]
    blocks = [_enrich(block, cpv, repo, env) for block in blocks]
    return Blockage(
        cpv=cpv, cp=_cp_of(cpv), repo=repo, blocks=tuple(blocks)
    )


def _enrich(block: Block, cpv: str, repo: str, env: PortageEnv) -> Block:
    """Fill in what Portage's one-line status leaves out."""
    if block.kind is BlockKind.PACKAGE_MASK:
        comment, location = _masking_reason(cpv, repo, env)
        return Block(block.kind, block.raw, comment=comment, location=location)

    if block.kind is BlockKind.LICENCE and not block.licences:
        return Block(block.kind, block.raw, licences=licenses.missing_for(cpv, repo, env))

    return block


def _masking_reason(cpv: str, repo: str, env: PortageEnv) -> tuple[str, str]:
    """The maintainer's note, and the file it lives in."""
    import portage  # noqa: PLC0415

    try:
        answer = portage.getmaskingreason(
            cpv,
            settings=env.settings,
            portdb=env.portdb,
            myrepo=repo or None,
            return_location=True,
        )
    except Exception:  # pragma: no cover
        log.warning("Could not read the masking reason for %s", cpv, exc_info=True)
        return "", ""

    if not answer:
        return "", ""
    comment, location = answer if isinstance(answer, tuple) else (answer, "")
    return _tidy_comment(comment or ""), str(location or "")


def _tidy_comment(comment: str) -> str:
    """Strip the leading ``# `` that every line of a mask comment carries."""
    lines = [line.removeprefix("#").removeprefix(" ") for line in comment.splitlines()]
    return "\n".join(lines).strip()


def _cp_of(cpv: str) -> str:
    from portage.versions import cpv_getkey  # noqa: PLC0415

    return cpv_getkey(cpv) or cpv


# ---------------------------------------------------------------------------
# fixes
# ---------------------------------------------------------------------------


def fix_for(block: Block, cpv: str) -> Fix | None:
    """The change that would lift *block*, or ``None`` when there is none.

    Always version-specific: ``=cat/pkg-1.2`` and not ``cat/pkg``. Accepting a
    whole package for all time because one version was untested is how
    ``/etc/portage`` turns into a file nobody dares read.
    """
    atom = f"={cpv}"

    if block.kind is BlockKind.TESTING_KEYWORD:
        return Fix("package.accept_keywords", atom, (block.keyword,))

    if block.kind is BlockKind.MISSING_KEYWORD:
        return Fix(
            "package.accept_keywords",
            atom,
            ("**",),
            caution="untested-on-this-arch",
        )

    if block.kind is BlockKind.UNSUPPORTED_ARCH:
        # The ebuild says outright that it does not work here. A line would
        # silence Portage without making the package build.
        return Fix(
            "package.accept_keywords",
            atom,
            ("**",),
            advisable=False,
            caution="marked-broken-here",
        )

    if block.kind is BlockKind.PACKAGE_MASK:
        return Fix(
            "package.unmask", atom, (), advisable=False, caution="masked-on-purpose"
        )

    if block.kind is BlockKind.LICENCE and block.licences:
        return Fix("package.license", atom, block.licences)

    return None


def fixes_for(blockage: Blockage) -> tuple[Fix, ...]:
    """One fix per block, in the order the blocks should be presented."""
    ordered = sorted(
        blockage.blocks,
        key=lambda block: 0 if block is blockage.primary else 1,
    )
    return tuple(
        fix for fix in (fix_for(block, blockage.cpv) for block in ordered) if fix is not None
    )
