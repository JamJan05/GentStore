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

"""Tests for the Portage layer.

Split in two on purpose. The first half is pure logic — ranking, keyword
classification, formatting — and runs anywhere. The second half talks to the
real Portage installation of the machine running the tests, which is the only
way to catch the kind of mistake that matters here (an API used with the wrong
arguments still returns *something*), and skips itself when there is none.
"""

from __future__ import annotations

import pytest

from gentstore.core import packages as pkgs
from gentstore.core import repos as repos_mod
from gentstore.core import worldset
from gentstore.core.cli import human_size
from gentstore.core.cli import main as cli_main
from gentstore.core.portage_env import PortageUnavailableError, env


def entry(cp: str, description: str = "", repos: tuple[str, ...] = ("gentoo",)) -> pkgs.IndexEntry:
    category, _, name = cp.partition("/")
    return pkgs.IndexEntry(
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
def index() -> pkgs.SearchIndex:
    return pkgs.SearchIndex(
        entries=(
            entry("media-video/mpv", "Media player for the command line"),
            entry("media-libs/mpvqt", "libmpv wrapper for QtQuick2"),
            entry("gui-apps/mpvpaper", "A video wallpaper program", repos=("guru",)),
            entry("app-editors/vim", "Vi IMproved, an updated version of vi"),
            entry("dev-libs/zydis", "Disassembler library", repos=("gentoo", "guru")),
        ),
        installed=frozenset({"app-editors/vim"}),
        repos=("gentoo", "guru"),
    )


# -- ranking and matching ---------------------------------------------------


def test_exact_package_name_outranks_a_substring(index: pkgs.SearchIndex) -> None:
    results = index.search("mpv")
    assert [r.cp for r in results][:2] == ["media-video/mpv", "media-libs/mpvqt"]


def test_a_full_cat_pkg_matches_exactly(index: pkgs.SearchIndex) -> None:
    assert [r.cp for r in index.search("media-video/mpv")] == ["media-video/mpv"]


def test_the_description_is_searched_too(index: pkgs.SearchIndex) -> None:
    assert [r.cp for r in index.search("wallpaper")] == ["gui-apps/mpvpaper"]


def test_description_matching_can_be_turned_off(index: pkgs.SearchIndex) -> None:
    assert index.search("wallpaper", match_description=False) == []


def test_search_is_case_insensitive(index: pkgs.SearchIndex) -> None:
    assert [r.cp for r in index.search("MPV")][0] == "media-video/mpv"


def test_a_repo_suffix_narrows_the_search(index: pkgs.SearchIndex) -> None:
    assert [r.cp for r in index.search("mpv::guru")] == ["gui-apps/mpvpaper"]


def test_the_repo_filter_and_the_repo_suffix_intersect(index: pkgs.SearchIndex) -> None:
    assert index.search("mpv::guru", repos=("gentoo",)) == []


def test_globs_are_matched_against_the_whole_cat_pkg(index: pkgs.SearchIndex) -> None:
    assert [r.cp for r in index.search("media-*/mpv*")] == [
        "media-video/mpv",
        "media-libs/mpvqt",
    ]


def test_only_installed_filters_the_result(index: pkgs.SearchIndex) -> None:
    assert [r.cp for r in index.search("vi", only_installed=True)] == ["app-editors/vim"]
    assert index.search("mpv", only_installed=True) == []


def test_an_empty_query_returns_nothing(index: pkgs.SearchIndex) -> None:
    assert index.search("   ") == []


def test_the_limit_is_honoured(index: pkgs.SearchIndex) -> None:
    assert len(index.search("m", limit=2)) == 2


def test_a_summary_knows_whether_it_is_installed(index: pkgs.SearchIndex) -> None:
    assert index.get("app-editors/vim").installed is True
    assert index.get("media-video/mpv").installed is False
    assert index.get("no/such-package") is None


# -- keywords ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("keywords", "version", "expected"),
    [
        (("amd64", "~x86"), "1.0", pkgs.Keywording.STABLE),
        (("~amd64", "~x86"), "1.0", pkgs.Keywording.TESTING),
        (("-amd64", "~x86"), "1.0", pkgs.Keywording.UNSUPPORTED),
        (("-*", "~x86"), "1.0", pkgs.Keywording.UNSUPPORTED),
        (("~x86",), "1.0", pkgs.Keywording.UNKEYWORDED),
        ((), "9999", pkgs.Keywording.LIVE),
        ((), "1.0_pre9999", pkgs.Keywording.LIVE),
        ((), "1.0", pkgs.Keywording.UNKEYWORDED),
    ],
)
def test_keywords_are_classified_for_the_local_arch(keywords, version, expected) -> None:
    assert pkgs.classify_keywords(keywords, "amd64", version) is expected


