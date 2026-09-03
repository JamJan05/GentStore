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

"""The search-index cache: what it keeps, and everything that must invalidate it.

Most of these run against a repository made of empty directories, because that
is all :func:`~gentstore.core.index_cache.fingerprint` looks at, and against a
hand-made index, because the file format does not care where the rows came from.
The two at the end ask the real machine the only question a fixture cannot: that
a cached index says the same thing as one built from Portage.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gentstore.core import index_cache
from gentstore.core import packages as pkgs


class FakeEnv:
    """Enough of :class:`~gentstore.core.portage_env.PortageEnv` for the cache."""

    def __init__(self, locations: dict[str, Path], installed: tuple[str, ...] = ()) -> None:
        self._locations = locations
        self.vardb = FakeVardb(installed)

    @property
    def repo_names(self) -> tuple[str, ...]:
        return tuple(self._locations)

    def repo_location(self, name: str) -> str | None:
        location = self._locations.get(name)
        return str(location) if location is not None else None


class FakeCpv(str):
    """What ``vardb.cpv_all()`` really answers: a string that knows its ``cp``."""

    @property
    def cp(self) -> str:
        version = self.rsplit("-", 1)[0]
        return version


class FakeVardb:
    def __init__(self, installed: tuple[str, ...]) -> None:
        self._installed = tuple(FakeCpv(item) for item in installed)

    def cpv_all(self) -> tuple[FakeCpv, ...]:
        return self._installed


def make_repo(root: Path, categories: tuple[str, ...] = ("app-editors", "media-video")) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "metadata").mkdir(exist_ok=True)
    for category in categories:
        (root / category).mkdir(exist_ok=True)
    return root


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
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the cache at a throwaway runtime directory."""
    runtime = tmp_path / "run"
    runtime.mkdir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    monkeypatch.delenv(index_cache.ENV_VARIABLE, raising=False)
    return runtime / "gentstore"


@pytest.fixture
def env(tmp_path: Path) -> FakeEnv:
    return FakeEnv(
        {"gentoo": make_repo(tmp_path / "gentoo"), "guru": make_repo(tmp_path / "guru")},
        installed=("app-editors/vim-9.1",),
    )


@pytest.fixture
def index() -> pkgs.SearchIndex:
    return pkgs.SearchIndex(
        entries=(
            entry("media-video/mpv", "Media player for the command line"),
            entry("app-editors/vim", "Vi IMproved, an updated version of vi"),
            entry("gui-apps/mpvpaper", "A video wallpaper program", repos=("guru", "gentoo")),
        ),
        installed=frozenset({"media-video/mpv"}),
        repos=("gentoo", "guru"),
        built_at=1_700_000_000.0,
        build_seconds=8.5,
    )


# -- the round trip ---------------------------------------------------------


def test_a_stored_index_comes_back_the_same(cache_dir, env, index) -> None:  # noqa: ANN001
    assert index_cache.store(index, env)
    restored = index_cache.load(env)
    assert restored is not None
    assert [e.cp for e in restored.entries] == [e.cp for e in index.entries]
    assert [e.description for e in restored.entries] == [e.description for e in index.entries]
    assert [e.repos for e in restored.entries] == [e.repos for e in index.entries]
    assert restored.repos == index.repos
    assert restored.build_seconds == index.build_seconds
    assert restored.built_at == index.built_at


def test_a_restored_index_can_be_searched(cache_dir, env, index) -> None:  # noqa: ANN001
    index_cache.store(index, env)
    restored = index_cache.load(env)
    assert restored is not None
    # The folded fields are derived on load, so a case-insensitive match proves
    # they were rebuilt rather than left empty.
    assert [item.cp for item in restored.search("MPV", limit=2)] == [
        "media-video/mpv",
        "gui-apps/mpvpaper",
    ]
    assert restored.get("app-editors/vim") is not None


def test_what_is_installed_is_re_read_rather_than_stored(cache_dir, env, index) -> None:  # noqa: ANN001
    """The one field that changes without the tree changing."""
    index_cache.store(index, env)
    env.vardb = FakeVardb(("gui-apps/mpvpaper-1.0",))
    restored = index_cache.load(env)
    assert restored is not None
    assert restored.installed == frozenset({"gui-apps/mpvpaper"})


def test_the_cache_file_is_written_where_the_session_ends(cache_dir, env, index) -> None:  # noqa: ANN001
    index_cache.store(index, env)
    assert index_cache.path() == cache_dir / "search-index.json"
    assert index_cache.path().is_file()


def test_without_a_runtime_directory_it_falls_back_to_the_cache_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    assert index_cache.directory() == tmp_path / "cache" / "gentstore"


# -- invalidation -----------------------------------------------------------


def test_a_package_added_to_a_repository_invalidates_it(cache_dir, env, index, tmp_path) -> None:  # noqa: ANN001
    index_cache.store(index, env)
    assert index_cache.load(env) is not None
    # A new cat/pkg is a new directory inside a category, which writes the
    # category directory — the thing the fingerprint watches.
    (tmp_path / "guru" / "media-video" / "newpkg").mkdir(parents=True)
    assert index_cache.load(env) is None


