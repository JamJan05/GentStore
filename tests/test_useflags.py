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

"""Tests for the USE flag layer: the parser, the provenance and the write plan.

The pure logic — parsing ``REQUIRED_USE``, deciding which flags belong in a
``package.use`` line, walking a dependency string — runs anywhere. The rest asks
the machine's own Portage about ``media-video/mpv``, because the interesting
mistakes in this area are all of the form "the API answered, just not the
question I thought I was asking".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gentstore.core import confedit, useflags
from gentstore.core import depgraph_hints as hints
from gentstore.core import required_use as ru
from gentstore.core.useflags import FlagLock, FlagSource, UseFlag, UseState

# -- REQUIRED_USE: parsing --------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "flag",
        "!flag",
        "|| ( a b )",
        "^^ ( a b c )",
        "?? ( a b )",
        "a? ( b )",
        "!a? ( b c )",
        "a? ( || ( b c ) )",
        "^^ ( a b ) || ( c d ) e? ( f )",
    ],
)
def test_expressions_survive_a_round_trip(text: str) -> None:
    """Rendered back, an expression must read the way the ebuild wrote it."""
    assert " ".join(node.render() for node in ru.parse(text)) == text


@pytest.mark.parametrize("text", ["|| ( a b", "|| a b )", ")", "a? b", "|| ("])
def test_a_malformed_expression_is_an_error_not_an_empty_list(text: str) -> None:
    """Silently ignoring a broken rule would let an invalid choice be written."""
    with pytest.raises(ru.RequiredUseError):
        ru.parse(text)


def test_an_empty_expression_has_no_requirements() -> None:
    assert ru.check("", ["anything"]) == ()


# -- REQUIRED_USE: evaluating ----------------------------------------------


@pytest.mark.parametrize(
    ("text", "use", "expected"),
    [
        ("flag", ["flag"], True),
        ("flag", [], False),
        ("!flag", [], True),
        ("!flag", ["flag"], False),
        ("|| ( a b )", ["b"], True),
        ("|| ( a b )", [], False),
        ("^^ ( a b )", ["a"], True),
        ("^^ ( a b )", ["a", "b"], False),
        ("^^ ( a b )", [], False),
        ("?? ( a b )", [], True),
        ("?? ( a b )", ["a"], True),
        ("?? ( a b )", ["a", "b"], False),
        ("a? ( b )", ["a", "b"], True),
        ("a? ( b )", ["a"], False),
        ("a? ( b )", [], True),
        ("!a? ( b )", [], False),
    ],
)
def test_requirements_are_evaluated_the_way_portage_would(text, use, expected) -> None:
    assert all(item.satisfied for item in ru.check(text, use)) is expected


def test_a_dormant_conditional_is_neither_met_nor_broken() -> None:
    """``vulkan? ( X )`` with vulkan off says nothing, and must not show a tick."""
    (requirement,) = ru.check("vulkan? ( X )", [])
    assert requirement.satisfied
    assert not requirement.applies
    assert not requirement.is_broken


def test_broken_requirements_are_the_ones_worth_showing() -> None:
    text = "|| ( cli libmpv ) vulkan? ( || ( X wayland ) ) test? ( cli )"
    requirements = ru.check(text, ["vulkan"])
    failures = [item.expression for item in ru.broken(requirements)]
    assert failures == ["|| ( cli libmpv )", "vulkan? ( || ( X wayland ) )"]


def test_nested_groups_evaluate_from_the_inside_out() -> None:
    text = "a? ( ^^ ( b c ) )"
    assert ru.check(text, ["a", "b"])[0].satisfied
    assert not ru.check(text, ["a", "b", "c"])[0].satisfied


def test_every_flag_in_a_rule_is_reported_including_the_condition() -> None:
    (requirement,) = ru.check("vulkan? ( || ( X wayland ) )", [])
    assert requirement.flags == frozenset({"vulkan", "X", "wayland"})


# -- dependency hints -------------------------------------------------------


def test_a_conditional_group_is_attributed_to_its_flag() -> None:
    collector = hints._Collector()
    hints._walk(["vulkan?", ["media-libs/vulkan-loader"]], "RDEPEND", (), collector)
    assert [item.atom for item in collector.pulls["vulkan"]] == ["media-libs/vulkan-loader"]


def test_a_negated_group_is_what_happens_when_the_flag_is_off() -> None:
    collector = hints._Collector()
    hints._walk(["!ssl?", ["dev-libs/nss"]], "RDEPEND", (), collector)
    assert "ssl" not in collector.pulls
    assert [item.atom for item in collector.pulls_off["ssl"]] == ["dev-libs/nss"]


def test_nested_conditions_are_carried_along() -> None:
    """``drm? ( egl? ( mesa ) )`` needs both, and saying so avoids a lie."""
    collector = hints._Collector()
    hints._walk(["drm?", ["egl?", ["media-libs/mesa"]]], "RDEPEND", (), collector)
    entry = collector.pulls["egl"][0]
    assert entry.atom == "media-libs/mesa"
    assert entry.also_needs == ("drm",)
    assert not entry.is_unconditional


def test_an_any_of_group_adds_no_condition_of_its_own() -> None:
    collector = hints._Collector()
    hints._walk(["x?", ["||", ["a/one", "b/two"]]], "RDEPEND", (), collector)
    assert {item.atom for item in collector.pulls["x"]} == {"a/one", "b/two"}


@pytest.mark.parametrize(
    ("atom", "expected"),
    [
        ("media-libs/libplacebo[vulkan?]", ("vulkan",)),
        ("media-libs/libva:=[X?,drm(+)?,wayland?]", ("X", "drm(+)", "wayland")),
        ("dev-libs/foo[vulkan=]", ("vulkan",)),
        ("dev-libs/foo[static-libs]", ()),
        ("dev-libs/foo", ()),
    ],
)
def test_use_dependencies_are_told_apart_from_fixed_demands(atom, expected) -> None:
    """``[vulkan?]`` mirrors our flag; ``[static-libs]`` is a fixed requirement."""
    assert hints._use_dependency_flags(atom) == expected


# -- the write plan ---------------------------------------------------------


def flag(name: str, *, enabled: bool, baseline: bool, lock: FlagLock = FlagLock.NONE) -> UseFlag:
    return UseFlag(
        name=name,
        enabled=enabled,
        baseline=baseline,
        source=FlagSource.PROFILE,
        lock=lock,
        lock_scope="profile" if lock is not FlagLock.NONE else "",
        description="",
        description_source=useflags.DescriptionSource.NONE,
        expand_variable="",
    )


@pytest.fixture
def state() -> UseState:
    return UseState(
        cpv="media-video/mpv-0.41.0-r2",
        cp="media-video/mpv",
        repo="gentoo",
        flags=(
            flag("vulkan", enabled=True, baseline=True),
            flag("jack", enabled=False, baseline=False),
            flag("X", enabled=True, baseline=True),
            flag("lua_single_target_luajit", enabled=True, baseline=True, lock=FlagLock.FORCED),
        ),
        required_use="|| ( cli libmpv )",
    )


def test_only_the_flags_that_differ_from_the_default_are_written(state: UseState) -> None:
    desired = {"vulkan": False, "jack": True, "X": True}
    assert confedit.changed_flags(state, desired) == {"vulkan": False, "jack": True}


def test_a_locked_flag_never_reaches_the_file(state: UseState) -> None:
    """use.force wins over package.use, so writing it would do nothing at all."""
    desired = {"lua_single_target_luajit": False}
    assert confedit.changed_flags(state, desired) == {}


def test_the_line_is_sorted_so_the_same_choice_gives_the_same_text() -> None:
    line = confedit.use_line("media-video/mpv", {"jack": True, "vulkan": False, "alsa": True})
    assert line == "media-video/mpv alsa jack -vulkan"


def test_a_directory_gets_a_file_named_after_the_package(tmp_path: Path, state) -> None:
    (tmp_path / "package.use").mkdir()
    path, kind, existing = confedit.locate("package.use", state.cp, config_dir=tmp_path)
    assert path == tmp_path / "package.use" / "mpv"
    assert kind is confedit.TargetKind.DIRECTORY
    assert existing is None


def test_an_existing_entry_is_amended_where_it_already_lives(tmp_path: Path, state) -> None:
    directory = tmp_path / "package.use"
    directory.mkdir()
    (directory / "media").write_text("media-video/mpv vulkan\n", encoding="utf-8")

    path, kind, existing = confedit.locate("package.use", state.cp, config_dir=tmp_path)

    assert path == directory / "media", "the entry should not be duplicated elsewhere"
    assert kind is confedit.TargetKind.EXISTING
    assert existing == "media-video/mpv vulkan"


def test_a_single_file_is_appended_to(tmp_path: Path, state) -> None:
    (tmp_path / "package.use").write_text("# mine\n", encoding="utf-8")
    path, kind, _existing = confedit.locate("package.use", state.cp, config_dir=tmp_path)
    assert path == tmp_path / "package.use"
    assert kind is confedit.TargetKind.SINGLE_FILE


def test_nothing_there_yet_means_the_recommended_directory_form(tmp_path: Path, state) -> None:
    path, kind, _existing = confedit.locate("package.use", state.cp, config_dir=tmp_path)
    assert path == tmp_path / "package.use" / "mpv"
    assert kind is confedit.TargetKind.NEW_DIRECTORY


def test_a_version_restricted_entry_is_left_alone(tmp_path: Path, state) -> None:
    """``>=media-video/mpv-0.40 X`` was written on purpose and is not ours to edit."""
    directory = tmp_path / "package.use"
    directory.mkdir()
    (directory / "media").write_text(">=media-video/mpv-0.40 X\n", encoding="utf-8")

    _path, kind, existing = confedit.locate("package.use", state.cp, config_dir=tmp_path)
    assert kind is confedit.TargetKind.DIRECTORY
    assert existing is None


def test_the_plan_for_a_fresh_change_is_a_single_appended_line(tmp_path, state) -> None:
    (tmp_path / "package.use").mkdir()
    plan = confedit.plan_package_use(
        state, {"jack": True, "vulkan": False}, config_dir=tmp_path
    )
    assert plan.op == "append_line"
    assert plan.line == "media-video/mpv jack -vulkan"


def test_changing_an_existing_entry_replaces_exactly_that_line(tmp_path, state) -> None:
    directory = tmp_path / "package.use"
    directory.mkdir()
    (directory / "mpv").write_text("media-video/mpv vulkan\n", encoding="utf-8")

    plan = confedit.plan_package_use(state, {"jack": True}, config_dir=tmp_path)

    assert plan.op == "replace_line"
    assert plan.previous == "media-video/mpv vulkan"
    assert plan.line == "media-video/mpv jack"
    assert plan.match is not None


def test_going_back_to_the_defaults_removes_the_line(tmp_path, state) -> None:
    directory = tmp_path / "package.use"
    directory.mkdir()
    (directory / "mpv").write_text("media-video/mpv jack\n", encoding="utf-8")

    plan = confedit.plan_package_use(state, {"jack": False}, config_dir=tmp_path)

    assert plan.op == "remove_line"
    assert plan.previous == "media-video/mpv jack"


def test_changing_nothing_plans_nothing(tmp_path, state) -> None:
    plan = confedit.plan_package_use(state, {"vulkan": True, "X": True}, config_dir=tmp_path)
    assert plan.is_noop


# -- against the real system ------------------------------------------------


@pytest.fixture(scope="session")
def mpv(portage_env):
    best = portage_env.portdb.xmatch("bestmatch-visible", "media-video/mpv")
    if not best:
        pytest.skip("media-video/mpv is not available here")
    return useflags.collect(str(best), env=portage_env)


def test_a_real_package_has_flags_with_descriptions(mpv: UseState) -> None:
    assert len(mpv.flags) > 20
    described = [item for item in mpv.flags if item.description]
    assert len(described) > len(mpv.flags) // 2


def test_the_profile_stack_is_read_in_order(mpv: UseState) -> None:
    """mpv's profile mentions both ``sdl`` and ``-sdl``; the later one wins.

    Portage flattens the profile stack by concatenation, so a set of tokens
    cannot tell the two apart — and reading it as a set reported ``sdl`` as
    enabled for every package on this system until this was fixed.
    """
    sdl = mpv.flag("sdl")
    if sdl is None:
        pytest.skip("this version of mpv has no sdl flag")
    assert sdl.enabled is False
    assert sdl.baseline is False


def test_expanded_flags_are_grouped_away_from_the_rest(mpv: UseState) -> None:
    groups = dict(mpv.grouped())
    assert groups[""], "there should be ordinary flags too"
    assert any(name.endswith("_SINGLE_TARGET") for name in groups if name)
    assert all(not item.is_expand for item in groups[""])


def test_a_forced_flag_is_reported_as_locked(mpv: UseState) -> None:
    locked = [item for item in mpv.flags if item.is_locked]
    assert locked, "mpv has forced lua_single_target flags on this profile"
    assert all(item.lock_scope in ("profile", "package") for item in locked)


def test_the_criterion_from_the_plan(portage_env, mpv: UseState) -> None:
    """Ticking ``vulkan`` has to show the real package it pulls in."""
    effects = hints.effects(mpv.cpv, mpv.repo, portage_env)
    vulkan = effects.get("vulkan")
    assert vulkan is not None
    atoms = " ".join(item.atom for item in vulkan.pulls_in)
    assert "media-libs/vulkan-loader" in atoms


def test_required_use_of_a_real_package_parses_and_round_trips(mpv: UseState) -> None:
    rendered = " ".join(node.render() for node in ru.parse(mpv.required_use))
    assert rendered == " ".join(mpv.required_use.split())


def test_the_current_selection_of_a_real_package_is_valid(mpv: UseState) -> None:
    """Whatever Portage has settled on must satisfy the package's own rules."""
    assert not ru.broken(ru.check(mpv.required_use, mpv.enabled))


