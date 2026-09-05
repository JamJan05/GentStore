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

"""Tests for regrouping one ``emerge --autounmask`` run into a plan.

Three of these read output recorded from a real machine rather than hand-written
text, because the shape of that output is the entire input to this module and a
fixture somebody typed from memory tests the memory. ``tests/fixtures/`` holds
what ``emerge`` actually printed for a package that needs fourteen keywords, for
a slot conflict, and for a run with nothing to say.

The one behaviour worth stating twice: a plan that could not be read must never
look like a plan with nothing to do. Both have no lines in them, and only one of
them means the package can be built.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gentstore.core import install_plan

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / f"{name}.txt").read_text(encoding="utf-8")


@pytest.fixture
def hyprland() -> install_plan.InstallPlan:
    return install_plan.from_output(fixture("pretend-autounmask-hyprland"))


# -- a real refusal ---------------------------------------------------------


def test_a_real_autounmask_block_becomes_one_group(hyprland) -> None:  # noqa: ANN001
    """Fourteen keywords for one window manager, in one place.

    This is the case the whole feature is for: not one refusal, but every
    refusal Portage could see in a single run, and none of them about the
    package the user actually chose.
    """
    assert [group.file for group in hyprland.groups] == ["package.accept_keywords"]
    assert len(hyprland) == 14
    assert hyprland.can_apply


def test_every_line_is_carried_through_exactly(hyprland) -> None:  # noqa: ANN001
    """Portage's proposal, byte for byte.

    Nothing here rebuilds an atom out of its parts or tidies ``=`` into ``>=``.
    A preview that shows one line and writes another is worse than no preview,
    and the line is the only thing the user is being asked to agree to.
    """
    lines = [entry.line for entry in hyprland.entries]
    for line in lines:
        assert line in fixture("pretend-autounmask-hyprland")
    assert "=gui-wm/hyprland-0.56.2 ~amd64" in lines


def test_each_line_says_who_asked_for_it(hyprland) -> None:  # noqa: ANN001
    """The ``# required by`` chain, with emerge's own bookkeeping removed."""
    entry = next(e for e in hyprland.entries if e.atom == "=gui-libs/hyprtoolkit-0.5.4")
    assert entry.reasons[0] == "gui-libs/hyprland-guiutils-0.2.2::hyproverlay"
    assert not any("(argument)" in reason for reason in entry.reasons)
    assert not any(reason.startswith("required by") for reason in entry.reasons)


def test_the_merge_list_is_counted(hyprland) -> None:  # noqa: ANN001
    """The summary line: 26 new packages and 2 upgrades, from the rows."""
    assert (hyprland.new, hyprland.updates) == (26, 2)
    assert (hyprland.downgrades, hyprland.removals) == (0, 0)


# -- the provisional case ---------------------------------------------------


def test_a_conflict_beside_changes_does_not_withdraw_the_offer(hyprland) -> None:  # noqa: ANN001
    """Portage gave up backtracking early, and says so.

    The blocker it reports was worked out *before* these fourteen lines existed,
    so treating it as a verdict would refuse to help with exactly the case this
    screen is for. The lines are still offered; the conflict is still shown; the
    install gate stays shut until a later run says otherwise.
    """
    assert hyprland.stopped_early
    assert hyprland.conflicts
    assert hyprland.is_provisional
    assert hyprland.can_apply
    assert not hyprland.is_ready


def test_an_unresolvable_graph_offers_nothing() -> None:
    """A slot conflict with no changes to make: there is nothing to apply."""
    plan = install_plan.from_output(fixture("pretend-conflict"))

    assert plan.conflicts
    assert not plan.can_apply
    assert not plan.is_ready
    assert not plan.is_provisional
    assert any("slot conflict" in line for line in plan.conflicts)


def test_a_block_portage_worked_out_for_itself_is_not_a_conflict() -> None:
    """``[blocks b ]`` and ``[blocks B ]`` look alike and mean opposite things.

    Portage writes the letter in lower case when the block is satisfied and in
    upper case when it is not (``_emerge/resolver/output.py``), and says which in
    its summary: ``Conflict: 1 block (all satisfied)``. This run lists a block
    *and* asks for one keyword — treating the block as an unresolved graph would
    withdraw the very line that makes the install work.
    """
    plan = install_plan.from_output(fixture("pretend-block-satisfied"))

    assert plan.conflicts == ()
    assert plan.can_apply
    assert [entry.line for entry in plan.entries] == ["=dev-libs/wayland-1.26.0 ~amd64"]


def test_a_block_portage_could_not_work_out_is_a_conflict(hyprland) -> None:  # noqa: ANN001
    """The other letter, from the same shape of row."""
    assert [row.flags for row in hyprland_rows()] == ["B"]
    assert hyprland.conflicts


def hyprland_rows():  # noqa: ANN201 - the blocker rows of that fixture
    from gentstore.core.emerge_parse import parse_pretend

    return parse_pretend(fixture("pretend-autounmask-hyprland")).unsatisfied_blockers


