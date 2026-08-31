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

"""Tests for reading and changing ``make.conf``, and for the profile list.

The promise this file has to keep is narrow and important: a change replaces one
line and leaves everything else — comments, ordering, blank lines — byte for
byte. Most of these tests are that promise, written down.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gentstore.core import makeconf, profiles
from gentstore.core.cfgfiles import DiffKind
from gentstore.runner import eselect

SAMPLE = '''# These settings were set by the catalyst build script that automatically
# built this stage.
COMMON_FLAGS="-march=native -O2 -pipe"
CFLAGS="${COMMON_FLAGS}"

# Two jobs per core was too many on this box; see bug 12345.
MAKEOPTS="-j4 -l4"
VIDEO_CARDS="amdgpu radeonsi"
ACCEPT_LICENSE=@FREE

# NOTE: this stage was built with the bindist USE flag enabled
LC_MESSAGES=C.UTF-8
'''


@pytest.fixture
def conf(tmp_path: Path) -> makeconf.MakeConf:
    path = tmp_path / "make.conf"
    path.write_text(SAMPLE, encoding="utf-8")
    return makeconf.load(path=path)


# -- reading ----------------------------------------------------------------


def test_assignments_are_found_with_their_line_numbers(conf) -> None:
    makeopts = conf.get("MAKEOPTS")
    assert makeopts.value == "-j4 -l4"
    assert makeopts.line_number == 7
    assert makeopts.quote == '"'


def test_an_unquoted_value_is_read_as_written(conf) -> None:
    assert conf.get("ACCEPT_LICENSE").value == "@FREE"
    assert conf.get("ACCEPT_LICENSE").quote == '"', "a missing quote is added on write"


def test_comments_are_not_mistaken_for_assignments(conf) -> None:
    assert not conf.defines("NOTE")
    assert not conf.defines("These")


def test_a_variable_the_file_does_not_mention(conf) -> None:
    assert conf.get("USE") is None
    assert conf.value("USE", "nothing") == "nothing"


def test_a_missing_file_is_a_valid_empty_answer(tmp_path: Path) -> None:
    conf = makeconf.load(path=tmp_path / "absent")
    assert not conf.exists
    assert conf.assignments == {}


def test_the_last_assignment_wins_as_it_does_in_the_shell() -> None:
    parsed = makeconf.parse('MAKEOPTS="-j2"\nMAKEOPTS="-j8"\n')
    assert parsed["MAKEOPTS"].value == "-j8"
    assert parsed["MAKEOPTS"].line_number == 2


def test_a_trailing_comment_is_not_part_of_the_value() -> None:
    parsed = makeconf.parse('MAKEOPTS="-j4"  # was -j8\n')
    assert parsed["MAKEOPTS"].value == "-j4"


def test_a_hash_inside_quotes_stays_in_the_value() -> None:
    parsed = makeconf.parse('EMERGE_DEFAULT_OPTS="--quiet #1"\n')
    assert parsed["EMERGE_DEFAULT_OPTS"].value == "--quiet #1"


def test_an_assignment_spanning_several_lines_is_flagged_not_guessed() -> None:
    parsed = makeconf.parse('USE="X \\\n  wayland"\n')
    assert parsed["USE"].continued
    assert not parsed["USE"].is_editable


def test_a_quote_left_open_also_counts_as_continued() -> None:
    parsed = makeconf.parse('USE="X\n  wayland"\n')
    assert not parsed["USE"].is_editable


# -- the change -------------------------------------------------------------


def test_changing_a_value_replaces_exactly_one_line(conf) -> None:
    plan = makeconf.plan_set(conf, "MAKEOPTS", "-j16 -l16")
    assert plan.op == "replace_line"
    assert plan.previous == 'MAKEOPTS="-j4 -l4"'
    assert plan.line == 'MAKEOPTS="-j16 -l16"'


def test_the_pattern_is_anchored_so_a_comment_cannot_match(conf) -> None:
    """"# was MAKEOPTS=…" in a comment must not be the line replaced."""
    plan = makeconf.plan_set(conf, "MAKEOPTS", "-j1")
    assert plan.match == r"^\s*MAKEOPTS="


def test_a_variable_the_file_lacks_is_appended(conf) -> None:
    plan = makeconf.plan_set(conf, "USE", "X wayland")
    assert plan.op == "append_line"
    assert plan.line == 'USE="X wayland"'


def test_setting_a_value_to_what_it_already_is_does_nothing(conf) -> None:
    assert makeconf.plan_set(conf, "MAKEOPTS", "-j4 -l4").is_noop


def test_a_multi_line_assignment_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "make.conf"
    path.write_text('USE="X \\\n  wayland"\n', encoding="utf-8")
    conf = makeconf.load(path=path)
    assert makeconf.plan_set(conf, "USE", "X").is_noop


def test_the_existing_quoting_style_is_kept(tmp_path: Path) -> None:
    path = tmp_path / "make.conf"
    path.write_text("MAKEOPTS='-j4'\n", encoding="utf-8")
    conf = makeconf.load(path=path)
    assert makeconf.plan_set(conf, "MAKEOPTS", "-j8").line == "MAKEOPTS='-j8'"


def test_indentation_is_kept(tmp_path: Path) -> None:
    path = tmp_path / "make.conf"
    path.write_text('  MAKEOPTS="-j4"\n', encoding="utf-8")
    conf = makeconf.load(path=path)
    assert makeconf.plan_set(conf, "MAKEOPTS", "-j8").line == '  MAKEOPTS="-j8"'


# -- the preview ------------------------------------------------------------


def test_the_preview_shows_one_removal_and_one_addition(conf) -> None:
    plan = makeconf.plan_set(conf, "MAKEOPTS", "-j16 -l16")
    lines = makeconf.preview(conf, plan)

    removed = [line.text for line in lines if line.kind is DiffKind.REMOVED]
    added = [line.text for line in lines if line.kind is DiffKind.ADDED]
    assert removed == ['-MAKEOPTS="-j4 -l4"']
    assert added == ['+MAKEOPTS="-j16 -l16"']


def test_the_comment_above_the_line_survives_the_change(conf) -> None:
    """The whole point: somebody's note about why MAKEOPTS is what it is."""
    plan = makeconf.plan_set(conf, "MAKEOPTS", "-j16 -l16")
    lines = makeconf.preview(conf, plan)
    context = [line.text for line in lines if line.kind is DiffKind.CONTEXT]
    assert any("bug 12345" in line for line in context)
    assert not any(
        "bug 12345" in line.text
        for line in lines
        if line.kind in (DiffKind.ADDED, DiffKind.REMOVED)
    )