# -- the whole write path, minus the password prompt -------------------------

_WRAPPER = """
import sys
from pathlib import Path
from gentstore.helper import gentstore_helper as helper
helper.CONFIG_ROOT = Path(sys.argv[1])
helper.BACKUP_PARENT = Path(sys.argv[1]).parent
sys.exit(helper.main())
"""


@pytest.fixture
def sandbox_helper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The real helper, as a real subprocess, against a throwaway /etc/portage.

    Everything the Save button does except becoming root: the plan is turned
    into a request, the request crosses a process boundary as JSON, and the
    helper decides for itself whether to carry it out.
    """
    from gentstore.runner import privilege

    root = tmp_path / "portage"
    (root / "package.use").mkdir(parents=True)
    wrapper = tmp_path / "wrapper.py"
    wrapper.write_text(_WRAPPER, encoding="utf-8")

    import sys as _sys

    monkeypatch.setattr(
        privilege,
        "helper_command",
        lambda: privilege.PrivilegedProgram(
            (_sys.executable, str(wrapper), str(root)), installed=False
        ),
    )
    monkeypatch.setattr(privilege, "detect", lambda: privilege.Escalation("direct", None))
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parent.parent))
    return root


def test_a_plan_becomes_exactly_one_line_in_package_use(
    sandbox_helper: Path, state: UseState
) -> None:
    from gentstore.runner import helper_client

    plan = confedit.plan_package_use(
        state, {"jack": True, "vulkan": False}, config_dir=sandbox_helper
    )
    result = helper_client.request(plan.op, **plan.as_request())

    assert result.ok, result.error
    written = (sandbox_helper / "package.use" / "mpv").read_text(encoding="utf-8")
    assert written == "media-video/mpv jack -vulkan\n"


def test_saving_the_same_choice_twice_does_not_duplicate_the_line(
    sandbox_helper: Path, state: UseState
) -> None:
    from gentstore.runner import helper_client

    plan = confedit.plan_package_use(state, {"jack": True}, config_dir=sandbox_helper)
    helper_client.request(plan.op, **plan.as_request())
    again = helper_client.request(plan.op, **plan.as_request())

    assert again.ok
    assert not again.changed
    written = (sandbox_helper / "package.use" / "mpv").read_text(encoding="utf-8")
    assert written.count("media-video/mpv") == 1


def test_a_second_change_replaces_the_line_and_keeps_the_comments(
    sandbox_helper: Path, state: UseState
) -> None:
    from gentstore.runner import helper_client

    target = sandbox_helper / "package.use" / "media"
    target.write_text("# my own note\nmedia-video/mpv vulkan\n", encoding="utf-8")

    plan = confedit.plan_package_use(state, {"jack": True}, config_dir=sandbox_helper)
    assert plan.op == "replace_line"
    assert helper_client.request(plan.op, **plan.as_request()).ok

    assert target.read_text(encoding="utf-8") == "# my own note\nmedia-video/mpv jack\n"


def test_the_backup_is_made_in_the_same_call_as_the_change(
    sandbox_helper: Path, state: UseState
) -> None:
    from gentstore.runner import helper_client

    plan = confedit.plan_package_use(state, {"jack": True}, config_dir=sandbox_helper)
    result = helper_client.request(plan.op, ensure_backup=True, **plan.as_request())

    assert result.ok
    assert result.backup, "a change must never land without its backup"
    assert (Path(result.backup) / "package.use").is_dir()