def test_a_successful_run_that_prints_three_exclamation_marks_is_not_a_conflict() -> None:
    """The bug this test exists for, in Portage's own words.

    An ordinary ``@world`` update resolves the graph, prints its merge list,
    exits zero — and says on the way past::

        !!! The following update(s) have been skipped due to unsatisfied
        !!! dependencies triggered by backtracking:

    Reading every ``!!!`` line as an unresolved graph turned that into "Portage
    cannot resolve this", announced over a run that had just worked. What counts
    is the specific things Portage prints when it genuinely has no answer, not
    the three characters it decorates half its output with.
    """
    plan = install_plan.from_output(fixture("pretend-world-skipped"))

    assert plan.conflicts == ()
    assert not plan.is_provisional
    assert plan.updates, "and the merge list was read: the run did resolve"


# -- the two quiet cases ----------------------------------------------------


def test_a_clean_run_opens_the_gate() -> None:
    """Nothing to write, nothing conflicting, and something was understood."""
    plan = install_plan.from_output(fixture("pretend-clean"))

    assert plan.is_ready
    assert not plan.can_apply
    assert not plan.unreadable


@pytest.mark.parametrize(
    "text",
    [
        "",
        "\n\n",
        "bash: emerge: command not found\n",
        "Traceback (most recent call last):\n  File \"/usr/bin/emerge\"\n",
    ],
)
def test_output_that_could_not_be_read_never_looks_ready(text: str) -> None:
    """The distinction the whole gate rests on.

    "Nothing to do" and "nothing came back" both produce a plan with no lines in
    it, and only the first of them means the package can be built. A check that
    failed must not be mistaken for a check that passed.
    """
    plan = install_plan.from_output(text)

    assert plan.unreadable
    assert not plan.is_ready
    assert not plan.can_apply


# -- the arranging it does --------------------------------------------------


def test_one_line_asked_for_twice_is_one_entry_with_both_reasons() -> None:
    """Portage prints a line once per chain that leads to it."""
    plan = install_plan.from_output(
        """
The following keyword changes are necessary to proceed:
# required by gui-wm/hyprland-0.56.2::hyproverlay
=dev-libs/aquamarine-0.14.0 ~amd64
# required by gui-libs/hyprtoolkit-0.5.4::hyproverlay
=dev-libs/aquamarine-0.14.0 ~amd64
"""
    )

    assert len(plan) == 1
    assert plan.entries[0].reasons == (
        "gui-wm/hyprland-0.56.2::hyproverlay",
        "gui-libs/hyprtoolkit-0.5.4::hyproverlay",
    )


def test_the_same_atom_with_different_tokens_stays_two_entries() -> None:
    """``~amd64`` and ``**`` are two different requests about one package."""
    plan = install_plan.from_output(
        "The following keyword changes are necessary to proceed:\n"
        "=cat/pkg-1 ~amd64\n"
        "=cat/pkg-1 **\n"
    )
    assert [entry.line for entry in plan.entries] == ["=cat/pkg-1 ~amd64", "=cat/pkg-1 **"]


def test_the_groups_come_in_a_fixed_order() -> None:
    """Keywords first because they are mildest, unmasking last because it is not."""
    plan = install_plan.from_output(
        "The following mask changes are necessary to proceed:\n"
        "=cat/masked-1\n"
        "\n"
        "The following USE changes are necessary to proceed:\n"
        "cat/pkg flag\n"
        "\n"
        "The following keyword changes are necessary to proceed:\n"
        "=cat/pkg-1 ~amd64\n"
    )
    assert [group.file for group in plan.groups] == [
        "package.accept_keywords",
        "package.use",
        "package.unmask",
    ]
    assert plan.group("package.unmask").is_unmask


def test_a_required_use_conflict_produces_no_line() -> None:
    """No entry in /etc/portage settles a package's flags contradicting itself.

    :mod:`gentstore.core.emerge_parse` already maps that block to no file; this
    is the half that matters here — it must not turn into a group of one empty
    line, and it must not open the gate either.
    """
    plan = install_plan.from_output(
        "The following REQUIRED_USE flag constraints are unsatisfied:\n"
        "  exactly-one-of ( qt5 qt6 )\n"
    )
    assert plan.groups == ()
    assert not plan.can_apply


@pytest.mark.parametrize(
    ("line", "unkeyworded", "live"),
    [
        ("=cat/pkg-1.2 ~amd64", False, False),
        ("=cat/pkg-1.2 **", True, False),
        ("=cat/pkg-9999 **", True, True),
        ("=cat/pkg-9999::overlay **", True, True),
        ("=cat/pkg-99999999 ~amd64", False, True),
    ],
)
def test_the_two_that_are_not_routine_are_marked(
    line: str, unkeyworded: bool, live: bool
) -> None:
    """``**`` and ``9999`` never disappear into a count of "8 keywords"."""
    plan = install_plan.from_output(
        f"The following keyword changes are necessary to proceed:\n{line}\n"
    )
    entry = plan.entries[0]
    assert entry.is_unkeyworded is unkeyworded
    assert entry.is_live is live
    assert entry.is_ordinary is not (unkeyworded or live)
