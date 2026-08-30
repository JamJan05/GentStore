"""Tests for finding and diffing the files an update leaves behind.

Built entirely on temporary directories: this machine has no pending ``._cfg``
files, and creating one in the real ``/etc`` to test against would be exactly
the kind of thing the project promises not to do.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gentstore.core import cfgfiles
from gentstore.core.cfgfiles import CFG_PREFIX, DiffKind


@pytest.fixture
def etc(tmp_path: Path) -> Path:
    directory = tmp_path / "etc"
    directory.mkdir()
    return directory


def pending(directory: Path, name: str, old: str | None, new: str) -> Path:
    if old is not None:
        (directory / name).write_text(old, encoding="utf-8")
    candidate = directory / f"._cfg0000_{name}"
    candidate.write_text(new, encoding="utf-8")
    return candidate


def find(etc: Path, masks: tuple[Path, ...] = ()) -> tuple:
    """Scan without touching Portage: the owner lookup needs a real vardb."""
    found = cfgfiles._scan(etc, masks)
    return tuple(cfgfiles._with_diffstat(item, "") for item in found)


# -- the name ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "number", "target"),
    [
        ("._cfg0000_make.conf", "0000", "make.conf"),
        ("._cfg0003_fstab", "0003", "fstab"),
        ("._cfg0000_.bashrc", "0000", ".bashrc"),
    ],
)
def test_the_portage_naming_is_understood(name: str, number: str, target: str) -> None:
    match = CFG_PREFIX.match(name)
    assert match is not None
    assert match.group("number") == number
    assert match.group("name") == target


@pytest.mark.parametrize("name", ["make.conf", "._cfg_make.conf", "._cfg00_x", "cfg0000_x"])
def test_other_names_are_not_configuration_candidates(name: str) -> None:
    assert CFG_PREFIX.match(name) is None


# -- finding ----------------------------------------------------------------


def test_a_pending_file_is_found_with_its_target(etc: Path) -> None:
    pending(etc, "fstab", "old\n", "new\n")
    (found,) = find(etc)

    assert found.candidate.name == "._cfg0000_fstab"
    assert found.target == etc / "fstab"
    assert found.number == 0
    assert not found.is_new_file


def test_subdirectories_are_searched_too(etc: Path) -> None:
    nested = etc / "conf.d"
    nested.mkdir()
    pending(nested, "hostname", "a\n", "b\n")
    assert len(find(etc)) == 1


def test_ordinary_files_are_left_alone(etc: Path) -> None:
    (etc / "fstab").write_text("x\n", encoding="utf-8")
    (etc / "hosts").write_text("y\n", encoding="utf-8")
    assert find(etc) == ()


def test_several_pending_versions_of_one_file_are_all_listed(etc: Path) -> None:
    (etc / "make.conf").write_text("old\n", encoding="utf-8")
    (etc / "._cfg0000_make.conf").write_text("first\n", encoding="utf-8")
    (etc / "._cfg0001_make.conf").write_text("second\n", encoding="utf-8")

    found = sorted(find(etc), key=lambda item: item.number)
    assert [item.number for item in found] == [0, 1]


def test_a_file_the_package_is_adding_outright_is_marked_as_new(etc: Path) -> None:
    pending(etc, "brand-new.conf", None, "hello\n")
    (found,) = find(etc)
    assert found.is_new_file
    assert found.removed == 0


def test_masked_directories_are_skipped(etc: Path) -> None:
    """CONFIG_PROTECT_MASK is where Portage overwrites without asking."""
    masked = etc / "env.d"
    masked.mkdir()
    pending(masked, "99gcc", "a\n", "b\n")
    pending(etc, "fstab", "a\n", "b\n")

    found = find(etc, masks=(masked,))
    assert [item.name for item in found] == ["fstab"]


def test_a_masked_single_file_is_skipped(etc: Path) -> None:
    pending(etc, "gentoo-release", "a\n", "b\n")
    assert find(etc, masks=(etc / "gentoo-release",)) == ()


# -- counting ---------------------------------------------------------------


def test_the_number_of_changed_lines_is_counted(etc: Path) -> None:
    pending(
        etc,
        "make.conf",
        "COMMON_FLAGS=\"-O2\"\nMAKEOPTS=\"-j4\"\nUSE=\"X\"\n",
        "COMMON_FLAGS=\"-O2\"\nMAKEOPTS=\"-j8\"\nUSE=\"X\"\nNEW=\"1\"\n",
    )
    (found,) = find(etc)
    assert found.removed == 1
    assert found.added == 2
    assert found.changed_lines == 3


def test_an_identical_file_shows_no_changes(etc: Path) -> None:
    pending(etc, "fstab", "same\n", "same\n")
    (found,) = find(etc)
    assert found.changed_lines == 0


# -- the difference ---------------------------------------------------------


def test_the_diff_marks_each_line_for_colouring(etc: Path) -> None:
    pending(etc, "fstab", "keep\nold\n", "keep\nnew\n")
    (found,) = find(etc)

    lines = cfgfiles.diff(found)
    kinds = {line.kind for line in lines}
    assert DiffKind.HEADER in kinds
    assert DiffKind.REMOVED in kinds
    assert DiffKind.ADDED in kinds

    removed = [line.text for line in lines if line.kind is DiffKind.REMOVED]
    added = [line.text for line in lines if line.kind is DiffKind.ADDED]
    assert removed == ["-old"]
    assert added == ["+new"]


def test_the_diff_of_a_new_file_is_all_additions(etc: Path) -> None:
    pending(etc, "brand-new.conf", None, "one\ntwo\n")
    (found,) = find(etc)
    lines = cfgfiles.diff(found)
    assert not [line for line in lines if line.kind is DiffKind.REMOVED]
    assert len([line for line in lines if line.kind is DiffKind.ADDED]) == 2


def test_a_file_that_is_not_valid_utf8_does_not_stop_the_scan(etc: Path) -> None:
    (etc / "binary.conf").write_bytes(b"\xff\xfe\x00")
    (etc / "._cfg0000_binary.conf").write_bytes(b"\xff\xfe\x01")
    (found,) = find(etc)
    assert cfgfiles.diff(found), "a binary file still has to produce something readable"


# -- the helper's side ------------------------------------------------------


def test_taking_the_new_version_replaces_the_target(etc: Path, monkeypatch) -> None:
    """The whole round trip through the real helper, on a temporary /etc."""
    import io
    import json

    from gentstore.helper import gentstore_helper as helper

    monkeypatch.setattr(helper, "CONFIG_ROOT", etc)
    monkeypatch.setattr(helper, "CONFIG_PROTECT_SOURCES", ())
    monkeypatch.setattr(helper, "ENV_D", etc / "no-env-d")
    monkeypatch.setattr(helper, "DEFAULT_PROTECTED", (str(etc),))
    monkeypatch.setattr(helper, "CONFIG_ARCHIVE", etc / "archive")

    candidate = pending(etc, "fstab", "old\n", "new\n")
    stdout = io.StringIO()
    helper.main(
        io.StringIO(json.dumps({"op": "cfg_apply", "path": str(candidate),
                                "decision": "accept"})),
        stdout,
    )
    answer = json.loads(stdout.getvalue())

    assert answer["ok"], answer
    assert (etc / "fstab").read_text(encoding="utf-8") == "new\n"
    assert not candidate.exists(), "the candidate goes only once a decision is made"
    assert answer["archived"], "the version being replaced has to be kept"


def test_merging_writes_what_the_user_ended_up_with(etc: Path, monkeypatch) -> None:
    import io
    import json

    from gentstore.helper import gentstore_helper as helper

    monkeypatch.setattr(helper, "CONFIG_ROOT", etc)
    monkeypatch.setattr(helper, "CONFIG_PROTECT_SOURCES", ())
    monkeypatch.setattr(helper, "ENV_D", etc / "no-env-d")
    monkeypatch.setattr(helper, "DEFAULT_PROTECTED", (str(etc),))
    monkeypatch.setattr(helper, "CONFIG_ARCHIVE", etc / "archive")

    candidate = pending(etc, "fstab", "old\n", "theirs\n")
    stdout = io.StringIO()
    helper.main(
        io.StringIO(
            json.dumps(
                {
                    "op": "cfg_apply",
                    "path": str(candidate),
                    "decision": "merge",
                    "content": "mine and theirs\n",
                }
            )
        ),
        stdout,
    )
    answer = json.loads(stdout.getvalue())

    assert answer["ok"], answer
    assert (etc / "fstab").read_text(encoding="utf-8") == "mine and theirs\n"
    assert not candidate.exists()
