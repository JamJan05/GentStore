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

"""Tests for the repository catalogue and for repository-level configuration.

The catalogue is parsed from a file Gentoo publishes and eselect caches, so the
tests use a small hand-written one for the parsing rules and the machine's real
copy for the shape of the thing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gentstore.core import overlays, repos
from gentstore.core.portage_env import PortageUnavailableError, env
from gentstore.runner import eselect

SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<repositories xmlns="" version="1.0">
  <repo quality="experimental" status="official">
    <name>guru</name>
    <description lang="en">Ebuild repository maintained by Gentoo users</description>
    <description lang="de">Von Nutzern gepflegtes Repository</description>
    <homepage>https://wiki.gentoo.org/wiki/Project:GURU</homepage>
    <owner type="project">
      <email>guru@gentoo.org</email>
      <name>GURU</name>
    </owner>
    <source type="git">git+ssh://github.com/gentoo-mirror/guru.git</source>
    <source type="git">https://github.com/gentoo-mirror/guru.git</source>
  </repo>
  <repo quality="testing" status="unofficial">
    <name>steam-overlay</name>
    <description lang="en">Overlay for Valve's Steam client</description>
    <homepage>https://github.com/anyc/steam-overlay</homepage>
    <source type="git">https://github.com/anyc/steam-overlay.git</source>
  </repo>
  <repo quality="core" status="official">
    <name>gentoo</name>
    <description lang="en">Official Gentoo ebuild repository</description>
    <source type="rsync">rsync://rsync.gentoo.org/gentoo-portage</source>
  </repo>
</repositories>
"""


@pytest.fixture
def catalogue(tmp_path: Path) -> overlays.Catalogue:
    path = tmp_path / "repositories.xml"
    path.write_text(SAMPLE, encoding="utf-8")
    return overlays.parse(path)


# -- parsing ----------------------------------------------------------------


def test_every_repository_is_read(catalogue: overlays.Catalogue) -> None:
    assert len(catalogue) == 3
    assert {entry.name for entry in catalogue.entries} == {"guru", "steam-overlay", "gentoo"}


def test_the_english_description_is_the_one_taken(catalogue: overlays.Catalogue) -> None:
    guru = catalogue.get("guru")
    assert guru.description == "Ebuild repository maintained by Gentoo users"


def test_owners_are_joined_into_something_readable(catalogue: overlays.Catalogue) -> None:
    assert catalogue.get("guru").owners == ("GURU <guru@gentoo.org>",)


def test_an_anonymous_source_is_preferred_over_ssh(catalogue: overlays.Catalogue) -> None:
    """git+ssh needs a key nobody syncing a public overlay is expected to have."""
    assert catalogue.get("guru").preferred_source == (
        "git",
        "https://github.com/gentoo-mirror/guru.git",
    )


def test_official_is_about_who_runs_it_not_about_quality(
    catalogue: overlays.Catalogue,
) -> None:
    guru = catalogue.get("guru")
    assert guru.is_official
    assert guru.quality == "experimental"
    assert not catalogue.get("steam-overlay").is_official


def test_a_broken_file_gives_an_empty_catalogue(tmp_path: Path) -> None:
    path = tmp_path / "repositories.xml"
    path.write_text("<repositories", encoding="utf-8")
    assert overlays.parse(path).is_empty


def test_a_missing_file_gives_an_empty_catalogue(tmp_path: Path) -> None:
    assert overlays.parse(tmp_path / "absent.xml").is_empty


# -- searching --------------------------------------------------------------


def test_an_exact_name_wins(catalogue: overlays.Catalogue) -> None:
    assert [e.name for e in catalogue.search("guru")] == ["guru"]


def test_a_partial_name_finds_the_overlay(catalogue: overlays.Catalogue) -> None:
    assert [e.name for e in catalogue.search("steam")] == ["steam-overlay"]


def test_the_description_is_searched_too(catalogue: overlays.Catalogue) -> None:
    assert [e.name for e in catalogue.search("Valve")] == ["steam-overlay"]


