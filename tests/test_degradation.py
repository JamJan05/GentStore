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

"""What happens when things are missing.

The final review from Docs/05-session-plan.md §S12: an empty ``/etc/portage``, no
optional tools, no network, no privileged helper. None of those is an error the
user caused, and none of them may produce a traceback or an empty screen with
no explanation. Every one of them has to come back as an answer.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from gentstore.core import binrepos, cfgfiles, confedit, glsa, makeconf, news, overlays, repos
from gentstore.core.backup import list_backups
from gentstore.runner import privilege


@pytest.fixture
def empty(tmp_path: Path) -> Path:
    """A configuration root with nothing in it — a freshly built stage."""
    root = tmp_path / "portage"
    root.mkdir()
    return root


# -- an empty /etc/portage --------------------------------------------------


def test_no_make_conf_is_an_empty_answer_not_a_failure(empty: Path) -> None:
    conf = makeconf.load(path=empty / "make.conf")
    assert not conf.exists
    assert conf.assignments == {}
    assert conf.value("MAKEOPTS") == ""


def test_setting_a_variable_in_a_file_that_does_not_exist_appends_it(empty: Path) -> None:
    conf = makeconf.load(path=empty / "make.conf")
    plan = makeconf.plan_set(conf, "MAKEOPTS", "-j4")
    assert plan.op == "append_line"
    assert plan.line == 'MAKEOPTS="-j4"'


def test_no_package_use_yet_plans_the_recommended_directory(empty: Path) -> None:
    path, kind, existing = confedit.locate("package.use", "media-video/mpv", config_dir=empty)
    assert kind is confedit.TargetKind.NEW_DIRECTORY
    assert path == empty / "package.use" / "mpv"
    assert existing is None


@pytest.mark.parametrize(
    "name", ["package.use", "package.mask", "package.accept_keywords", "package.license"]
)
def test_reading_a_file_that_is_not_there_gives_nothing(empty: Path, name: str) -> None:
    assert confedit.read_entries(name, config_dir=empty) == ()


def test_no_binrepos_conf_means_no_binary_hosts(empty: Path) -> None:
    assert binrepos.read(config_dir=empty.parent) == ()


def test_no_repos_conf_means_no_sections_to_show(empty: Path) -> None:
    assert repos.config_files(config_dir=empty) == ()
    assert repos.config_section("gentoo", config_dir=empty) is None


def test_nothing_is_masked_when_there_is_no_package_mask(empty: Path) -> None:
    assert repos.masked_repos(config_dir=empty) == frozenset()
    assert not repos.is_masked("guru", config_dir=empty)


def test_no_pending_configuration_files_in_an_empty_tree(empty: Path) -> None:
    assert cfgfiles.find(roots=(empty,), masks=()) == ()


def test_no_backups_yet(tmp_path: Path) -> None:
    assert list_backups(tmp_path) == ()


def test_no_news_state_means_nothing_unread(tmp_path: Path) -> None:
    assert news.unread_ids("gentoo", tmp_path) == frozenset()


def test_no_elog_directory_means_no_messages(tmp_path: Path) -> None:
    from gentstore.core import elog

    assert elog.load(directory=tmp_path / "absent") == ()


# -- optional tools that are not installed ----------------------------------


def test_a_missing_glsa_check_is_reported_not_raised(monkeypatch) -> None:
    monkeypatch.setattr(glsa.shutil, "which", lambda _name: None)
    assert not glsa.is_available()
    assert glsa.PACKAGE == "app-portage/gentoolkit"


def test_a_missing_cpuid2cpuflags_names_the_package(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    suggestion = makeconf.suggest_cpu_flags()
    assert not suggestion.is_available
    assert suggestion.missing == makeconf.CPUID_PACKAGE


def test_a_makeopts_suggestion_survives_a_system_with_no_meminfo(monkeypatch) -> None:
    monkeypatch.setattr(makeconf, "_total_memory_gib", lambda: None)
    suggestion = makeconf.suggest_makeopts()
    assert suggestion.is_available
    assert suggestion.reason == "cores"


def test_no_repository_catalogue_yet(monkeypatch, tmp_path: Path) -> None:
    """Before the first `eselect repository list`, there is nothing to search."""
    monkeypatch.setattr(overlays, "CACHE_PATHS", (tmp_path / "absent.xml",))
    catalogue = overlays.load()
    assert catalogue.is_empty
    assert catalogue.search("steam") == []


# -- no way to become root --------------------------------------------------


def test_no_privilege_tool_is_an_explanation_not_a_crash(monkeypatch) -> None:
    monkeypatch.setattr(privilege.shutil, "which", lambda _name: None)
    monkeypatch.setattr(privilege, "preferred", "auto")
    escalation = privilege.detect()
    assert not escalation.is_available
    assert "pkexec" in (escalation.problem or "")


def test_asking_for_a_tool_that_is_not_there_falls_back(monkeypatch) -> None:
    """A preference is a preference, not an instruction to invent a program."""
    monkeypatch.setattr(
        privilege.shutil, "which", lambda name: "/usr/bin/pkexec" if name == "pkexec" else None
    )
    monkeypatch.setattr(privilege, "preferred", "sudo")
    escalation = privilege.detect()
    assert escalation.kind == "pkexec", "sudo is not installed, so pkexec it is"


def test_a_helper_request_without_privileges_comes_back_as_a_result(monkeypatch) -> None:
    from gentstore.runner import helper_client

    monkeypatch.setattr(
        privilege, "detect", lambda: privilege.Escalation("none", None, "nothing here")
    )
    result = helper_client.request("backup")
    assert not result.ok
    assert result.code == "no_privilege"


def test_no_helper_installed_and_none_in_the_tree(monkeypatch) -> None:
    from gentstore.runner import helper_client

    monkeypatch.setattr(privilege, "helper_command", lambda: None)
    monkeypatch.setattr(
        privilege, "detect", lambda: privilege.Escalation("direct", None)
    )
    result = helper_client.request("backup")
    assert result.code == "no_helper"
    assert privilege.HELPER_NAME in result.error


# -- no network -------------------------------------------------------------


def test_nothing_reads_the_network_on_its_own() -> None:
    """Docs/04-privileges.md §8: the only traffic is the programs we run.

    Checked by looking: no module under core/ may import a network client. The
    repository catalogue is the one thing that needs fetching, and it is
    fetched by `eselect repository list` as a visible command.
    """
    import ast

    forbidden = {"urllib", "http", "requests", "socket", "ftplib", "httpx", "aiohttp"}
    offenders = []
    for source in sorted((Path(__file__).resolve().parent.parent / "gentstore").rglob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.split(".")[0] in forbidden:
                    offenders.append(f"{source.name}:{node.lineno}: {name}")
    assert not offenders, "Gentstore does not fetch anything itself:\n" + "\n".join(offenders)
