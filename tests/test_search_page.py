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

"""Tests for the "Search & install" screen and the widgets it is built from.

They run against a hand-made index rather than the machine's real repositories,
so the assertions are about the screen's behaviour — filtering, counting,
selection — and not about which packages happen to be installed here.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from gentstore.core.packages import (  # noqa: E402
    IndexEntry,
    Keywording,
    PackageState,
    PackageSummary,
    SearchIndex,
    Version,
)
from gentstore.models.packages import PackageListModel  # noqa: E402
from gentstore.ui.main_window import MainWindow  # noqa: E402
from gentstore.ui.pages import SearchPage  # noqa: E402
from gentstore.ui.tasks import wait_for_tasks  # noqa: E402

OFFICIAL = "gentoo"
OVERLAY = "guru"


def entry(cp: str, description: str, repos: tuple[str, ...]) -> IndexEntry:
    category, _, name = cp.partition("/")
    return IndexEntry(
        cp=cp,
        category=category,
        name=name,
        description=description,
        repos=repos,
        fold_name=name.lower(),
        fold_cp=cp.lower(),
        fold_description=description.lower(),
    )


@pytest.fixture
def index() -> SearchIndex:
    return SearchIndex(
        entries=(
            entry("media-video/mpv", "Media player for the command line", (OFFICIAL,)),
            entry("media-libs/mpvqt", "libmpv wrapper for QtQuick2", (OFFICIAL,)),
            entry("gui-apps/mpvpaper", "A video wallpaper program", (OVERLAY,)),
            entry("media-sound/mpvc", "mpc-like tool for mpv", (OVERLAY,)),
            entry("app-editors/vim", "Vi IMproved", (OFFICIAL,)),
        ),
        installed=frozenset({"app-editors/vim"}),
        repos=(OFFICIAL, OVERLAY),
    )


@pytest.fixture
def window(app, index: SearchIndex) -> MainWindow:  # noqa: ANN001 - conftest fixture
    app.apply_language("en")
    window = MainWindow(app.settings)
    window.context.set_official_only(False, "hide")
    window.set_page("search")
    window.context.install_index(index)
    return window


@pytest.fixture
def page(window: MainWindow) -> SearchPage:
    current = window.stack.currentWidget()
    assert isinstance(current, SearchPage)
    return current


def search(page: SearchPage, query: str) -> list[str]:
    """Run a query and return the ``cat/pkg`` of every row, in order."""
    page.set_query(query)
    wait_for_tasks()  # the details request fired by the automatic selection
    model = page._model
    return [model.summary_at(row).cp for row in range(model.rowCount())]


# -- the result list --------------------------------------------------------


def test_a_query_produces_the_expected_rows(page: SearchPage) -> None:
    assert search(page, "mpv")[0] == "media-video/mpv"
    assert "app-editors/vim" not in search(page, "mpv")


def test_an_empty_query_clears_the_list(page: SearchPage) -> None:
    assert search(page, "mpv")
    assert search(page, "") == []


def test_the_first_result_is_selected_automatically(page: SearchPage) -> None:
    search(page, "mpv")
    assert page._list.currentIndex().row() == 0


def test_the_repository_filter_narrows_the_list(page: SearchPage) -> None:
    search(page, "mpv")
    page._set_repo_filter(OVERLAY)
    rows = [page._model.summary_at(r).cp for r in range(page._model.rowCount())]
    assert rows and all(OVERLAY in page._model.summary_at(r).repos for r in range(len(rows)))


def test_there_is_a_filter_pill_per_repository_plus_all(page: SearchPage) -> None:
    assert set(page._repo_pills) == {"*", OFFICIAL, OVERLAY}


# -- one repository at a time -----------------------------------------------


def test_no_filter_leaves_the_screen_looking_at_every_repository(page: SearchPage) -> None:
    search(page, "mpv")
    assert page._active_repo() == ""


def test_a_filter_pill_confines_the_whole_screen_to_that_repository(
    page: SearchPage,
) -> None:
    """The list is only half of it — the details panel has to follow.

    Two repositories carrying the same package is the case this exists for: the
    panel must not offer a version the chosen repository does not have.
    """
    search(page, "mpv")
    page._set_repo_filter(OVERLAY)
    wait_for_tasks()
    assert page._active_repo() == OVERLAY
    assert page._narrowed_to == OVERLAY


def test_the_rows_wear_the_badge_of_the_repository_that_was_chosen(
    page: SearchPage,
) -> None:
    """Otherwise a row says ``::gentoo`` while the panel beside it says ``::guru``."""
    search(page, "mpv")
    page._set_repo_filter(OVERLAY)
    wait_for_tasks()
    rows = [page._model.summary_at(r) for r in range(page._model.rowCount())]
    assert rows
    assert all(row.repos == (OVERLAY,) for row in rows)


def test_without_a_filter_the_rows_name_every_repository(page: SearchPage) -> None:
    search(page, "mpv")
    summary = page._model.summary_at(page._model.row_of("media-video/mpv"))
    assert summary.repos == (OFFICIAL,)


def test_a_typed_repository_suffix_confines_the_screen_too(page: SearchPage) -> None:
    search(page, f"mpv::{OVERLAY}")
    assert page._active_repo() == OVERLAY


def test_hide_mode_confines_the_screen_to_the_official_repository(
    window: MainWindow, page: SearchPage
) -> None:
    search(page, "mpv")
    window.context.set_official_only(True, "hide")
    wait_for_tasks()
    assert page._active_repo() == OFFICIAL


def test_mask_mode_does_not_confine_the_screen(
    window: MainWindow, page: SearchPage
) -> None:
    """Mode ``mask`` is a change to Portage, not a filter on this screen."""
    search(page, "mpv")
    window.context.set_official_only(True, "mask")
    wait_for_tasks()
    assert page._active_repo() == ""


# -- "only ::gentoo" --------------------------------------------------------


def test_hide_mode_drops_overlay_packages_and_says_how_many(
    window: MainWindow, page: SearchPage
) -> None:
    before = search(page, "mpv")
    window.context.set_official_only(True, "hide")
    wait_for_tasks()

    after = [page._model.summary_at(r).cp for r in range(page._model.rowCount())]
    assert "gui-apps/mpvpaper" in before
    assert "gui-apps/mpvpaper" not in after
    # isHidden rather than isVisible: the window is never shown in the tests, so
    # nothing inside it counts as visible.
    assert not page._notice.isHidden()
    assert "2" in page._notice.text()


def test_mask_mode_does_not_filter_the_list(window: MainWindow, page: SearchPage) -> None:
    """Mode ``mask`` changes Portage, not the interface.

    If the screen filtered here as well, the user would see the effect of a
    change that has not been written yet.
    """
    before = search(page, "mpv")
    window.context.set_official_only(True, "mask")
    wait_for_tasks()
    after = [page._model.summary_at(r).cp for r in range(page._model.rowCount())]
    assert after == before
    assert page._notice.isHidden()


# -- the model --------------------------------------------------------------


def test_the_model_asks_for_a_package_state_once_per_package() -> None:
    calls: list[str] = []

    def provider(cp: str) -> PackageState:
        calls.append(cp)
        return PackageState(cp, "1.0", "2.0", "9999")

    model = PackageListModel(provider)
    model.set_results([PackageSummary("media-video/mpv", "…", ("gentoo",), True)])
    index = model.index(0)
    first = model.data(index, PackageListModel.StateRole)
    again = model.data(index, PackageListModel.StateRole)

    assert calls == ["media-video/mpv"], "the answer should be cached"
    assert first is again
    assert first.has_update


def test_invalidating_the_states_makes_the_model_ask_again() -> None:
    calls: list[str] = []

    def provider(cp: str) -> PackageState:
        calls.append(cp)
        return PackageState(cp, None, "2.0", "2.0")

    model = PackageListModel(provider)
    model.set_results([PackageSummary("media-video/mpv", "…", ("gentoo",), False)])
    model.data(model.index(0), PackageListModel.StateRole)
    model.invalidate_states()
    model.data(model.index(0), PackageListModel.StateRole)
    assert len(calls) == 2


def test_a_failing_state_provider_does_not_break_the_row() -> None:
    def provider(cp: str) -> PackageState:
        raise RuntimeError("the repository went away")

    model = PackageListModel(provider)
    model.set_results([PackageSummary("media-video/mpv", "…", ("gentoo",), False)])
    state = model.data(model.index(0), PackageListModel.StateRole)
    assert isinstance(state, PackageState)
    assert state.available_version is None


# -- the version picker -----------------------------------------------------


def make_version(version: str, keywording: Keywording, installed: bool = False) -> Version:
    return Version(
        cpv=f"media-video/mpv-{version}",
        cp="media-video/mpv",
        version=version,
        repo="gentoo",
        slot="0",
        sub_slot="0",
        keywords=(),
        keywording=keywording,
        masking=(),
        iuse=(),
        restrict="",
        eapi="8",
        installed=installed,
    )


def make_details(repos: tuple[str, ...] = ("gentoo",), repo: str = ""):  # noqa: ANN201
    from gentstore.core.packages import PackageDetails

    return PackageDetails(
        cp="media-video/mpv",
        description="",
        homepage=(),
        license="",
        repos=repos,
        versions=(
            make_version("0.40.0", Keywording.STABLE),
            make_version("0.41.0", Keywording.TESTING),
            make_version("9999", Keywording.LIVE),
        ),
        installed=(),
        best_visible="media-video/mpv-0.40.0",
        download_size=None,
        repo=repo,
    )


def test_live_versions_are_listed_last(page: SearchPage) -> None:
    """``9999`` sorts highest but is almost never what somebody wants."""
    assert [v.version for v in page._ordered_versions(make_details())] == [
        "0.41.0", "0.40.0", "9999",
    ]


# -- the atom the buttons run -----------------------------------------------


def test_a_single_repository_atom_carries_no_qualifier(page: SearchPage) -> None:
    """``=cat/pkg-1.2::gentoo`` is noise when there is nowhere else to get it."""
    page._details = info = make_details()
    page._selected_cpv = "media-video/mpv-0.41.0"
    assert page._atom_for(info) == "=media-video/mpv-0.41.0"


def test_a_package_in_two_repositories_is_qualified(page: SearchPage) -> None:
    page._details = info = make_details(repos=("gentoo", OVERLAY))
    page._selected_cpv = "media-video/mpv-0.41.0"
    assert page._atom_for(info) == "=media-video/mpv-0.41.0::gentoo"


def test_narrowing_to_a_repository_qualifies_the_atom(page: SearchPage) -> None:
    """The whole point of picking a repository.

    The same version number can sit in two repositories; without the qualifier
    Portage would pick by repository priority rather than by what is on screen.
    """
    page._details = info = make_details(repo="gentoo")
    page._selected_cpv = "media-video/mpv-0.41.0"
    assert page._atom_for(info) == "=media-video/mpv-0.41.0::gentoo"
    assert page._pretend_spec(info).display.endswith("=media-video/mpv-0.41.0::gentoo")


def test_without_a_version_the_narrowed_atom_still_names_the_repository(
    page: SearchPage,
) -> None:
    page._details = info = make_details(repo=OVERLAY)
    page._selected_cpv = None
    assert page._atom_for(info) == f"media-video/mpv::{OVERLAY}"


# -- a stale answer ---------------------------------------------------------


def test_details_for_a_repository_that_is_no_longer_selected_are_dropped(
    page: SearchPage,
) -> None:
    """A slow answer must not repopulate the panel with the previous filter."""
    search(page, "mpv")
    page._set_repo_filter(OVERLAY)
    wait_for_tasks()
    page._selected_cp = "media-video/mpv"
    page._details = None
    page._on_details(make_details(repo=""))
    assert page._details is None


# -- the changes emerge asks for --------------------------------------------


REFUSED_FOR_A_DEPENDENCY = """
[ebuild  N     ] sys-fs/squashfs-tools-4.7.5::gentoo  USE="xattr zstd" 403 KiB
[ebuild  N    ~] sci-ml/lmstudio-bin-0.4.23::overlay-nuda  USE="-cuda" 986657 KiB