def test_a_stable_keyword_does_not_beat_an_explicit_exclusion() -> None:
    # -amd64 wins over amd64: the ebuild says it does not work here.
    assert (
        pkgs.classify_keywords(("amd64", "-amd64"), "amd64", "1.0") is pkgs.Keywording.UNSUPPORTED
    )


# -- small pieces -----------------------------------------------------------


def test_a_version_builds_an_unambiguous_atom() -> None:
    version = pkgs.Version(
        cpv="media-video/mpv-0.41.0",
        cp="media-video/mpv",
        version="0.41.0",
        repo="gentoo",
        slot="0",
        sub_slot="2",
        keywords=("amd64",),
        keywording=pkgs.Keywording.STABLE,
        masking=(),
        iuse=(),
        restrict="",
        eapi="8",
        installed=False,
    )
    assert version.atom == "=media-video/mpv-0.41.0::gentoo"
    assert version.slot_display == "0/2"
    assert version.is_installable is True


def test_a_sub_slot_equal_to_the_slot_is_not_shown() -> None:
    assert pkgs._split_slot("0") == ("0", "0")
    assert pkgs._split_slot("0/2") == ("0", "2")


@pytest.mark.parametrize(
    ("size", "expected"), [(None, "?"), (11, "11 B"), (2048, "2.0 KiB"), (7262018, "6.9 MiB")]
)
def test_sizes_are_formatted_for_people(size, expected) -> None:
    assert human_size(size) == expected


def test_world_file_comments_and_blank_lines_are_ignored(tmp_path) -> None:
    path = tmp_path / "world"
    path.write_text("# a comment\n\napp-editors/vim\n  sys-apps/portage  \n", encoding="utf-8")
    assert worldset._read_lines(path) == ("app-editors/vim", "sys-apps/portage")


def test_a_missing_world_file_is_not_an_error(tmp_path) -> None:
    assert worldset._read_lines(tmp_path / "absent") == ()


# -- against the real system ------------------------------------------------


@pytest.fixture(scope="session")
def portage_env():
    try:
        return env()
    except PortageUnavailableError as exc:  # pragma: no cover - non-Gentoo host
        pytest.skip(f"no usable Portage installation: {exc}")


@pytest.fixture(scope="session")
def live_index(portage_env) -> pkgs.SearchIndex:
    return pkgs.SearchIndex.build(portage_env)


def test_the_environment_describes_a_real_system(portage_env) -> None:
    assert portage_env.arch
    assert portage_env.main_repo_name in portage_env.repo_names


def test_the_index_covers_the_whole_tree(live_index, portage_env) -> None:
    assert len(live_index) > 1000
    assert set(live_index.repos) == set(portage_env.repo_names)
    # The completion criterion for this session: fast enough to build at start-up.
    assert live_index.build_seconds < 15


def test_every_indexed_package_names_at_least_one_repository(live_index) -> None:
    assert all(item.repos for item in live_index.entries)


def test_a_well_known_package_is_findable(live_index) -> None:
    results = live_index.search("portage")
    assert "sys-apps/portage" in {item.cp for item in results}


def test_details_of_portage_itself(portage_env) -> None:
    info = pkgs.details("sys-apps/portage", portage_env)
    assert info.cp == "sys-apps/portage"
    assert info.description
    assert info.versions
    assert info.is_installed, "sys-apps/portage must be installed for Portage to work at all"
    assert all(version.repo for version in info.versions)
    assert any(version.installed for version in info.versions)


def test_the_best_visible_version_is_one_of_the_listed_ones(portage_env) -> None:
    info = pkgs.details("sys-apps/portage", portage_env)
    assert info.best_visible is not None
    assert info.version(info.best_visible) is not None
    assert info.version(info.best_visible).is_installable


def test_an_unknown_package_raises(portage_env) -> None:
    with pytest.raises(pkgs.UnknownPackageError):
        pkgs.details("no-such-category/no-such-package", portage_env)