def test_within_a_rank_the_more_trustworthy_comes_first(catalogue: overlays.Catalogue) -> None:
    """"gentoo" and "steam-overlay" both merely contain "o"; core beats testing."""
    names = [e.name for e in catalogue.search("o")]
    assert names.index("gentoo") < names.index("steam-overlay")


def test_a_name_match_beats_a_description_match(catalogue: overlays.Catalogue) -> None:
    """"guru" has the letter in its name; "gentoo" only in its description."""
    names = [e.name for e in catalogue.search("u")]
    assert names.index("guru") < names.index("gentoo")


def test_an_empty_query_finds_nothing(catalogue: overlays.Catalogue) -> None:
    assert catalogue.search("   ") == []


# -- what eselect will accept ----------------------------------------------


@pytest.mark.parametrize("name", ["guru", "steam-overlay", "my_repo", "x11-extras", "a.b"])
def test_sensible_repository_names_are_allowed(name: str) -> None:
    assert overlays.is_valid_name(name)


@pytest.mark.parametrize("name", ["", "-leading", "with space", "../escape", "sla/sh"])
def test_nonsense_repository_names_are_refused(name: str) -> None:
    assert not overlays.is_valid_name(name)


@pytest.mark.parametrize(
    "uri",
    [
        "https://github.com/x/y.git",
        "git://anongit.gentoo.org/repo.git",
        "rsync://rsync.gentoo.org/gentoo-portage",
        "git@github.com:x/y.git",
        "ssh://git@example.org/repo.git",
        "file:///var/db/repos/local",
    ],
)
def test_plausible_urls_are_allowed(uri: str) -> None:
    assert overlays.is_valid_uri(uri)


@pytest.mark.parametrize("uri", ["", "   ", "just-a-word", "-u://x", "wss://x/y"])
def test_nonsense_urls_are_refused(uri: str) -> None:
    assert not overlays.is_valid_uri(uri)


@pytest.mark.parametrize(
    "uri",
    [
        "ext::sh -c 'touch /tmp/pwn' ://",
        "ext::git-upload-pack ://elsewhere",
        "fd::7 ://",
    ],
)
def test_a_url_that_is_really_a_command_is_refused(uri: str) -> None:
    """git reads ``ext::`` as "run this"; the "://" on the end is decoration.

    The URL is synced as root's business, so a URL that is really a command is
    a way to run a command — and the one thing the Add dialog warns about is
    ebuilds, which would leave somebody looking in the wrong direction. The
    launcher checks the same string again on the far side of pkexec.
    """
    assert not overlays.is_valid_uri(uri)


# -- repos.conf -------------------------------------------------------------


CONF = """# created by eselect-repo

[guru]
location = /var/db/repos/guru
sync-type = git
sync-uri = https://github.com/gentoo-mirror/guru.git

[steam-overlay]
location = /var/db/repos/steam-overlay
sync-type = git
"""


@pytest.fixture
def portage_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "repos.conf"
    directory.mkdir()
    (directory / "eselect-repo.conf").write_text(CONF, encoding="utf-8")
    return tmp_path


def test_the_section_that_defines_a_repository_is_found(portage_dir: Path) -> None:
    found = repos.config_section("guru", config_dir=portage_dir)
    assert found is not None
    path, text = found
    assert path.name == "eselect-repo.conf"
    assert text.splitlines()[0] == "[guru]"
    assert "sync-uri = https://github.com/gentoo-mirror/guru.git" in text


def test_a_section_stops_at_the_next_one(portage_dir: Path) -> None:
    _path, text = repos.config_section("guru", config_dir=portage_dir)
    assert "steam-overlay" not in text


def test_the_last_section_runs_to_the_end(portage_dir: Path) -> None:
    _path, text = repos.config_section("steam-overlay", config_dir=portage_dir)
    assert text.splitlines()[0] == "[steam-overlay]"
    assert "sync-type = git" in text


def test_a_repository_with_no_section_is_reported_as_such(portage_dir: Path) -> None:
    assert repos.config_section("gentoo", config_dir=portage_dir) is None


