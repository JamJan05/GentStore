"""Tests for why a package is blocked, and for the line that unblocks it.

The classification is driven entirely by Portage's own wording, so most of these
pin that wording down: if a future Portage changes "~amd64 keyword" to something
else, this is where it should be noticed, rather than in an interface that
quietly falls back to "Portage will not install this version".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gentstore.core import confedit, licenses
from gentstore.core.masking import (
    Block,
    Blockage,
    BlockKind,
    _classify,
    _tidy_comment,
    fix_for,
    inspect,
)
from gentstore.core.portage_env import PortageUnavailableError, env

# -- reading Portage's wording ---------------------------------------------


@pytest.mark.parametrize(
    ("raw", "kind", "keyword"),
    [
        ("~amd64 keyword", BlockKind.TESTING_KEYWORD, "~amd64"),
        ("~arm64 keyword", BlockKind.TESTING_KEYWORD, "~arm64"),
        ("missing keyword", BlockKind.MISSING_KEYWORD, "**"),
        ("-amd64 keyword", BlockKind.UNSUPPORTED_ARCH, "-amd64"),
        ("-* keyword", BlockKind.UNSUPPORTED_ARCH, "-*"),
    ],
)
def test_keyword_blocks_are_told_apart(raw: str, kind: BlockKind, keyword: str) -> None:
    block = _classify(raw)
    assert block.kind is kind
    assert block.keyword == keyword


def test_a_package_mask_is_recognised() -> None:
    assert _classify("package.mask").kind is BlockKind.PACKAGE_MASK
    assert _classify("profile").kind is BlockKind.PACKAGE_MASK


def test_licence_names_are_pulled_out_of_the_message() -> None:
    block = _classify("BUSL-1.1 Microsoft-vscode license(s)")
    assert block.kind is BlockKind.LICENCE
    assert block.licences == ("BUSL-1.1", "Microsoft-vscode")


def test_a_check_that_failed_does_not_read_as_a_package_that_is_fine() -> None:
    """The distinction the whole ``unknown`` kind exists for."""
    unchecked = Blockage(
        cpv="a/b-1", cp="a/b", repo="", blocks=(Block(BlockKind.UNKNOWN, ""),)
    )
    clean = Blockage(cpv="a/b-1", cp="a/b", repo="", blocks=())

    assert unchecked.is_blocked and not clean.is_blocked
    assert unchecked.primary.kind is BlockKind.UNKNOWN
    assert fix_for(unchecked.primary, "a/b-1") is None, "there is nothing to offer"


def test_an_unfamiliar_reason_is_kept_verbatim() -> None:
    block = _classify("EAPI 9 is not supported")
    assert block.kind is BlockKind.OTHER
    assert block.raw == "EAPI 9 is not supported"


def test_the_hash_marks_are_stripped_from_a_mask_comment() -> None:
    comment = "# Sam James <sam@gentoo.org> (2026-08-21)\n# Grave security vulnerabilities\n"
    assert _tidy_comment(comment) == (
        "Sam James <sam@gentoo.org> (2026-08-21)\nGrave security vulnerabilities"
    )


def test_the_most_serious_reason_is_the_one_led_with() -> None:
    """A package that is both hard-masked and untested is a hard-mask story."""
    blockage = Blockage(
        cpv="a/b-1",
        cp="a/b",
        repo="gentoo",
        blocks=(
            Block(BlockKind.MISSING_KEYWORD, "missing keyword", keyword="**"),
            Block(BlockKind.PACKAGE_MASK, "package.mask"),
        ),
    )
    assert blockage.primary.kind is BlockKind.PACKAGE_MASK


def test_nothing_blocking_means_nothing_to_show() -> None:
    blockage = Blockage(cpv="a/b-1", cp="a/b", repo="gentoo", blocks=())
    assert not blockage.is_blocked
    assert blockage.primary is None


# -- the fixes --------------------------------------------------------------


@pytest.mark.parametrize(
    ("block", "file_name", "tokens", "advisable"),
    [
        (
            Block(BlockKind.TESTING_KEYWORD, "~amd64 keyword", keyword="~amd64"),
            "package.accept_keywords",
            ("~amd64",),
            True,
        ),
        (
            Block(BlockKind.MISSING_KEYWORD, "missing keyword", keyword="**"),
            "package.accept_keywords",
            ("**",),
            True,
        ),
        (
            Block(BlockKind.UNSUPPORTED_ARCH, "-amd64 keyword", keyword="-amd64"),
            "package.accept_keywords",
            ("**",),
            False,
        ),
        (Block(BlockKind.PACKAGE_MASK, "package.mask"), "package.unmask", (), False),
        (
            Block(BlockKind.LICENCE, "BUSL-1.1 license(s)", licences=("BUSL-1.1",)),
            "package.license",
            ("BUSL-1.1",),
            True,
        ),
    ],
)
def test_each_kind_of_block_has_its_own_file(block, file_name, tokens, advisable) -> None:
    fix = fix_for(block, "app-admin/vault-1.18.4")
    assert fix is not None
    assert fix.file == file_name
    assert fix.tokens == tokens
    assert fix.advisable is advisable


def test_a_fix_is_always_pinned_to_one_version() -> None:
    """cat/pkg would accept every future version too, which nobody asked for."""
    fix = fix_for(_classify("~amd64 keyword"), "dev-libs/zydis-4.1.1")
    assert fix.atom == "=dev-libs/zydis-4.1.1"
    assert fix.line == "=dev-libs/zydis-4.1.1 ~amd64"


def test_there_is_no_fix_for_a_reason_we_do_not_understand() -> None:
    assert fix_for(_classify("EAPI 9 is not supported"), "a/b-1") is None


def test_the_two_dangerous_fixes_carry_a_caution() -> None:
    for raw in ("-amd64 keyword", "package.mask"):
        fix = fix_for(_classify(raw), "a/b-1")
        assert not fix.advisable
        assert fix.caution


# -- the files --------------------------------------------------------------


def test_an_entry_is_looked_up_by_atom_not_by_package(tmp_path: Path) -> None:
    """accept_keywords entries are version-specific; the file name is not."""
    directory = tmp_path / "package.accept_keywords"
    directory.mkdir()
    (directory / "zydis").write_text("=dev-libs/zydis-4.1.1 ~amd64\n", encoding="utf-8")

    path, kind, existing = confedit.locate(
        "package.accept_keywords",
        "dev-libs/zydis",
        config_dir=tmp_path,
        entry="=dev-libs/zydis-4.1.1",
    )
    assert path == directory / "zydis"
    assert kind is confedit.TargetKind.EXISTING
    assert existing == "=dev-libs/zydis-4.1.1 ~amd64"


def test_a_different_version_gets_its_own_line(tmp_path: Path) -> None:
    directory = tmp_path / "package.accept_keywords"
    directory.mkdir()
    (directory / "zydis").write_text("=dev-libs/zydis-4.1.1 ~amd64\n", encoding="utf-8")

    plan = confedit.plan_entry(
        "package.accept_keywords",
        "dev-libs/zydis",
        "=dev-libs/zydis-4.2.0",
        ("~amd64",),
        config_dir=tmp_path,
    )
    assert plan.op == "append_line"


def test_accepting_the_same_thing_twice_is_a_no_op(tmp_path: Path) -> None:
    directory = tmp_path / "package.license"
    directory.mkdir()
    (directory / "vault").write_text("=app-admin/vault-1.18.4 BUSL-1.1\n", encoding="utf-8")

    plan = confedit.plan_entry(
        "package.license",
        "app-admin/vault",
        "=app-admin/vault-1.18.4",
        ("BUSL-1.1",),
        config_dir=tmp_path,
    )
    assert plan.is_noop


def test_an_entry_can_be_taken_back_out(tmp_path: Path) -> None:
    directory = tmp_path / "package.unmask"
    directory.mkdir()
    (directory / "croc").write_text("# mine\n=acct-group/croc-0-r2\n", encoding="utf-8")

    plan = confedit.plan_removal(
        "package.unmask", "acct-group/croc", "=acct-group/croc-0-r2", config_dir=tmp_path
    )
    assert plan.op == "remove_line"
    assert plan.previous == "=acct-group/croc-0-r2"


def test_removing_something_that_is_not_there_plans_nothing(tmp_path: Path) -> None:
    (tmp_path / "package.unmask").mkdir()
    plan = confedit.plan_removal(
        "package.unmask", "a/b", "=a/b-1", config_dir=tmp_path
    )
    assert plan.is_noop


def test_reading_a_file_back_skips_comments_and_blanks(tmp_path: Path) -> None:
    directory = tmp_path / "package.accept_keywords"
    directory.mkdir()
    (directory / "one").write_text("# a note\n\na/b ~amd64\n", encoding="utf-8")
    (directory / "two").write_text("c/d ~amd64\n", encoding="utf-8")

    entries = confedit.read_entries("package.accept_keywords", config_dir=tmp_path)
    assert [line for _path, line in entries] == ["a/b ~amd64", "c/d ~amd64"]


def test_reading_a_missing_file_is_simply_empty(tmp_path: Path) -> None:
    assert confedit.read_entries("package.unmask", config_dir=tmp_path) == ()


@pytest.mark.parametrize(
    ("atom", "expected"),
    [
        ("=media-video/mpv-0.41.0-r2", "media-video/mpv"),
        (">=media-video/mpv-0.40", "media-video/mpv"),
        ("media-video/mpv", "media-video/mpv"),
    ],
)
def test_the_package_is_recovered_from_the_atom(atom: str, expected: str) -> None:
    assert confedit.cp_from_atom(atom) == expected


# -- against the real system ------------------------------------------------


@pytest.fixture(scope="session")
def portage_env():
    try:
        return env()
    except PortageUnavailableError as exc:  # pragma: no cover - non-Gentoo host
        pytest.skip(f"no usable Portage installation: {exc}")


def find_blocked(portage_env, kind: BlockKind) -> Blockage | None:
    """The first package on this machine blocked in a particular way."""
    for cp in portage_env.portdb.cp_all()[::11]:
        for cpv in portage_env.portdb.cp_list(cp):
            blockage = inspect(str(cpv), getattr(cpv, "repo", ""), portage_env)
            if blockage.primary is not None and blockage.primary.kind is kind:
                return blockage
    return None


def test_a_stable_installable_package_is_not_blocked(portage_env) -> None:
    best = portage_env.portdb.xmatch("bestmatch-visible", "sys-apps/portage")
    assert best, "sys-apps/portage must be visible for Portage to work at all"
    assert not inspect(str(best), env=portage_env).is_blocked


def test_a_testing_package_reports_the_keyword_and_the_line(portage_env) -> None:
    blockage = find_blocked(portage_env, BlockKind.TESTING_KEYWORD)
    if blockage is None:  # pragma: no cover - a fully stable tree
        pytest.skip("nothing on this machine is blocked by a testing keyword")

    block = blockage.primary
    assert block.keyword.startswith("~")
    fix = fix_for(block, blockage.cpv)
    assert fix.line == f"={blockage.cpv} {block.keyword}"


def test_a_masked_package_carries_the_maintainers_own_words(portage_env) -> None:
    blockage = find_blocked(portage_env, BlockKind.PACKAGE_MASK)
    if blockage is None:  # pragma: no cover
        pytest.skip("nothing on this machine is hard-masked")

    block = blockage.primary
    assert block.comment, "a mask without its comment is the useless half of the answer"
    assert not block.comment.startswith("#"), "the comment markers should be gone"
    assert block.location.endswith("package.mask")


def test_a_licence_block_names_the_licence_that_is_missing(portage_env) -> None:
    blockage = find_blocked(portage_env, BlockKind.LICENCE)
    if blockage is None:  # pragma: no cover - a system accepting everything
        pytest.skip("this system accepts every licence in the tree")

    block = blockage.primary
    assert block.licences
    for name in block.licences:
        assert not licenses.describe(name, portage_env).is_free


def test_licence_groups_are_resolved_through_their_nesting(portage_env) -> None:
    """@FREE is built out of other groups, so membership is not a literal read."""
    mit = licenses.describe("MIT", portage_env)
    assert mit.is_free
    assert mit.has_text


def test_the_licence_check_agrees_with_the_masking_status(portage_env) -> None:
    """Two different Portage entry points, one answer.

    ``getmaskingstatus`` names the licences in a sentence; ``getMissingLicenses``
    returns them as a list. The interface reads the first and falls back to the
    second, so they had better say the same thing.
    """
    blockage = find_blocked(portage_env, BlockKind.LICENCE)
    if blockage is None:  # pragma: no cover - a system accepting everything
        pytest.skip("this system accepts every licence in the tree")

    from_status = set(blockage.primary.licences)
    from_manager = set(licenses.missing_for(blockage.cpv, blockage.repo, portage_env))
    assert from_status == from_manager