def test_appending_shows_up_at_the_end(conf) -> None:
    plan = makeconf.plan_set(conf, "USE", "X")
    added = [line.text for line in makeconf.preview(conf, plan) if line.kind is DiffKind.ADDED]
    assert added == ['+USE="X"']


# -- the suggestions --------------------------------------------------------


def test_makeopts_is_suggested_from_the_hardware() -> None:
    suggestion = makeconf.suggest_makeopts()
    assert suggestion.is_available
    assert suggestion.value.startswith("-j")
    assert suggestion.reason in ("cores", "memory")


def test_memory_caps_the_number_of_jobs(monkeypatch) -> None:
    """A 64-core machine with 8 GiB cannot run 64 compiles at once."""
    monkeypatch.setattr(makeconf.os, "sched_getaffinity", lambda _pid: set(range(64)))
    monkeypatch.setattr(makeconf, "_total_memory_gib", lambda: 8.0)
    suggestion = makeconf.suggest_makeopts()
    assert suggestion.value == "-j4 -l64"
    assert suggestion.reason == "memory"


def test_plenty_of_memory_means_one_job_per_core(monkeypatch) -> None:
    monkeypatch.setattr(makeconf.os, "sched_getaffinity", lambda _pid: set(range(4)))
    monkeypatch.setattr(makeconf, "_total_memory_gib", lambda: 64.0)
    suggestion = makeconf.suggest_makeopts()
    assert suggestion.value == "-j4 -l4"
    assert suggestion.reason == "cores"