# -- hiding a repository ----------------------------------------------------


def test_the_mask_atom_covers_every_package_from_one_repository() -> None:
    assert repos.mask_atom("guru") == "*/*::guru"


def test_masking_writes_one_line_to_a_file_named_after_the_repository(
    tmp_path: Path,
) -> None:
    (tmp_path / "package.mask").mkdir()
    plan = repos.plan_mask("guru", config_dir=tmp_path)
    assert plan.op == "append_line"
    assert plan.path == tmp_path / "package.mask" / "guru"
    assert plan.line == "*/*::guru"


def test_a_masked_repository_is_recognised(tmp_path: Path) -> None:
    directory = tmp_path / "package.mask"
    directory.mkdir()
    (directory / "guru").write_text("*/*::guru\n", encoding="utf-8")

    assert repos.is_masked("guru", config_dir=tmp_path)
    assert not repos.is_masked("steam-overlay", config_dir=tmp_path)
    assert repos.masked_repos(config_dir=tmp_path) == frozenset({"guru"})


def test_unmasking_takes_the_line_back_out(tmp_path: Path) -> None:
    directory = tmp_path / "package.mask"
    directory.mkdir()
    (directory / "guru").write_text("# mine\n*/*::guru\n", encoding="utf-8")

    plan = repos.plan_unmask("guru", config_dir=tmp_path)
    assert plan.op == "remove_line"
    assert plan.previous == "*/*::guru"


def test_ordinary_package_masks_are_not_mistaken_for_repository_masks(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "package.mask"
    directory.mkdir()
    (directory / "croc").write_text("=acct-group/croc-0-r2\n", encoding="utf-8")
    assert repos.masked_repos(config_dir=tmp_path) == frozenset()


# -- the commands -----------------------------------------------------------


def test_refreshing_the_catalogue_needs_no_privileges() -> None:
    """It writes to the user's own cache, so asking for a password would be rude."""
    spec = eselect.list_repositories()
    assert not spec.privileged
    assert spec.argv == ("eselect", "repository", "list")


def test_changing_repositories_does_need_privileges() -> None:
    for spec in (
        eselect.enable("guru"),
        eselect.add("mine", "git", "https://example.invalid/x.git"),
        eselect.remove("guru"),
        eselect.sync("guru"),
    ):
        assert spec.privileged


def test_removal_forces_by_default() -> None:
    """Without -f eselect refuses exactly when the interface has already asked."""
    assert "-f" in eselect.remove("guru").argv
    assert "-f" not in eselect.remove("guru", force=False).argv


def test_syncing_one_repository_uses_emaint() -> None:
    assert eselect.sync("guru").argv == ("emaint", "sync", "-r", "guru")


# -- against the real system ------------------------------------------------


@pytest.fixture(scope="session")
def portage_env():
    try:
        return env()
    except PortageUnavailableError as exc:  # pragma: no cover - non-Gentoo host
        pytest.skip(f"no usable Portage installation: {exc}")


def test_the_machines_own_catalogue_reads(portage_env) -> None:
    catalogue = overlays.load()
    if catalogue.is_empty:  # pragma: no cover - nobody has run eselect here
        pytest.skip("no repository catalogue has been fetched on this machine")
    assert len(catalogue) > 100
    assert catalogue.get("guru") is not None
    assert all(entry.name for entry in catalogue.entries)


def test_every_configured_repository_has_a_section_or_comes_from_the_profile(
    portage_env,
) -> None:
    for info in repos.list_repositories(portage_env, count_packages=False):
        section = repos.config_section(info.name, portage_env)
        assert section is None or f"[{info.name}]" in section[1]


def test_the_installed_packages_add_up(portage_env) -> None:
    """Every installed package came from exactly one configured repository."""
    from_repos = sum(
        len(repos.installed_from(info.name, portage_env))
        for info in repos.list_repositories(portage_env, count_packages=False)
    )
    assert 0 < from_repos <= len(portage_env.vardb.cpv_all())