def test_enabling_a_repository_invalidates_it(cache_dir, env, index, tmp_path) -> None:  # noqa: ANN001
    index_cache.store(index, env)
    env._locations["extra"] = make_repo(tmp_path / "extra")
    assert index_cache.load(env) is None


def test_a_repository_moving_invalidates_it(cache_dir, env, index, tmp_path) -> None:  # noqa: ANN001
    index_cache.store(index, env)
    env._locations["guru"] = make_repo(tmp_path / "guru-elsewhere")
    assert index_cache.load(env) is None


def test_a_repository_that_is_not_on_disk_is_not_an_error(tmp_path, cache_dir, index) -> None:  # noqa: ANN001
    absent = FakeEnv({"gone": tmp_path / "not-here"})
    assert index_cache.store(index, absent)
    assert index_cache.load(absent) is not None


def test_discarding_removes_the_file(cache_dir, env, index) -> None:  # noqa: ANN001
    index_cache.store(index, env)
    index_cache.discard()
    assert not index_cache.path().exists()
    assert index_cache.load(env) is None
    # And a second call has nothing to do rather than something to fail at.
    index_cache.discard()


# -- a file that cannot be trusted -----------------------------------------


def test_a_corrupt_file_is_a_miss_not_a_crash(cache_dir, env, index) -> None:  # noqa: ANN001
    index_cache.store(index, env)
    index_cache.path().write_text("{not json at all", encoding="utf-8")
    assert index_cache.load(env) is None


def test_a_file_from_another_format_version_is_ignored(cache_dir, env, index) -> None:  # noqa: ANN001
    index_cache.store(index, env)
    document = json.loads(index_cache.path().read_text(encoding="utf-8"))
    document["format"] = index_cache.FORMAT + 1
    index_cache.path().write_text(json.dumps(document), encoding="utf-8")
    assert index_cache.load(env) is None


def test_a_row_of_the_wrong_shape_is_ignored(cache_dir, env, index) -> None:  # noqa: ANN001
    index_cache.store(index, env)
    document = json.loads(index_cache.path().read_text(encoding="utf-8"))
    document["entries"][1] = ["media-video/mpv"]
    index_cache.path().write_text(json.dumps(document), encoding="utf-8")
    assert index_cache.load(env) is None


def test_no_file_at_all_is_simply_a_miss(cache_dir, env) -> None:  # noqa: ANN001
    assert index_cache.load(env) is None


# -- the switch -------------------------------------------------------------


def test_the_cache_can_be_turned_off(cache_dir, env, index, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv(index_cache.ENV_VARIABLE, "0")
    assert not index_cache.enabled()
    assert index_cache.store(index, env) is False
    assert not index_cache.path().exists()
    monkeypatch.delenv(index_cache.ENV_VARIABLE)
    index_cache.store(index, env)
    monkeypatch.setenv(index_cache.ENV_VARIABLE, "0")
    assert index_cache.load(env) is None


def test_cached_index_builds_once_and_reads_afterwards(  # noqa: ANN001
    cache_dir, env, index, monkeypatch
) -> None:
    builds = []

    def build(_env=None, on_progress=None):  # noqa: ANN001, ANN202
        builds.append(_env)
        return index

    monkeypatch.setattr(pkgs.SearchIndex, "build", build)
    first = index_cache.cached_index(env)
    second = index_cache.cached_index(env)
    assert len(builds) == 1
    assert [e.cp for e in first.entries] == [e.cp for e in second.entries]


def test_progress_reaches_completion_even_on_a_hit(cache_dir, env, index) -> None:  # noqa: ANN001
    """The window's progress bar has to arrive at 100 %, cache or no cache."""
    index_cache.store(index, env)
    reported: list[tuple[int, int]] = []
    index_cache.cached_index(env, lambda done, total: reported.append((done, total)))
    assert reported[-1] == (len(index), len(index))


# -- against the real system ------------------------------------------------


def test_a_cached_index_matches_one_built_from_portage(  # noqa: ANN001
    portage_env, cache_dir
) -> None:
    built = pkgs.SearchIndex.build(portage_env)
    assert index_cache.store(built, portage_env)
    restored = index_cache.load(portage_env)
    assert restored is not None
    assert {e.cp for e in restored.entries} == {e.cp for e in built.entries}
    assert restored.repos == built.repos
    assert restored.installed == built.installed


def test_reading_the_cache_is_much_faster_than_building(portage_env, cache_dir) -> None:  # noqa: ANN001
    import time  # noqa: PLC0415 - only this test measures anything

    built = pkgs.SearchIndex.build(portage_env)
    index_cache.store(built, portage_env)
    started = time.monotonic()
    restored = index_cache.load(portage_env)
    elapsed = time.monotonic() - started
    assert restored is not None
    # The whole point of the file. Generous by a wide margin: it measures under
    # a second here against several to build, and a loaded CI machine is still
    # nowhere near the bound.
    assert elapsed < max(1.0, built.build_seconds / 2)
