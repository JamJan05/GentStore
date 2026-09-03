"""The numbers the site states about the application, and the script that moves them.

The page announced 1.3.0 for as long as it took somebody to notice, because
cutting a release touched four files on `main` and nothing at all over here.
`--check` is the half of that script these tests run: it is what stops the two
language files drifting apart from each other between releases, and what the
release workflow leans on to know it changed what it meant to.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import set_version


@pytest.fixture
def content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A copy of the real content files, so a test can rewrite them."""
    directory = tmp_path / "content"
    directory.mkdir()
    for source in set_version.CONTENT_DIR.glob("*.json"):
        (directory / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(set_version, "CONTENT_DIR", directory)
    return directory


def read(directory: Path, name: str) -> dict:
    return json.loads((directory / name).read_text(encoding="utf-8"))


# -- the files as they are --------------------------------------------------

def test_the_shipped_content_agrees_with_itself() -> None:
    """Two languages, one version and one test count between them."""
    assert set_version.main(["--check"]) == 0


def test_every_language_states_the_same_version() -> None:
    versions = {
        set_version.stated(set_version.load(path), place, set_version.VERSION_RE)
        for path in set_version.content_files()
        for place in set_version.VERSION_AT
    }
    assert len(versions) == 1, f"the site states {versions}"


# -- rewriting --------------------------------------------------------------

def test_a_bump_moves_every_place_that_states_the_version(content: Path) -> None:
    assert set_version.main(["9.9.9"]) == 0
    assert set_version.main(["--check", "9.9.9"]) == 0
    for name in ("en.json", "pl.json"):
        document = read(content, name)
        assert document["header"]["version"] == "9.9.9"
        assert "9.9.9" in document["status"]["title"]


def test_the_test_count_moves_on_its_own(content: Path) -> None:
    """--tests without a version: the count goes stale between releases too."""
    before = read(content, "en.json")["header"]["version"]
    assert set_version.main(["--tests", "1234"]) == 0
    document = read(content, "en.json")
    assert document["header"]["version"] == before
    assert "1234 tests" in document["hero"]["badges"]
    assert document["status"]["caveat"]["body"].startswith("1234 tests")


def test_the_formatting_survives_a_rewrite(content: Path) -> None:
    """One number changed is one line in the diff, not a re-punctuated file."""
    before = (content / "en.json").read_text(encoding="utf-8").splitlines()
    set_version.main(["9.9.9", "--tests", "1234"])
    after = (content / "en.json").read_text(encoding="utf-8").splitlines()
    assert len(before) == len(after)
    assert sum(a != b for a, b in zip(before, after, strict=True)) == 4


def test_a_rewrite_that_changes_nothing_writes_nothing(content: Path) -> None:
    current = read(content, "en.json")["header"]["version"]
    stamp = (content / "en.json").stat().st_mtime_ns
    assert set_version.main([current]) == 0
    assert (content / "en.json").stat().st_mtime_ns == stamp


# -- the failures worth having ----------------------------------------------

def test_a_reworded_line_stops_the_script(content: Path) -> None:
    """A silent no-op is the whole failure this exists to prevent.

    If the caveat is ever rewritten so the count no longer leads it, the pattern
    finds nothing — and the useful answer is an error, not a run that reports
    success while leaving the old number on the page.
    """
    document = read(content, "en.json")
    document["status"]["caveat"]["body"] = "Tests: 572 of them pass."
    (content / "en.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")

    assert set_version.main(["--tests", "1234"]) == 1
    assert set_version.main(["--check"]) == 1


def test_two_languages_that_disagree_are_caught(content: Path) -> None:
    document = read(content, "pl.json")
    document["header"]["version"] = "0.0.1"
    (content / "pl.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")

    assert set_version.main(["--check"]) == 1


def test_check_against_a_version_the_files_do_not_state(content: Path) -> None:
    assert set_version.main(["--check", "0.0.1"]) == 1


def test_a_bad_version_is_refused(content: Path) -> None:
    with pytest.raises(SystemExit) as refused:
        set_version.main(["1.3"])
    assert refused.value.code == 2


# -- the heading it will not touch ------------------------------------------

def test_the_highlights_heading_is_left_alone_and_reported(
    content: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """"New in 1.3.0" over 1.3.0's list stays true; moving it would not.

    The list under that heading is written by hand for each release. A script
    that relabelled it would be claiming, in public, that a reader is looking at
    what changed in a version nobody wrote a word about.
    """
    before = read(content, "en.json")["status"]["changes_title"]
    assert set_version.main(["9.9.9"]) == 0

    assert read(content, "en.json")["status"]["changes_title"] == before
    assert "still heads its highlights" in capsys.readouterr().err