The following USE changes are necessary to proceed:
 (see "package.use" in the portage(5) man page for more details)
# required by sci-ml/lmstudio-bin-0.4.23::overlay-nuda
>=sys-fs/squashfs-tools-4.7.5 zstd
"""


def make_panel(config_dir=None):  # noqa: ANN001, ANN201 - a widget
    """The panel, pointed at a throwaway ``/etc/portage`` when one is given.

    Without it the batch is worked out against the machine running the tests,
    and "this line is already accepted here" turns a test about grouping into a
    test about somebody's configuration.
    """
    from gentstore.ui.widgets.required_changes import RequiredChanges

    return RequiredChanges(config_dir=config_dir)


def test_a_refusal_about_a_dependency_becomes_a_line_to_save(app, tmp_path) -> None:  # noqa: ANN001
    """emerge stops, and the line it wants is offered rather than just printed.

    The package itself is fine here — nothing is masked — so the block notice
    has nothing to say and this frame is the only thing standing between the
    user and retyping an atom out of the terminal pane.
    """
    from gentstore.core.install_plan import from_output

    (tmp_path / "package.use").mkdir()
    frame = make_panel(tmp_path)
    frame.set_plan(from_output(REFUSED_FOR_A_DEPENDENCY))

    assert not frame.isHidden()
    assert [entry.line for entry in frame.selected] == [
        ">=sys-fs/squashfs-tools-4.7.5 zstd"
    ]

    # Asking to see the lines only builds the preview; nothing is written.
    frame._on_show_lines()
    batch = frame.batch
    assert batch is not None
    assert [plan.line for plan in batch.appends] == [
        ">=sys-fs/squashfs-tools-4.7.5 zstd"
    ]
    assert batch.appends[0].path.name == "squashfs-tools"
    assert "package.use" in str(batch.appends[0].path)


def test_output_with_nothing_to_change_leaves_the_frame_away(app) -> None:  # noqa: ANN001
    """An ordinary run must not leave a demand on the screen."""
    from gentstore.core.install_plan import from_output

    frame = make_panel()
    frame.set_plan(from_output("[ebuild  N     ] app-misc/foo-1.2::gentoo 10 KiB\n"))
    assert frame.isHidden()
    assert frame.selected == ()


def test_an_unticked_line_stays_out_of_the_batch(app, tmp_path) -> None:  # noqa: ANN001
    """The checkbox is the decision, and it is the only thing consulted."""
    from gentstore.core.install_plan import from_output

    frame = make_panel(tmp_path)
    plan = from_output(REFUSED_FOR_A_DEPENDENCY)
    frame.set_plan(plan)

    frame._on_entry_toggled(plan.entries[0], False)
    assert frame.selected == ()

    frame._on_show_lines()
    batch = frame.batch
    assert batch is not None and batch.is_empty


def test_unticking_survives_a_second_analysis(app) -> None:  # noqa: ANN001
    """Re-running the analysis must not undo an answer the user has given.

    The second run reports the same line, because nothing was written. Ticking
    it again "because it looks routine" would quietly reverse a decision, and
    the decision is the only thing this screen is really asking for.
    """
    from gentstore.core.install_plan import from_output

    frame = make_panel()
    plan = from_output(REFUSED_FOR_A_DEPENDENCY)
    frame.set_plan(plan)
    frame._on_entry_toggled(plan.entries[0], False)

    frame.set_plan(from_output(REFUSED_FOR_A_DEPENDENCY))
    assert frame.selected == ()


def test_a_line_goes_in_even_when_its_directory_does_not_exist(app, tmp_path) -> None:  # noqa: ANN001
    """Gentoo recommends the directory form, and now something creates it.

    The preview has always said "neither package.use nor a directory of that
    name exists yet, so that is what will be created", and for a long time
    nothing did — ``check_path`` refused a target whose parent was missing. The
    helper creates that one directory itself now, so the line is an ordinary
    append and belongs in the batch like any other.
    """
    from gentstore.core.install_plan import from_output

    frame = make_panel(tmp_path)          # nothing exists under it at all
    frame.set_plan(from_output(REFUSED_FOR_A_DEPENDENCY))
    frame._on_show_lines()

    batch = frame.batch
    assert batch is not None and not batch.is_empty
    assert [plan.line for plan in batch.appends] == [
        ">=sys-fs/squashfs-tools-4.7.5 zstd"
    ]
    assert batch.needs_replacement == ()


def test_a_conflict_is_shown_and_offers_no_button(app) -> None:  # noqa: ANN001
    """Portage could not resolve the graph, and no line in /etc/portage will.

    The rule the screen follows is "what the parser does not understand stays
    visible": the text is Portage's own, and there is nothing to apply.
    """
    from gentstore.core.install_plan import from_output

    fixture = Path(__file__).parent / "fixtures" / "pretend-conflict.txt"
    frame = make_panel()
    plan = from_output(fixture.read_text(encoding="utf-8"))
    frame.set_plan(plan)

    assert not frame.isHidden()
    assert plan.conflicts and not plan.can_apply
    assert not frame._btn_apply.isVisible()
    assert not frame._conflict.isHidden()


def test_masks_start_unticked_and_keywords_do_not(app) -> None:  # noqa: ANN001
    """A keyword is ordinary Gentoo; an unmask undoes somebody's decision."""
    from gentstore.core.install_plan import from_output

    frame = make_panel()
    frame.set_plan(
        from_output(
            "The following keyword changes are necessary to proceed:\n"
            "=cat/keyworded-1 ~amd64\n"
            "\n"
            "The following mask changes are necessary to proceed:\n"
            "=cat/masked-1\n"
        )
    )

    assert [entry.line for entry in frame.selected] == ["=cat/keyworded-1 ~amd64"]


