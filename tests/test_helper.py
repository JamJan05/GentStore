"""Tests for the privileged helper.

This is the only code in Gentstore that runs as root and writes outside the
user's home directory, so the tests are mostly about the things it must
*refuse*. The request arrives on standard input from a program the user is
running; the helper is root; those two facts together mean nothing in the
request may be believed without checking.

``CONFIG_ROOT`` is replaced with a temporary directory here. It is a module
constant rather than an argument or an environment variable precisely so that
only an in-process import can do that — the installed program cannot be talked
into writing somewhere else.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest

from gentstore.helper import gentstore_helper as helper


@pytest.fixture
def portage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "etc" / "portage"
    (root / "repos.conf").mkdir(parents=True)
    monkeypatch.setattr(helper, "CONFIG_ROOT", root)
    monkeypatch.setattr(helper, "BACKUP_PARENT", tmp_path / "etc")
    # cfg_apply reaches outside CONFIG_ROOT, into whatever Portage protects.
    # That list comes from root-owned files; here it comes from the sandbox.
    monkeypatch.setattr(helper, "CONFIG_PROTECT_SOURCES", ())
    monkeypatch.setattr(helper, "ENV_D", tmp_path / "no-env-d")
    monkeypatch.setattr(helper, "DEFAULT_PROTECTED", (str(tmp_path / "etc"),))
    return root


def call(op: str, **fields) -> dict:
    """Run one request the way the installed program would."""
    stdin = io.StringIO(json.dumps({"op": op, **fields}))
    stdout = io.StringIO()
    helper.main(stdin, stdout)
    return json.loads(stdout.getvalue())


# -- refusals ---------------------------------------------------------------


def test_a_path_outside_the_configuration_root_is_refused(portage: Path, tmp_path: Path) -> None:
    victim = tmp_path / "passwd"
    victim.write_text("root:x:0:0\n", encoding="utf-8")
    answer = call("append_line", path=str(victim), line="attacker:x:0:0")

    assert answer["ok"] is False
    assert answer["code"] == "outside_root"
    assert victim.read_text(encoding="utf-8") == "root:x:0:0\n"


def test_traversal_out_of_the_root_is_refused(portage: Path) -> None:
    answer = call("append_line", path=str(portage / ".." / ".." / "shadow"), line="x")
    assert answer["code"] == "outside_root"


def test_a_relative_path_is_refused(portage: Path) -> None:
    assert call("append_line", path="package.use/mpv", line="x")["code"] == "relative_path"


def test_a_symlink_pointing_out_of_the_root_is_refused(portage: Path, tmp_path: Path) -> None:
    victim = tmp_path / "outside.conf"
    victim.write_text("original\n", encoding="utf-8")
    (portage / "escape").symlink_to(victim)

    answer = call("append_line", path=str(portage / "escape"), line="added")

    assert answer["ok"] is False
    assert answer["code"] == "outside_root"
    assert victim.read_text(encoding="utf-8") == "original\n"


def test_a_symlink_inside_the_root_is_still_refused(portage: Path) -> None:
    """Not an escape, but writing through a link is never what was meant."""
    (portage / "real").write_text("one\n", encoding="utf-8")
    (portage / "link").symlink_to(portage / "real")

    answer = call("append_line", path=str(portage / "link"), line="two")

    assert answer["code"] == "symlink"
    assert (portage / "real").read_text(encoding="utf-8") == "one\n"


def test_a_directory_is_not_a_file(portage: Path) -> None:
    assert call("append_line", path=str(portage / "repos.conf"), line="x")["code"] == "not_a_file"


def test_an_unknown_operation_is_refused(portage: Path) -> None:
    assert call("chmod", path=str(portage / "x"))["code"] == "unknown_op"


def test_malformed_json_is_refused() -> None:
    stdout = io.StringIO()
    helper.main(io.StringIO("{not json"), stdout)
    assert json.loads(stdout.getvalue())["code"] == "bad_json"


# -- append_line ------------------------------------------------------------


def test_append_line_creates_the_file(portage: Path) -> None:
    target = portage / "package.use" / "mpv"
    target.parent.mkdir()
    answer = call("append_line", path=str(target), line="media-video/mpv vulkan")

    assert answer["ok"] and answer["changed"]
    assert target.read_text(encoding="utf-8") == "media-video/mpv vulkan\n"


def test_append_line_keeps_what_was_already_there(portage: Path) -> None:
    target = portage / "package.use"
    target.write_text("# my own comment\nmedia-video/mpv X\n", encoding="utf-8")
    call("append_line", path=str(target), line="www-client/firefox pgo")

    assert target.read_text(encoding="utf-8") == (
        "# my own comment\nmedia-video/mpv X\nwww-client/firefox pgo\n"
    )


def test_append_line_does_not_duplicate_an_identical_line(portage: Path) -> None:
    target = portage / "package.use"
    target.write_text("media-video/mpv vulkan\n", encoding="utf-8")
    answer = call("append_line", path=str(target), line="media-video/mpv vulkan")

    assert answer["ok"] and answer["changed"] is False
    assert target.read_text(encoding="utf-8").count("vulkan") == 1


def test_append_line_fixes_a_missing_final_newline(portage: Path) -> None:
    target = portage / "package.use"
    target.write_text("first line without a newline", encoding="utf-8")
    call("append_line", path=str(target), line="second")
    assert target.read_text(encoding="utf-8") == "first line without a newline\nsecond\n"


# -- replace_line -----------------------------------------------------------


def test_replace_line_changes_one_line_and_nothing_else(portage: Path) -> None:
    target = portage / "make.conf"
    target.write_text(
        '# tuned for this box\nMAKEOPTS="-j4"\n\n# keep\nFEATURES="ccache"\n', encoding="utf-8"
    )
    answer = call("replace_line", path=str(target), match=r"^MAKEOPTS=", line='MAKEOPTS="-j28"')

    assert answer["ok"] and answer["changed"]
    assert answer["previous"] == 'MAKEOPTS="-j4"'
    assert target.read_text(encoding="utf-8") == (
        '# tuned for this box\nMAKEOPTS="-j28"\n\n# keep\nFEATURES="ccache"\n'
    )


def test_replace_line_refuses_when_several_lines_match(portage: Path) -> None:
    target = portage / "make.conf"
    original = 'MAKEOPTS="-j4"\nMAKEOPTS="-j8"\n'
    target.write_text(original, encoding="utf-8")

    answer = call("replace_line", path=str(target), match=r"^MAKEOPTS=", line='MAKEOPTS="-j1"')

    assert answer["code"] == "ambiguous"
    assert target.read_text(encoding="utf-8") == original


def test_replace_line_refuses_a_smuggled_second_line(portage: Path) -> None:
    """One line in, one line out.

    The response says which line was replaced and what it now reads, and the
    interface shows that to the user as an account of what happened. A request
    that turned one line into three would make that account false.
    """
    target = portage / "make.conf"
    target.write_text('MAKEOPTS="-j4"\n', encoding="utf-8")

    answer = call(
        "replace_line",
        path=str(target),
        match="^MAKEOPTS=",
        line='MAKEOPTS="-j8"\nFEATURES="-sandbox"',
    )

    assert answer["code"] == "multiline"
    assert target.read_text(encoding="utf-8") == 'MAKEOPTS="-j4"\n'


def test_replace_line_refuses_when_nothing_matches(portage: Path) -> None:
    target = portage / "make.conf"
    target.write_text('USE="X"\n', encoding="utf-8")
    assert call("replace_line", path=str(target), match="^NOPE=", line="x")["code"] == "no_match"


# -- remove_line ------------------------------------------------------------


def test_remove_line_takes_out_exactly_that_line(portage: Path) -> None:
    target = portage / "package.mask"
    target.write_text("a\nb\nc\n", encoding="utf-8")
    answer = call("remove_line", path=str(target), line="b")

    assert answer["changed"]
    assert target.read_text(encoding="utf-8") == "a\nc\n"


def test_remove_line_says_so_when_there_is_nothing_to_remove(portage: Path) -> None:
    target = portage / "package.mask"
    target.write_text("a\n", encoding="utf-8")
    assert call("remove_line", path=str(target), line="b")["changed"] is False


# -- whole-file operations --------------------------------------------------


def test_write_file_is_limited_to_repos_conf(portage: Path) -> None:
    answer = call("write_file", path=str(portage / "make.conf"), content="x", expect=None)
    assert answer["code"] == "not_owned"


def test_write_file_creates_a_repository_definition(portage: Path) -> None:
    target = portage / "repos.conf" / "guru.conf"
    answer = call("write_file", path=str(target), content="[guru]\nlocation = /x\n", expect=None)

    assert answer["ok"] and answer["changed"]
    assert target.read_text(encoding="utf-8") == "[guru]\nlocation = /x\n"


def test_write_file_refuses_to_clobber_an_unexpected_file(portage: Path) -> None:
    target = portage / "repos.conf" / "guru.conf"
    target.write_text("edited by hand\n", encoding="utf-8")

    answer = call("write_file", path=str(target), content="ours\n", expect="what we wrote\n")

    assert answer["code"] == "changed_underfoot"
    assert target.read_text(encoding="utf-8") == "edited by hand\n"


def test_write_file_needs_an_expectation(portage: Path) -> None:
    target = portage / "repos.conf" / "guru.conf"
    assert call("write_file", path=str(target), content="x")["code"] == "bad_request"


def test_delete_file_removes_what_we_put_there(portage: Path) -> None:
    target = portage / "repos.conf" / "guru.conf"
    target.write_text("ours\n", encoding="utf-8")
    assert call("delete_file", path=str(target), expect="ours\n")["ok"]
    assert not target.exists()


# -- atomicity and permissions ---------------------------------------------


def test_the_original_survives_a_failed_write(portage: Path, monkeypatch) -> None:
    target = portage / "make.conf"
    target.write_text("original\n", encoding="utf-8")

    def explode(*_args, **_kwargs):
        raise OSError("the disk filled up")

    monkeypatch.setattr(helper.os, "replace", explode)
    with pytest.raises(OSError):
        helper.atomic_write(target, "replacement\n")

    assert target.read_text(encoding="utf-8") == "original\n"
    leftovers = [p for p in portage.iterdir() if p.name.startswith(".make.conf.")]
    assert not leftovers, "the temporary file should have been cleaned up"


def test_an_existing_file_keeps_its_permissions(portage: Path) -> None:
    target = portage / "make.conf"
    target.write_text("original\n", encoding="utf-8")
    os.chmod(target, 0o600)

    call("append_line", path=str(target), line="added")

    assert oct(target.stat().st_mode)[-3:] == "600"


# -- backups ----------------------------------------------------------------


def test_a_backup_copies_the_whole_tree(portage: Path) -> None:
    (portage / "make.conf").write_text('USE="X"\n', encoding="utf-8")
    answer = call("backup")

    assert answer["ok"]
    copy = Path(answer["backup"])
    assert (copy / "make.conf").read_text(encoding="utf-8") == 'USE="X"\n'


def test_old_backups_are_pruned(portage: Path, monkeypatch) -> None:
    monkeypatch.setattr(helper, "BACKUP_KEEP", 2)
    for hour in range(4):
        stamp = f"portage.bak-2026-01-01T{hour:02d}00"
        (helper.BACKUP_PARENT / stamp).mkdir()
    helper.make_backup()

    remaining = [p.name for p in helper.list_backups()]
    assert len(remaining) == helper.BACKUP_KEEP
    assert "portage.bak-2026-01-01T0000" not in remaining


def test_restoring_puts_the_old_configuration_back(portage: Path) -> None:
    (portage / "make.conf").write_text("before\n", encoding="utf-8")
    name = Path(call("backup")["backup"]).name

    (portage / "make.conf").write_text("after\n", encoding="utf-8")
    (portage / "package.use").write_text("added later\n", encoding="utf-8")

    assert call("restore", name=name)["ok"]
    assert (portage / "make.conf").read_text(encoding="utf-8") == "before\n"
    assert not (portage / "package.use").exists()


def test_restoring_keeps_a_copy_of_the_present_state(portage: Path) -> None:
    """Restoring is itself a change, so it too has to be undoable."""
    (portage / "make.conf").write_text("before\n", encoding="utf-8")
    name = Path(call("backup")["backup"]).name
    (portage / "make.conf").write_text("after\n", encoding="utf-8")

    call("restore", name=name)

    saved = [b for b in helper.list_backups() if b.name != name]
    assert saved, "the state that was replaced should have been kept"
    assert (saved[-1] / "make.conf").read_text(encoding="utf-8") == "after\n"


def test_a_made_up_backup_name_is_refused(portage: Path) -> None:
    assert call("restore", name="../../etc")["code"] == "bad_backup_name"


# -- configuration files ----------------------------------------------------


def test_cfg_apply_accepts_the_new_version(portage: Path) -> None:
    (portage / "make.conf").write_text("old\n", encoding="utf-8")
    candidate = portage / "._cfg0000_make.conf"
    candidate.write_text("new\n", encoding="utf-8")

    answer = call("cfg_apply", path=str(candidate), decision="accept")

    assert answer["ok"]
    assert (portage / "make.conf").read_text(encoding="utf-8") == "new\n"
    assert not candidate.exists()


def test_cfg_apply_rejects_by_deleting_only_the_candidate(portage: Path) -> None:
    (portage / "make.conf").write_text("old\n", encoding="utf-8")
    candidate = portage / "._cfg0000_make.conf"
    candidate.write_text("new\n", encoding="utf-8")

    call("cfg_apply", path=str(candidate), decision="reject")

    assert (portage / "make.conf").read_text(encoding="utf-8") == "old\n"
    assert not candidate.exists()


def test_cfg_apply_reaches_the_whole_protected_directory(portage: Path, tmp_path) -> None:
    """._cfg files land all over /etc, not only in /etc/portage."""
    target = tmp_path / "etc" / "fstab"
    target.write_text("old\n", encoding="utf-8")
    candidate = tmp_path / "etc" / "._cfg0000_fstab"
    candidate.write_text("new\n", encoding="utf-8")

    answer = call("cfg_apply", path=str(candidate), decision="accept")

    assert answer["ok"], answer
    assert target.read_text(encoding="utf-8") == "new\n"


def test_cfg_apply_still_refuses_outside_the_protected_directories(
    portage: Path, tmp_path
) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    candidate = outside / "._cfg0000_passwd"
    candidate.write_text("root:x:0:0\n", encoding="utf-8")

    answer = call("cfg_apply", path=str(candidate), decision="accept")

    assert answer["code"] == "outside_root"
    assert candidate.exists()


def test_the_protected_list_is_read_from_root_owned_files_only(
    portage: Path, tmp_path, monkeypatch
) -> None:
    """A request cannot widen where the helper will write."""
    conf = tmp_path / "make.conf"
    conf.write_text('CONFIG_PROTECT="/etc /usr/share/config"\n', encoding="utf-8")
    monkeypatch.setattr(helper, "CONFIG_PROTECT_SOURCES", (conf,))
    monkeypatch.setattr(helper, "DEFAULT_PROTECTED", ())

    roots = {str(path) for path in helper.protected_roots()}
    assert "/etc" in roots
    assert not any("elsewhere" in path for path in roots)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('CONFIG_PROTECT="/etc /opt/x"', ["/etc", "/opt/x"]),
        ("CONFIG_PROTECT=/usr/share/config", ["/usr/share/config"]),
        ("CONFIG_PROTECT='/etc'", ["/etc"]),
        ("  CONFIG_PROTECT=\"/etc\"  ", ["/etc"]),
        ("CONFIG_PROTECT_MASK=\"/etc/env.d\"", []),
        ('export CONFIG_PROTECT="/etc"', []),
        ('CONFIG_PROTECT="$OTHER /etc"', ["/etc"]),
    ],
)
def test_only_a_plain_assignment_counts(text: str, expected: list[str]) -> None:
    """Not a shell parser: anything clever is a way to widen the reach."""
    assert helper._config_protect_values(text) == expected


def test_cfg_apply_honours_an_expectation_when_it_is_given(portage: Path, tmp_path) -> None:
    """The same guarantee write_file has, for the one operation that reaches /etc.

    cfg_apply resolves files wherever CONFIG_PROTECT points, and a merge writes
    the text the user ended up with. If the target moved on between the diff
    they read and the button they pressed, their version wins.
    """
    target = tmp_path / "etc" / "sudoers"
    target.write_text("# original\n", encoding="utf-8")
    candidate = tmp_path / "etc" / "._cfg0000_sudoers"
    candidate.write_text("# from the package\n", encoding="utf-8")

    answer = call(
        "cfg_apply",
        path=str(candidate),
        decision="merge",
        content="attacker ALL=(ALL) NOPASSWD: ALL\n",
        expect="# something else entirely\n",
    )

    assert answer["code"] == "changed_underfoot"
    assert target.read_text(encoding="utf-8") == "# original\n"
    assert candidate.exists(), "a refused decision leaves the decision to make"

    answer = call(
        "cfg_apply",
        path=str(candidate),
        decision="merge",
        content="# merged by hand\n",
        expect="# original\n",
    )
    assert answer["ok"] is True
    assert target.read_text(encoding="utf-8") == "# merged by hand\n"


def test_cfg_apply_without_an_expectation_still_works(portage: Path, tmp_path) -> None:
    """Optional, not required: an older interface does not send one yet."""
    target = tmp_path / "etc" / "conf.d"
    target.write_text("old\n", encoding="utf-8")
    candidate = tmp_path / "etc" / "._cfg0000_conf.d"
    candidate.write_text("new\n", encoding="utf-8")

    assert call("cfg_apply", path=str(candidate), decision="accept")["ok"] is True
    assert target.read_text(encoding="utf-8") == "new\n"


def test_cfg_apply_only_touches_cfg_files(portage: Path) -> None:
    target = portage / "make.conf"
    target.write_text("x\n", encoding="utf-8")
    assert call("cfg_apply", path=str(target), decision="reject")["code"] == "not_a_cfg_file"


# -- the backup that comes with a change ------------------------------------


def test_ensure_backup_copies_before_changing_anything(portage: Path) -> None:
    target = portage / "package.use"
    target.write_text("before\n", encoding="utf-8")

    answer = call("append_line", path=str(target), line="after", ensure_backup=True)

    assert answer["ok"] and answer["changed"]
    copy = Path(answer["backup"])
    assert (copy / "package.use").read_text(encoding="utf-8") == "before\n"
    assert target.read_text(encoding="utf-8") == "before\nafter\n"


def test_the_answer_says_who_did_it(portage: Path) -> None:
    answer = call("backup")
    assert answer["identity"]["euid"] == os.geteuid()