def test_a_missing_optional_tool_is_an_answer_not_an_error(monkeypatch) -> None:
    import shutil

    monkeypatch.setattr(shutil, "which", lambda _name: None)
    suggestion = makeconf.suggest_cpu_flags()
    assert not suggestion.is_available
    assert suggestion.missing == makeconf.CPUID_PACKAGE


# -- profiles ---------------------------------------------------------------

PROFILE_LIST = """Available profile symlink targets:
  [1]   default/linux/amd64/23.0 (stable)
  [3]   default/linux/amd64/23.0/desktop (stable)
  [7]   default/linux/amd64/23.0/desktop/plasma (stable) *
  [52]  default/linux/amd64/23.0/split-usr/musl/llvm (exp)
  [53]  default/linux/amd64/23.0/no-multilib/hardened (dev)
"""


def test_the_profile_list_is_read_with_its_numbering() -> None:
    found = profiles.parse(PROFILE_LIST)
    assert [item.index for item in found] == [1, 3, 7, 52, 53]
    assert found[0].path == "default/linux/amd64/23.0"


def test_the_current_profile_is_the_starred_one() -> None:
    current = profiles.current(profiles.parse(PROFILE_LIST))
    assert current.index == 7
    assert current.path.endswith("desktop/plasma")


def test_stability_is_read_and_only_stable_counts_as_stable() -> None:
    found = {item.index: item for item in profiles.parse(PROFILE_LIST)}
    assert found[1].is_stable
    assert not found[52].is_stable
    assert found[52].stability == "exp"


def test_the_family_and_the_variant_are_told_apart() -> None:
    found = {item.index: item for item in profiles.parse(PROFILE_LIST)}
    assert found[7].family == "default/linux/amd64/23.0"
    assert found[7].variant == "desktop/plasma"
    assert found[1].variant == "—"


def test_filtering_finds_by_any_part_of_the_path() -> None:
    found = profiles.parse(PROFILE_LIST)
    assert [item.index for item in profiles.search(found, "plasma")] == [7]
    assert [item.index for item in profiles.search(found, "hardened")] == [53]
    assert len(profiles.search(found, "")) == len(found)


def test_colour_escapes_do_not_confuse_the_parser() -> None:
    coloured = "  [7]   \x1b[32;01mdefault/linux/amd64/23.0\x1b[39;49;00m (stable) *"
    (item,) = profiles.parse(coloured)
    assert item.index == 7
    assert item.current


def test_listing_profiles_needs_no_privileges_but_setting_one_does() -> None:
    assert not eselect.list_profiles().privileged
    assert eselect.set_profile(7).privileged
    assert eselect.set_profile(7).argv == ("eselect", "profile", "set", "7")


# -- against the real file --------------------------------------------------


def test_the_machines_own_make_conf_parses() -> None:
    from gentstore.core.portage_env import PortageUnavailableError, env

    try:
        environment = env()
    except PortageUnavailableError as exc:  # pragma: no cover - non-Gentoo host
        pytest.skip(f"no usable Portage installation: {exc}")

    conf = makeconf.load(environment)
    if not conf.exists:  # pragma: no cover - a system without make.conf
        pytest.skip("this machine has no make.conf")
    assert conf.assignments
    for assignment in conf.assignments.values():
        assert assignment.raw in conf.lines, "every assignment must point at a real line"


def test_what_portage_uses_and_what_the_file_says_are_asked_separately() -> None:
    """FEATURES comes from the profile as well, and conflating them misleads."""
    from gentstore.core.portage_env import PortageUnavailableError, env

    try:
        environment = env()
    except PortageUnavailableError as exc:  # pragma: no cover
        pytest.skip(f"no usable Portage installation: {exc}")

    conf = makeconf.load(environment)
    from_portage = makeconf.effective("FEATURES", environment)
    assert from_portage, "Portage always has a FEATURES value"

    # The file may or may not set it; what matters is that the two are read
    # from different places, so a screen can show both and say which is which.
    from_file = conf.value("FEATURES")
    if not conf.defines("FEATURES"):
        assert from_file == ""
        assert from_portage != from_file, "the profile contributes even with no line here"
