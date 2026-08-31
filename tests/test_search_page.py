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


def test_a_refusal_about_a_dependency_becomes_a_line_to_save(app) -> None:  # noqa: ANN001
    """emerge stops, and the line it wants is offered rather than just printed.

    The package itself is fine here — nothing is masked — so the block notice
    has nothing to say and this frame is the only thing standing between the
    user and retyping an atom out of the terminal pane.
    """
    from gentstore.core.emerge_parse import parse_pretend
    from gentstore.ui.widgets.required_changes import RequiredChanges

    frame = RequiredChanges()
    frame.set_preview(parse_pretend(REFUSED_FOR_A_DEPENDENCY))

    assert not frame.isHidden()
    assert [entry.line for entry in frame.entries] == [
        ">=sys-fs/squashfs-tools-4.7.5 zstd"
    ]

    # Pressing the row's button only arms the preview; nothing is written.
    frame._arm(frame.entries[0])
    assert frame.plan is not None
    assert frame.plan.line == ">=sys-fs/squashfs-tools-4.7.5 zstd"
    assert frame.plan.path.name == "squashfs-tools"
    assert "package.use" in str(frame.plan.path)


def test_output_with_nothing_to_change_leaves_the_frame_away(app) -> None:  # noqa: ANN001
    """An ordinary run must not leave a demand on the screen."""
    from gentstore.core.emerge_parse import parse_pretend
    from gentstore.ui.widgets.required_changes import RequiredChanges

    frame = RequiredChanges()
    frame.set_preview(parse_pretend("[ebuild  N     ] app-misc/foo-1.2::gentoo 10 KiB\n"))
    assert frame.isHidden()
    assert frame.entries == ()