def test_without_a_repository_nothing_is_narrowed(portage_env) -> None:
    """A regression guard.

    The per-version repository is a loop variable and the restriction is a
    parameter; when the two shared a name, every unrestricted lookup silently
    answered as if the last repository read had been asked for.
    """
    info = pkgs.details("sys-apps/portage", portage_env)
    assert info.repo == ""
    assert info.best_visible == str(portage_env.portdb.xmatch(
        "bestmatch-visible", "sys-apps/portage"
    ))


def test_narrowing_the_details_to_one_repository(portage_env) -> None:
    """Asking for one repository must not answer with another one's ebuilds."""
    main = portage_env.main_repo_name
    info = pkgs.details("sys-apps/portage", portage_env, repo=main)
    assert info.repo == main
    assert info.versions
    assert {version.repo for version in info.versions} == {main}
    assert info.repos == (main,)
    assert info.best_visible is None or info.version(info.best_visible) is not None


def test_a_repository_that_does_not_carry_the_package_offers_no_versions(
    portage_env,
) -> None:
    info = pkgs.details("sys-apps/portage", portage_env, repo="no-such-repository")
    assert info.versions == ()
    assert info.best_visible is None
    # Installed is never narrowed: the package is on the system either way.
    assert info.is_installed


def test_a_version_is_installed_only_under_the_repository_it_came_from(
    portage_env,
) -> None:
    """The same version in two repositories is not the same ebuild.

    Marking the other repository's copy as installed would promise a rebuild
    that Portage would not perform.
    """
    info = pkgs.details("sys-apps/portage", portage_env)
    installed = {(entry.cpv, entry.repo) for entry in info.installed if entry.repo}
    if not installed:  # pragma: no cover - a vardb entry without a repository
        pytest.skip("nothing here records the repository it was built from")
    for version in info.versions:
        if version.installed:
            assert (version.cpv, version.repo) in installed


def test_the_state_line_can_be_narrowed_to_one_repository(portage_env) -> None:
    main = portage_env.main_repo_name
    everywhere = pkgs.package_state("sys-apps/portage", portage_env)
    here = pkgs.package_state("sys-apps/portage", portage_env, repo=main)
    assert here.installed_version == everywhere.installed_version
    assert here.newest_version is not None

    nowhere = pkgs.package_state("sys-apps/portage", portage_env, repo="no-such-repository")
    assert nowhere.newest_version is None
    assert nowhere.available_version is None
    assert nowhere.installed_version == everywhere.installed_version


def test_repositories_are_listed_in_priority_order(portage_env) -> None:
    entries = repos_mod.list_repositories(portage_env, count_packages=False)
    assert [r.name for r in entries] == list(portage_env.repo_names)
    assert sum(1 for r in entries if r.is_main) == 1


def test_the_main_repository_has_packages_and_a_sync_date(portage_env) -> None:
    main = repos_mod.repository(portage_env.main_repo_name, portage_env, count_packages=True)
    assert main is not None
    assert main.package_count and main.package_count > 1000
    assert main.last_sync is not None


def test_world_entries_resolve_to_installed_packages(portage_env) -> None:
    entries = worldset.world_entries(portage_env)
    assert entries, "an empty @world would make the rest of this meaningless"
    assert all("/" in item.cp for item in entries)
    satisfied = [item for item in entries if item.is_satisfied]
    assert len(satisfied) >= len(entries) - 2


def test_installed_packages_carry_sizes(portage_env) -> None:
    installed = worldset.installed_packages(portage_env)
    assert len(installed) > 100
    assert worldset.total_installed_size(installed) > 0
    assert {p.cp for p in installed} == set(worldset.installed_cps(portage_env))


def test_resolve_cp_accepts_atoms_and_names(portage_env, live_index) -> None:
    assert pkgs.resolve_cp("sys-apps/portage") == "sys-apps/portage"
    assert pkgs.resolve_cp(">=sys-apps/portage-3.0") == "sys-apps/portage"
    assert pkgs.resolve_cp("mpv", live_index) == "media-video/mpv"
    assert pkgs.resolve_cp("not an atom") is None


def test_an_ambiguous_name_is_not_resolved_to_a_guess(live_index) -> None:
    # acct-group/portage, acct-user/portage and sys-apps/portage all exist.
    assert len(pkgs.matching_cps("portage", live_index)) > 1
    assert pkgs.resolve_cp("portage", live_index) is None


@pytest.mark.parametrize("argv", [["--json", "info"], ["--json", "repos", "--fast"], ["world"]])
def test_the_diagnostic_cli_runs(portage_env, argv, capsys) -> None:
    assert cli_main(argv) == 0
    assert capsys.readouterr().out