def test_a_starred_keyword_and_a_live_atom_start_unticked(app) -> None:  # noqa: ANN001
    """``**`` and ``9999`` are decisions of a different size from ``~amd64``."""
    from gentstore.core.install_plan import from_output

    frame = make_panel()
    plan = from_output(
        "The following keyword changes are necessary to proceed:\n"
        "=cat/ordinary-1 ~amd64\n"
        "=cat/untested-1 **\n"
        "=cat/live-9999 **\n"
    )
    frame.set_plan(plan)

    assert [entry.line for entry in frame.selected] == ["=cat/ordinary-1 ~amd64"]
    assert [entry.line for entry in plan.notable] == [
        "=cat/untested-1 **",
        "=cat/live-9999 **",
    ]


# -- the install gate -------------------------------------------------------


def feed_log(window: MainWindow, text: str) -> None:
    """Put *text* in the log pane the way a finished command would leave it."""
    window.log_view.start("emerge", "")
    for line in text.splitlines():
        window.log_view.append(line)


def finish_analysis(page: SearchPage, info, window: MainWindow, output: str) -> None:  # noqa: ANN001
    """Play out an analysis the way pressing the button does.

    Two pieces of state, because the screen asks two questions of a finished
    run: did I start it, and was it the analysis. Setting only the second is how
    the gate tests used to pass while the frame filled itself from whatever
    command happened to end.
    """
    feed_log(window, output)
    spec = page._analysis_spec(info)
    page._ran = spec.argv
    page._analysing = spec.argv
    page._on_command_finished(1)


def arm_details(page: SearchPage) -> object:
    info = make_details()
    page._details = info
    page._selected_cpv = "media-video/mpv-0.40.0"
    page._refresh_actions(info)
    return info


def test_the_install_button_waits_for_an_analysis(
    window: MainWindow, page: SearchPage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing installs until Portage has said, about this command, that it can.

    The gate costs a click and a few seconds before every install. What it buys
    is the one thing the screen could not say before: that the build will start
    rather than stop on a keyword four dependencies down.
    """
    monkeypatch.setattr(page, "_reload_package", lambda: None)
    info = arm_details(page)

    assert not page._btn_primary.isEnabled(), "no analysis has been run yet"
    assert page._btn_analyse.isEnabled()

    fixture = (Path(__file__).parent / "fixtures" / "pretend-clean.txt").read_text()
    finish_analysis(page, info, window, fixture)

    assert page._btn_primary.isEnabled(), "a clean analysis opens the gate"


def test_an_analysis_that_wants_changes_keeps_the_gate_shut(
    window: MainWindow, page: SearchPage, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(page, "_reload_package", lambda: None)
    info = arm_details(page)

    finish_analysis(page, info, window, REFUSED_FOR_A_DEPENDENCY)

    assert not page._btn_primary.isEnabled()
    assert not page._required.isHidden(), "and the lines are on screen instead"


def test_a_plain_pretend_cannot_open_the_gate(
    window: MainWindow, page: SearchPage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--pretend`` without ``--autounmask`` never mentions a licence.

    So a clean-looking run of it is an answer to a question that was not asked,
    and letting it stand in for the analysis would be the quietest way to put
    the old behaviour back.
    """
    monkeypatch.setattr(page, "_reload_package", lambda: None)
    arm_details(page)

    info = page._details
    feed_log(window, (Path(__file__).parent / "fixtures" / "pretend-clean.txt").read_text())
    page._ran = page._pretend_spec(info).argv   # this screen ran it…
    page._analysing = None                      # …but it was Pretend, not the analysis
    page._on_command_finished(0)

    assert not page._btn_primary.isEnabled()


def test_choosing_another_version_shuts_the_gate(
    window: MainWindow, page: SearchPage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gate is the command line, so a different atom is a different gate."""
    monkeypatch.setattr(page, "_reload_package", lambda: None)
    info = arm_details(page)
    fixture = (Path(__file__).parent / "fixtures" / "pretend-clean.txt").read_text()
    finish_analysis(page, info, window, fixture)
    assert page._btn_primary.isEnabled()

    page._selected_cpv = "media-video/mpv-0.41.0"
    page._refresh_actions(info)

    assert not page._btn_primary.isEnabled()


def test_the_analysis_carries_the_options_the_install_would(page: SearchPage) -> None:
    """A plan for one command and an install of another is not a plan."""
    info = arm_details(page)
    analysis = page._analysis_spec(info).argv
    install = page._primary_spec(info).argv

    assert "--autounmask" in analysis
    assert "--pretend" in analysis
    assert analysis[-1] == install[-1], "the same atom"
    assert ("--getbinpkg" in analysis) == ("--getbinpkg" in install)
    for forbidden in ("--autounmask-write", "--autounmask-continue", "--ask"):
        assert forbidden not in analysis


def test_cancelling_the_preview_sends_nothing(app, tmp_path) -> None:  # noqa: ANN001
    """The second confirmation is a real one: dismissing it writes nothing."""
    from gentstore.core.install_plan import from_output

    (tmp_path / "package.use").mkdir()
    frame = make_panel(tmp_path)
    frame.set_plan(from_output(REFUSED_FOR_A_DEPENDENCY))

    sent: list[object] = []
    frame.apply_requested.connect(sent.append)

    frame._on_show_lines()
    assert frame.batch is not None
    frame._disarm()

    assert frame.batch is None
    assert sent == [], "nothing may reach the helper before Save is pressed"


def test_only_ticked_lines_reach_the_helper(app, tmp_path) -> None:  # noqa: ANN001
    """What the request carries is exactly what the boxes say."""
    from gentstore.core.install_plan import from_output

    (tmp_path / "package.accept_keywords").mkdir()
    frame = make_panel(tmp_path)
    plan = from_output(
        "The following keyword changes are necessary to proceed:\n"
        "=cat/one-1 ~amd64\n"
        "=cat/two-1 ~amd64\n"
    )
    frame.set_plan(plan)
    frame._on_entry_toggled(plan.entries[1], False)

    sent: list[object] = []
    frame.apply_requested.connect(sent.append)
    frame._on_show_lines()
    frame._on_save()

    assert len(sent) == 1
    request = sent[0].as_request()
    assert [item["line"] for item in request["entries"]] == ["=cat/one-1 ~amd64"]


def test_a_command_this_screen_did_not_start_leaves_the_frame_alone(
    window: MainWindow, page: SearchPage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """"Update @world" from the toolbar is not an answer about this package.

    One runner and one log panel serve the whole window, so every command ends
    here. A ``@world`` update reports on the entire system; showing that report
    inside the frame belonging to one package attributes it to something that
    had nothing to do with it — which is what happened, and it announced a
    conflict under a package the run never mentioned.
    """
    monkeypatch.setattr(page, "_reload_package", lambda: None)
    arm_details(page)

    feed_log(window, REFUSED_FOR_A_DEPENDENCY)
    page._ran = None                       # the toolbar started it, not this screen
    page._analysing = None
    page._on_command_finished(1)

    assert page._required.isHidden()
    assert page._required.selected == ()
    assert not page._btn_primary.isEnabled()
