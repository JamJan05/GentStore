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


#: Files that live under /etc/portage on a real system and that Gentstore has
#: no business writing a line to. The first three are the ones that matter:
#: bashrc is sourced by every merge, package.env points at env/ files that set
#: any variable a build sees, and postsync.d holds programs run after a sync —
#: a line appended to any of them is code running as root later on.
FORBIDDEN = [
    "bashrc",
    "package.env",
    "env/hardened.conf",
    "postsync.d/whatever",
    "sets/mine",
    "color.map",
    "make.profile",
    "profile/package.use.mask",
    "repos.conf/gentoo.conf",
    "package.use.bak",
]


@pytest.mark.parametrize("name", FORBIDDEN)
@pytest.mark.parametrize("op", ["append_line", "replace_line", "remove_line"])
def test_line_edits_are_refused_outside_the_files_gentstore_writes(
    portage: Path, op: str, name: str
) -> None:
    """Being inside /etc/portage is not enough; the file has to be one of ours.

    ``/etc/portage`` is not a directory of inert configuration. Several files in
    it are executed, directly or otherwise, and the helper is root — so the
    question it answers is not "is this path inside the root" but "is this one
    of the files the interface writes".
    """
    target = portage / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("original\n", encoding="utf-8")

    answer = call(op, path=str(target), line="original", match="^original")

    assert answer["ok"] is False
    assert answer["code"] == "not_editable", answer
    assert target.read_text(encoding="utf-8") == "original\n"


@pytest.mark.parametrize(
    ("name", "line"),
    [
        ("package.use", "media-video/mpv vulkan"),
        ("package.use/mpv", "media-video/mpv vulkan"),
        ("package.accept_keywords/mpv", "=media-video/mpv-0.41.0 ~amd64"),
        ("package.license/mpv", "=media-video/mpv-0.41.0 NVIDIA-CUDA"),
        ("package.unmask/mpv", "=media-video/mpv-0.41.0"),
        ("package.mask/guru", "*/*::guru"),
        # make.conf takes a line of its own shape — see _check_make_conf_line.
        ("make.conf", 'MAKEOPTS="-j4 -l4.5"'),
    ],
)
def test_the_files_gentstore_writes_are_still_writable(
    portage: Path, name: str, line: str
) -> None:
    """The other half of the whitelist: it has to let the interface work."""
    target = portage / name
    target.parent.mkdir(parents=True, exist_ok=True)

    answer = call("append_line", path=str(target), line=line)

    assert answer["ok"] and answer["changed"], answer


def test_a_package_use_file_may_not_be_a_whole_tree(portage: Path) -> None:
    """Portage would read a deeper tree; nothing here ever builds a path into one."""
    target = portage / "package.use" / "sub" / "deeper"
    target.parent.mkdir(parents=True)

    answer = call("append_line", path=str(target), line="x/y flag")

    assert answer["code"] == "not_editable"
    assert not target.exists()


def test_a_symlink_out_of_the_root_is_still_named_a_symlink(
    portage: Path, tmp_path: Path
) -> None:
    """The whitelist runs after the path checks, so refusals keep their reason.

    A file inside a ``package.use`` directory that is a link to somewhere else
    is refused for being a link. Reporting it as "not one of the files we write"
    would be true and would hide what is actually going on.
    """
    victim = tmp_path / "outside.conf"
    victim.write_text("original\n", encoding="utf-8")
    (portage / "package.use").mkdir()
    (portage / "package.use" / "mpv").symlink_to(victim)

    answer = call("append_line", path=str(portage / "package.use" / "mpv"), line="added")

    assert answer["code"] == "outside_root"
    assert victim.read_text(encoding="utf-8") == "original\n"


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
    answer = call(
        "replace_line",
        path=str(target),
        match_kind="assignment",
        match_literal="MAKEOPTS",
        line='MAKEOPTS="-j28"',
    )

    assert answer["ok"] and answer["changed"]
    assert answer["previous"] == 'MAKEOPTS="-j4"'
    assert target.read_text(encoding="utf-8") == (
        '# tuned for this box\nMAKEOPTS="-j28"\n\n# keep\nFEATURES="ccache"\n'
    )


def test_replace_line_refuses_when_several_lines_match(portage: Path) -> None:
    target = portage / "make.conf"
    original = 'MAKEOPTS="-j4"\nMAKEOPTS="-j8"\n'
    target.write_text(original, encoding="utf-8")

    answer = call(
        "replace_line",
        path=str(target),
        match_kind="assignment",
        match_literal="MAKEOPTS",
        line='MAKEOPTS="-j1"',
    )

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
        match_kind="assignment",
        match_literal="MAKEOPTS",
        line='MAKEOPTS="-j8"\nUSE="X wayland"',
    )

    assert answer["code"] == "multiline"
    assert target.read_text(encoding="utf-8") == 'MAKEOPTS="-j4"\n'


def test_replace_line_refuses_when_nothing_matches(portage: Path) -> None:
    target = portage / "make.conf"
    target.write_text('USE="X"\n', encoding="utf-8")
    # A line make.conf could hold, so that "nothing matches" is what this test
    # gets to be about rather than the shape of the replacement.
    answer = call(
        "replace_line",
        path=str(target),
        match_kind="assignment",
        match_literal="NOPE",
        line='USE="X wayland"',
    )
    assert answer["code"] == "no_match"


# -- what a line in make.conf may say ---------------------------------------

#: Assignments that are not Gentstore's to make. The first three move the whole
#: operation or run a script of somebody's choosing during every merge; the rest
#: are the shell syntax that would make any variable do the same.
FORBIDDEN_MAKE_CONF = [
    'ROOT="/tmp/foo"',
    'PORTAGE_CONFIGROOT="/tmp/foo"',
    'SYSROOT="/tmp/foo"',
    'PORTAGE_BASHRC="/tmp/x"',
    'FETCHCOMMAND="/tmp/x \\${URI}"',
    'PORTAGE_TMPDIR="/tmp/x"',
    'FEATURES="$(command)"',
    'FEATURES="`command`"',
    'FEATURES="${OTHER}"',
    'USE="X" ; ROOT="/tmp/foo"',
    'USE="X" # and a comment',
    'USE="X"; reboot',
    "USE=\"X\" && reboot",
    'USE="X\\"',
    "USE='X' 'Y'",
    'USE="X',
    'USE=X"',
    "not an assignment at all",
    "# USE=\"X\"",
    "  export USE=\"X\"",
]


@pytest.mark.parametrize("line", FORBIDDEN_MAKE_CONF)
@pytest.mark.parametrize("op", ["append_line", "replace_line", "remove_line"])
def test_make_conf_takes_only_the_assignments_gentstore_makes(
    portage: Path, op: str, line: str
) -> None:
    """The path check says which file; this says which line.

    ``make.conf`` is the one file on the list whose contents decide what Portage
    *does* rather than which packages it installs, so being allowed to write the
    file is not the same as being allowed to write anything in it. The interface
    already refuses to type these — that is not a reason for this program to
    accept them, because the request arrives on stdin and what is on the other
    end of stdin is not this program's business to assume.
    """
    target = portage / "make.conf"
    target.write_text('USE="X"\n', encoding="utf-8")

    answer = call(
        op, path=str(target), line=line, match_kind="assignment", match_literal="USE"
    )

    assert answer["ok"] is False, answer
    assert answer["code"] == "make_conf_line", answer
    assert target.read_text(encoding="utf-8") == 'USE="X"\n'


def test_a_line_break_in_a_make_conf_value_is_still_a_line_break(portage: Path) -> None:
    """Refused a step earlier, and worth saying which step.

    ``append_line`` and ``replace_line`` take one line by definition, so this
    never reaches the make.conf check. The reason it is here is that the two
    checks together are what covers it, and a later rearrangement could drop the
    first one without anything else noticing.
    """
    target = portage / "make.conf"
    target.write_text('USE="X"\n', encoding="utf-8")

    answer = call("append_line", path=str(target), line='USE="X"\nROOT="/tmp/foo"')

    assert answer["code"] == "multiline"
    assert target.read_text(encoding="utf-8") == 'USE="X"\n'


@pytest.mark.parametrize("op", ["append_line", "replace_line", "remove_line"])
def test_a_null_byte_is_refused_a_step_earlier_and_for_every_file(
    portage: Path, op: str
) -> None:
    """It used to be a make.conf rule, which left the question unanswered for
    every other file this program writes.

    "The file already contains that line" is not something anybody can decide
    about a file with a NUL in it, and none of the four operations has a reason
    to put one there. Refused in the step that takes the line apart, so it is
    refused once rather than in four places.
    """
    target = portage / "package.use"
    target.write_text("media-video/mpv vulkan\n", encoding="utf-8")

    answer = call(
        op,
        path=str(target),
        line="app-x/y flag\x00hidden",
        match_kind="entry",
        match_literal="app-x/y",
    )

    assert answer["code"] == "nul_byte", answer
    assert target.read_bytes() == b"media-video/mpv vulkan\n"


def test_replace_line_checks_the_new_line_and_not_only_the_pattern(
    portage: Path,
) -> None:
    """Two claims in one request, checked separately.

    "Find the line matching ``USE=``" is a claim about the file. "Put this in
    its place" is a claim about what is going in. A request may make the first
    one honestly and the second one not, and the pattern says nothing at all
    about the line that replaces what it found.
    """
    target = portage / "make.conf"
    target.write_text('USE="X"\nMAKEOPTS="-j4"\n', encoding="utf-8")

    answer = call(
        "replace_line", path=str(target), match="^USE=", line='ROOT="/tmp/foo"'
    )

    assert answer["code"] == "make_conf_line"
    assert target.read_text(encoding="utf-8") == 'USE="X"\nMAKEOPTS="-j4"\n'


@pytest.mark.parametrize(
    "line",
    [
        'MAKEOPTS="-j4 -l4.5"',
        "MAKEOPTS=-j4",
        'EMERGE_DEFAULT_OPTS="--quiet-build=y --with-bdeps=y"',
        'USE="-bindist X gtk python_targets_python3_12"',
        'ACCEPT_KEYWORDS="~amd64"',
        'ACCEPT_LICENSE="-* @FREE @BINARY-REDISTRIBUTABLE"',
        'VIDEO_CARDS="amdgpu radeonsi"',
        'CPU_FLAGS_X86="aes avx avx2 sse4_2"',
        'FEATURES="parallel-fetch ccache candy"',
        'L10N="pl en pt-BR"',
        'USE=""',
        '\tMAKEOPTS="-j4"',
    ],
)
def test_the_assignments_gentstore_does_make_still_go_through(
    portage: Path, line: str
) -> None:
    """A policy that refuses the real thing is not a policy, it is a bug."""
    target = portage / "make.conf"
    target.write_text("# somebody's own notes\n", encoding="utf-8")

    answer = call("append_line", path=str(target), line=line)

    assert answer["ok"] and answer["changed"], answer


def test_a_file_called_make_conf_somewhere_else_is_not_make_conf(portage: Path) -> None:
    """``package.use/make.conf`` is an ordinary package.use entry.

    The make.conf policy is keyed off which of the allowed names the path
    started with, not off the file's own name, because those are two different
    questions and only one of them is about /etc/portage/make.conf.
    """
    target = portage / "package.use" / "make.conf"
    target.parent.mkdir()

    answer = call("append_line", path=str(target), line="media-video/mpv vulkan")

    assert answer["ok"] and answer["changed"], answer


# -- the one directory the helper creates -----------------------------------


def test_a_missing_package_directory_is_created(portage: Path) -> None:
    """Gentoo recommends the directory form, and the preview promises it.

    ``package.unmask`` does not exist on a system that has never unmasked
    anything, and until this existed the write was refused with a message about
    a directory the user had just been told would appear.
    """
    target = portage / "package.unmask" / "hyprland"
    answer = call("append_line", path=str(target), line="=gui-wm/hyprland-0.56.2")

    assert answer["ok"] and answer["changed"], answer
    assert answer["created_directory"] == str(portage / "package.unmask")
    assert target.read_text(encoding="utf-8") == "=gui-wm/hyprland-0.56.2\n"
    assert oct(os.stat(portage / "package.unmask").st_mode)[-3:] == "755"


def test_creating_the_directory_is_not_reported_when_it_was_there(portage: Path) -> None:
    (portage / "package.use").mkdir()
    answer = call("append_line", path=str(portage / "package.use" / "a"), line="cat/a flag")
    assert answer["ok"] and "created_directory" not in answer


def test_make_conf_never_becomes_a_directory(portage: Path) -> None:
    """The exception that is the reason for a second list.

    ``make.conf`` is on the list of files the helper may write a line to, and it
    is a *file*. Creating a directory of that name on a system that has not got
    one yet would leave Portage reading an empty directory where its main
    configuration file belongs.
    """
    answer = call("append_line", path=str(portage / "make.conf" / "x"), line='USE="X"')

    assert answer["ok"] is False and answer["code"] == "no_directory"
    assert not (portage / "make.conf").exists()


@pytest.mark.parametrize(
    ("relative", "reason"),
    [
        ("package.use/deeper/still", "deeper than anything Gentstore writes"),
        ("bashrc/anything", "a name that is not on the list"),
        ("package.env/a", "a name that is not on the list"),
    ],
)
def test_no_other_directory_is_ever_created(
    portage: Path, relative: str, reason: str
) -> None:
    answer = call("append_line", path=str(portage / relative), line="x")

    assert answer["ok"] is False, reason
    assert not (portage / relative.partition("/")[0]).exists(), reason


def test_a_symlink_where_the_directory_would_go_is_left_alone(
    portage: Path, tmp_path: Path
) -> None:
    """Something is already there, and replacing it is not this function's job.

    The link is left for ``check_path`` to refuse in the ordinary way, which is
    what keeps "create the one missing directory" from turning into "decide what
    to do about whatever is in its place".
    """
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (portage / "package.unmask").symlink_to(elsewhere)

    answer = call("append_line", path=str(portage / "package.unmask" / "a"), line="=cat/a-1")

    assert answer["ok"] is False
    assert list(elsewhere.iterdir()) == [], "nothing may be written through the link"
    assert (portage / "package.unmask").is_symlink(), "and the link is still a link"


def test_a_traversal_creates_nothing(portage: Path, tmp_path: Path) -> None:
    answer = call("append_line", path=str(portage / ".." / ".." / "evil" / "x"), line="x")

    assert answer["ok"] is False and answer["code"] == "outside_root"
    assert not (tmp_path / "evil").exists()


def test_a_grouped_write_creates_the_directories_it_needs(portage: Path) -> None:
    answer = call(
        "append_lines",
        entries=[
            {"path": str(portage / "package.accept_keywords" / "hyprland"),
             "line": "=gui-wm/hyprland-0.56.2 ~amd64"},
            {"path": str(portage / "package.unmask" / "hyprland"),
             "line": "=gui-wm/hyprland-0.56.2"},
        ],
    )

    assert answer["ok"] and answer["written"] == 2, answer
    assert sorted(p.name for p in portage.iterdir() if p.is_dir()) == [
        "package.accept_keywords",
        "package.unmask",
        "repos.conf",
    ]


def test_a_refused_batch_leaves_at_most_an_empty_directory(
    portage: Path, tmp_path: Path
) -> None:
    """The all-or-nothing guarantee is about lines, and it still holds.

    Validating an entry is what calls ``check_path``, and ``check_path`` cannot
    approve a path whose parent is missing — so the directory is made during the
    checking pass and a refused batch can leave one behind. An empty
    ``package.unmask`` means exactly what no ``package.unmask`` means, which is
    nothing at all; no *line* is written, and that is the promise.
    """
    answer = call(
        "append_lines",
        entries=[
            {"path": str(portage / "package.unmask" / "a"), "line": "=cat/a-1"},
            {"path": str(tmp_path / "shadow"), "line": "attacker:x:0:0"},
        ],
    )

    assert answer["ok"] is False and answer["code"] == "outside_root"
    assert list((portage / "package.unmask").iterdir()) == []
    assert not (tmp_path / "shadow").exists()


# -- grouped writes ---------------------------------------------------------


@pytest.fixture
def batchable(portage: Path) -> Path:
    """A configuration root with the directories a real system has.

    Every ``package.*`` name, including the two a grouped write must refuse, so
    that a refusal is about the name and not about a missing directory.
    """
    for name in (
        "package.accept_keywords",
        "package.license",
        "package.use",
        "package.unmask",
        "package.mask",
        "package.env",
    ):
        (portage / name).mkdir()
    return portage


def entries(root: Path, *pairs: tuple[str, str]) -> list[dict]:
    return [{"path": str(root / name), "line": line} for name, line in pairs]


def test_a_grouped_write_reaches_all_four_files(batchable: Path) -> None:
    """One request, four files, one backup — the point of the operation."""
    answer = call(
        "append_lines",
        ensure_backup=True,
        entries=entries(
            batchable,
            ("package.accept_keywords/hyprland", "=gui-wm/hyprland-0.56.2 ~amd64"),
            ("package.accept_keywords/hyprland", "=gui-libs/aquamarine-0.14.0 ~amd64"),
            ("package.unmask/hyprland", "=gui-wm/hyprland-0.56.2"),
            ("package.use/squashfs-tools", ">=sys-fs/squashfs-tools-4.7.5 zstd"),
            ("package.license/lmstudio", "sci-ml/lmstudio-bin LM-Studio-EULA"),
        ),
    )

    assert answer["ok"] and answer["written"] == 5, answer
    assert answer["backup"], "a grouped write deserves a backup like any other"
    # Two lines into one file: the second read has to see the first write.
    assert (batchable / "package.accept_keywords" / "hyprland").read_text(
        encoding="utf-8"
    ) == "=gui-wm/hyprland-0.56.2 ~amd64\n=gui-libs/aquamarine-0.14.0 ~amd64\n"


def test_a_line_that_is_already_there_is_left_alone(batchable: Path) -> None:
    """Running the same analysis twice is ordinary, not an error."""
    pair = ("package.accept_keywords/mpv", "=media-video/mpv-0.41.0 ~amd64")
    call("append_lines", entries=entries(batchable, pair))
    answer = call("append_lines", entries=entries(batchable, pair, pair))

    assert answer["ok"] and answer["changed"] is False
    assert answer["written"] == 0 and answer["skipped"] == 2
    assert (batchable / "package.accept_keywords" / "mpv").read_text(
        encoding="utf-8"
    ) == "=media-video/mpv-0.41.0 ~amd64\n"


def test_one_bad_entry_leaves_every_file_untouched(batchable: Path, tmp_path: Path) -> None:
    """All of it or none of it.

    The third of five is wrong, and the two before it are perfectly good. A
    write that got that far and stopped would leave the configuration in a state
    the user never chose and could not name — which is worse than the refusal,
    because they would have to work out what happened before they could try
    again.
    """
    request = entries(
        batchable,
        ("package.accept_keywords/a", "=cat/a-1 ~amd64"),
        ("package.use/a", "cat/a flag"),
    )
    request.append({"path": str(tmp_path / "shadow"), "line": "attacker:x:0:0"})
    request += entries(
        batchable,
        ("package.license/a", "cat/a SOME-EULA"),
        ("package.unmask/a", "=cat/a-1"),
    )

    answer = call("append_lines", entries=request)

    assert answer["ok"] is False and answer["code"] == "outside_root"
    assert "entry 3" in answer["error"], answer["error"]
    written = [item for name in batchable.iterdir() if name.is_dir() for item in name.iterdir()]
    assert written == [], "nothing at all should have been written"


@pytest.mark.parametrize(
    ("name", "line", "code"),
    [
        # The two names a grouped write refuses although the helper writes them
        # one line at a time: make.conf decides what Portage does, and
        # package.mask adds a restriction rather than lifting one.
        ("make.conf", 'USE="X"', "not_batchable"),
        ("package.mask/a", "=cat/a-1", "not_batchable"),
        # And the ones nothing may write a line to at all.
        ("package.env/a", "cat/a custom", "not_editable"),
        ("bashrc", "id", "not_editable"),
    ],
)
def test_a_grouped_write_refuses_the_files_it_is_not_for(
    batchable: Path, name: str, line: str, code: str
) -> None:
    answer = call("append_lines", entries=entries(batchable, (name, line)))
    assert answer["ok"] is False and answer["code"] == code, answer


@pytest.mark.parametrize(
    ("description", "payload"),
    [
        ("no entries at all", {}),
        ("an empty list", {"entries": []}),
        ("not a list", {"entries": "package.use/a"}),
        ("an entry that is not an object", {"entries": ["a/b flag"]}),
    ],
)
def test_a_malformed_grouped_request_is_refused(
    batchable: Path, description: str, payload: dict
) -> None:
    answer = call("append_lines", **payload)
    assert answer["ok"] is False and answer["code"] == "bad_request", description


def test_an_entry_missing_a_field_is_refused(batchable: Path) -> None:
    for entry in ({"path": str(batchable / "package.use" / "a")}, {"line": "cat/a flag"}):
        answer = call("append_lines", entries=[entry])
        assert answer["ok"] is False and answer["code"] == "bad_request", answer


def test_a_second_line_cannot_ride_along_inside_the_first(batchable: Path) -> None:
    """The oldest trick against a line-based writer, and the plainest refusal."""
    answer = call(
        "append_lines",
        entries=entries(batchable, ("package.use/a", "cat/a flag\ncat/evil -*")),
    )
    assert answer["ok"] is False and answer["code"] == "multiline"


def test_an_empty_line_is_refused(batchable: Path) -> None:
    answer = call("append_lines", entries=entries(batchable, ("package.use/a", "   ")))
    assert answer["ok"] is False and answer["code"] == "bad_request"


def test_a_grouped_write_is_bounded(batchable: Path) -> None:
    """Every entry is a file read and rewritten while this process is root."""
    too_many = entries(
        batchable, *[("package.use/a", f"cat/a-{n} flag") for n in range(helper.BATCH_MAX + 1)]
    )
    assert call("append_lines", entries=too_many)["code"] == "too_many"


def test_the_helper_and_the_interface_agree_on_what_a_batch_may_touch() -> None:
    """The narrow list is duplicated for the same reason the wide one is.

    The helper imports nothing from the rest of Gentstore so that it can be read
    as one file. That costs a second copy of the list, and this is the rent —
    the same arrangement as
    :func:`test_the_helper_and_the_interface_agree_on_what_is_editable`.
    """
    from gentstore.core import confedit  # noqa: PLC0415 - the helper must not import it

    assert set(helper.BATCH_EDITABLE) == set(confedit.BATCHABLE)
    assert set(helper.BATCH_EDITABLE) <= set(helper.LINE_EDITABLE)


def test_a_grouped_write_deserves_a_backup_like_any_other_change() -> None:
    assert "append_lines" in helper.MUTATING


def test_the_helper_and_the_interface_agree_on_what_is_editable() -> None:
    """The copy in the helper is allowed to exist; it is not allowed to drift.

    The helper imports nothing from the rest of Gentstore, on purpose: it is
    meant to be readable as one file by somebody who does not trust it. That
    costs a duplicated list, and this is the rent.
    """
    from gentstore.core import makeconf  # noqa: PLC0415 - the helper must not import it

    assert set(helper.MAKE_CONF_VARIABLES) == set(makeconf.EDITABLE)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("MAKEOPTS", "-j4 -l4.5"),
        ("EMERGE_DEFAULT_OPTS", "--quiet-build=y --with-bdeps=y --keep-going"),
        ("USE", "-bindist X gtk"),
        ("ACCEPT_KEYWORDS", "~amd64"),
        ("ACCEPT_LICENSE", "-* @FREE"),
        ("VIDEO_CARDS", "amdgpu radeonsi"),
        ("CPU_FLAGS_X86", "aes avx avx2"),
        ("FEATURES", "parallel-fetch ccache -candy"),
        ("L10N", "pl en pt-BR"),
        ("USE", ""),
    ],
)
def test_what_the_interface_writes_is_what_the_helper_accepts(
    portage: Path, name: str, value: str
) -> None:
    """The seam itself, rather than the two lists either side of it.

    A stricter helper than the screen it serves is a refusal the user cannot
    act on: the line in front of them is the line being refused.
    """
    from gentstore.core import makeconf  # noqa: PLC0415

    line = makeconf.format_line(name, value)
    target = portage / "make.conf"
    target.write_text("# somebody's own notes\n", encoding="utf-8")

    answer = call("append_line", path=str(target), line=line)

    assert answer["ok"] and answer["changed"], (line, answer)


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


# -- the fields of the request itself ---------------------------------------


@pytest.mark.parametrize("keep", ["abc", {"a": 1}, [], True, 1.5])
def test_a_keep_that_is_not_a_whole_number_is_a_refusal_not_a_traceback(
    portage: Path, keep: object
) -> None:
    """The contract is one JSON answer, always — including for bad input.

    ``keep`` was the one field that reached ``int()`` unchecked, so a request
    carrying ``"abc"`` raised a ValueError that ``main`` does not catch: root
    printed a stack trace on stderr and nothing at all on stdout, and the
    interface was left with an exit status and no reason. ``True`` is in the
    list because ``isinstance(True, int)`` is the trap that would let it in.
    """
    answer = call("backup", keep=keep)
    assert answer["ok"] is False
    assert answer["code"] == "bad_request"


def test_a_bad_keep_refuses_before_the_change_it_was_attached_to(portage: Path) -> None:
    """``ensure_backup`` runs first, so the refusal has to happen before the write."""
    target = portage / "package.use"
    target.write_text("media-video/mpv vulkan\n", encoding="utf-8")

    answer = call(
        "append_line", path=str(target), line="x/y flag", ensure_backup=True, keep="zz"
    )
    assert answer["code"] == "bad_request"
    assert target.read_text(encoding="utf-8") == "media-video/mpv vulkan\n"


def test_a_regular_expression_from_the_request_is_no_longer_accepted(portage: Path) -> None:
    """The cap on pattern length was a bound rather than a cure, and not much
    of a bound: ``^(a+)+$`` is seven characters and runs for ever against a
    sixty-character line, which an earlier append_line can put in the file.

    Nothing in the standard library can give a regular expression a deadline,
    and this process is root, so the answer is not to compile one at all.
    """
    target = portage / "package.use"
    target.write_text("media-video/mpv vulkan\n", encoding="utf-8")

    answer = call("replace_line", path=str(target), line="x/y flag", match="^(a+)+$")

    assert answer["code"] == "bad_pattern"
    assert "match_kind" in answer["error"]
    assert target.read_text(encoding="utf-8") == "media-video/mpv vulkan\n"


def test_the_literal_is_still_bounded(portage: Path) -> None:
    target = portage / "package.use"
    target.write_text("media-video/mpv vulkan\n", encoding="utf-8")
    answer = call(
        "replace_line",
        path=str(target),
        line="x/y flag",
        match_kind="entry",
        match_literal="a" * (helper.PATTERN_MAX + 1),
    )
    assert answer["code"] == "bad_pattern"


@pytest.mark.parametrize(
    "literal",
    ["media-video/mpv", "^(a+)+$", ".*", "a" * 200, "[", "\\", "cat/pkg(", "$^"],
)
def test_every_literal_is_an_ordinary_string(portage: Path, literal: str) -> None:
    """re.escape makes every character of it ordinary, so there is nothing left
    to craft: whatever arrives is looked for verbatim or not found."""
    target = portage / "package.use"
    target.write_text(f"{literal} vulkan\nmedia-video/other x\n", encoding="utf-8")

    answer = call(
        "replace_line",
        path=str(target),
        line="a/b flag",
        match_kind="entry",
        match_literal=literal,
    )

    assert answer["ok"], answer
    assert answer["previous"] == f"{literal} vulkan"


def test_an_unknown_match_kind_is_refused(portage: Path) -> None:
    target = portage / "package.use"
    target.write_text("media-video/mpv vulkan\n", encoding="utf-8")
    answer = call(
        "replace_line",
        path=str(target),
        line="x/y flag",
        match_kind="whatever",
        match_literal="media-video/mpv",
    )
    assert answer["code"] == "bad_pattern"


def test_the_two_kinds_are_anchored(portage: Path) -> None:
    """A mention inside a comment, or inside another entry's value, is not the
    line being replaced."""
    target = portage / "make.conf"
    target.write_text('# was MAKEOPTS=-j8\nUSE="X"\n', encoding="utf-8")

    answer = call(
        "replace_line",
        path=str(target),
        line='MAKEOPTS="-j1"',
        match_kind="assignment",
        match_literal="MAKEOPTS",
    )

    assert answer["code"] == "no_match"
    assert target.read_text(encoding="utf-8") == '# was MAKEOPTS=-j8\nUSE="X"\n'


def test_the_interface_and_the_helper_agree_on_how_a_line_is_found(portage: Path) -> None:
    """The seam: what core/confedit.py and core/makeconf.py put in a plan has to
    be something this program knows how to build a pattern from."""
    from gentstore.core import makeconf  # noqa: PLC0415

    conf = makeconf.load(path=portage / "make.conf")
    plan = makeconf.plan_set(conf, "MAKEOPTS", "-j4")
    if plan.match_kind is not None:
        assert plan.match_kind in helper.MATCH_KINDS


# -- where cfg_apply may reach ----------------------------------------------


def test_config_protect_cannot_be_pointed_at_a_directory_others_can_write(
    portage: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The list of protected directories is only as trustworthy as its sources.

    Two of the three are root-owned files nothing else touches. The third is
    ``/etc/portage/make.conf``, which this same program appends lines to on
    request — so a caller can write a CONFIG_PROTECT of its own and then ask
    cfg_apply to follow it. Where it points is not the interesting part; whether
    somebody other than root could have planted the ``._cfg`` file waiting there
    is.

    ``geteuid`` is faked because the check is deliberately asleep when we are not
    root: unprivileged, every directory in this fixture belongs to whoever is
    running the suite, and refusing on that would refuse the person asking.
    """
    theirs = tmp_path / "theirs"
    theirs.mkdir()
    monkeypatch.setattr(helper, "DEFAULT_PROTECTED", (str(theirs),))
    monkeypatch.setattr(helper.os, "geteuid", lambda: 0)

    # stat() answers honestly: the directory belongs to the user running this,
    # and the faked euid says root is asking. That is exactly the shape of the
    # thing being refused.
    assert theirs.resolve() not in helper.protected_roots()


# -- what a whole-file write may contain ------------------------------------


def test_write_file_refuses_a_file_that_redefines_another_repository(portage: Path) -> None:
    """Portage reads every file in repos.conf and merges them, so a section
    repeated in a file read later replaces the earlier definition.

    The path check says "repos.conf, so yes"; it has nothing to say about a file
    called guru.conf that defines gentoo. That is not adding a repository, it is
    pointing every package on the system somewhere else, and it arrived on stdin.
    """
    target = portage / "repos.conf" / "zzz-guru.conf"
    answer = call(
        "write_file",
        path=str(target),
        content="[gentoo]\nsync-uri = https://attacker.example/tree.git\n",
        expect=None,
    )

    assert answer["ok"] is False
    assert answer["code"] == "bad_content"
    assert not target.exists()


def test_write_file_refuses_a_default_section(portage: Path) -> None:
    """[DEFAULT] applies to every other section, including ones in files this
    program never wrote."""
    target = portage / "repos.conf" / "guru.conf"
    answer = call(
        "write_file",
        path=str(target),
        content=(
            "[DEFAULT]\nsync-uri = https://attacker.example/\n"
            "\n[guru]\nlocation = /var/db/repos/guru\n"
        ),
        expect=None,
    )

    assert answer["code"] == "bad_content"
    assert not target.exists()


def test_write_file_refuses_a_file_naming_the_main_repository(portage: Path) -> None:
    target = portage / "repos.conf" / "gentoo.conf"
    answer = call(
        "write_file",
        path=str(target),
        content="[gentoo]\nsync-uri = https://attacker.example/tree.git\n",
        expect=None,
    )

    assert answer["code"] == "bad_content"
    assert not target.exists()


@pytest.mark.parametrize(
    "content",
    [
        "[guru]\nsync-hooks = /tmp/mine.sh\n",
        "[guru]\nsync-openpgp-key-path = /tmp/mine.gpg\n",
        "[guru]\npost-sync = /tmp/mine.sh\n",
    ],
)
def test_write_file_refuses_keys_gentstore_does_not_write(portage: Path, content: str) -> None:
    """A list of what this application writes, not a list of what looks
    dangerous — the same rule as LINE_EDITABLE, one level down."""
    target = portage / "repos.conf" / "guru.conf"
    answer = call("write_file", path=str(target), content=content, expect=None)
    assert answer["code"] == "bad_content"
    assert not target.exists()


def test_write_file_refuses_a_location_others_can_write(
    portage: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`location` names the directory Portage reads ebuilds from, and an ebuild
    is a shell script this machine runs as root while merging."""
    theirs = tmp_path / "theirs"
    theirs.mkdir()
    monkeypatch.setattr(helper.os, "geteuid", lambda: 0)

    target = portage / "repos.conf" / "guru.conf"
    answer = call(
        "write_file",
        path=str(target),
        content=f"[guru]\nlocation = {theirs}\nsync-type = git\n",
        expect=None,
    )

    assert answer["code"] == "bad_content"
    assert not target.exists()


def test_write_file_still_writes_the_definitions_gentstore_makes(portage: Path) -> None:
    """The refusals above must not have cost the operation its reason to exist."""
    binrepos = portage / "binrepos.conf"
    binrepos.mkdir()
    target = binrepos / "gentoo-binhost.conf"
    content = binrepos_section_text()

    answer = call("write_file", path=str(target), content=content, expect=None)

    assert answer["ok"] and answer["changed"], answer
    assert target.read_text(encoding="utf-8") == content


def binrepos_section_text() -> str:
    """What core/binrepos.py actually produces, so the two cannot drift apart."""
    from gentstore.core import binrepos

    return binrepos.section_text("gentoo-binhost", "https://distfiles.gentoo.org/releases", 1)


def test_a_whole_file_write_goes_no_deeper_than_gentstore_does(portage: Path) -> None:
    nested = portage / "repos.conf" / "nested"
    nested.mkdir()
    answer = call(
        "write_file", path=str(nested / "guru.conf"), content="[guru]\n", expect=None
    )
    assert answer["code"] == "not_owned"


# -- what a merge has to say about the file it is merging into --------------


def test_cfg_apply_merge_requires_an_expectation(portage: Path, tmp_path) -> None:
    """A merge writes text that arrived in the request. Nothing else in the
    operation ties that text to anything the user saw — so it has to say what it
    expects to find, and an accept, whose content is on disk, does not."""
    target = tmp_path / "etc" / "sudoers"
    target.write_text("root ALL=(ALL) ALL\n", encoding="utf-8")
    candidate = tmp_path / "etc" / "._cfg0000_sudoers"
    candidate.write_text("root ALL=(ALL) ALL\n", encoding="utf-8")

    answer = call(
        "cfg_apply",
        path=str(candidate),
        decision="merge",
        content="attacker ALL=(ALL) NOPASSWD: ALL\n",
    )

    assert answer["ok"] is False
    assert answer["code"] == "bad_request"
    assert target.read_text(encoding="utf-8") == "root ALL=(ALL) ALL\n"
    assert candidate.exists()


def test_cfg_apply_merge_refuses_when_the_target_moved_on(portage: Path, tmp_path) -> None:
    target = tmp_path / "etc" / "conf.d"
    target.write_text("edited by hand\n", encoding="utf-8")
    candidate = tmp_path / "etc" / "._cfg0000_conf.d"
    candidate.write_text("new\n", encoding="utf-8")

    answer = call(
        "cfg_apply",
        path=str(candidate),
        decision="merge",
        content="merged\n",
        expect="what the diff showed\n",
    )

    assert answer["code"] == "changed_underfoot"
    assert target.read_text(encoding="utf-8") == "edited by hand\n"


def test_cfg_apply_merge_goes_through_when_it_says_what_it_saw(portage: Path, tmp_path) -> None:
    target = tmp_path / "etc" / "conf.d"
    target.write_text("old\n", encoding="utf-8")
    candidate = tmp_path / "etc" / "._cfg0000_conf.d"
    candidate.write_text("new\n", encoding="utf-8")

    answer = call(
        "cfg_apply", path=str(candidate), decision="merge", content="merged\n", expect="old\n"
    )

    assert answer["ok"], answer
    assert target.read_text(encoding="utf-8") == "merged\n"
    assert not candidate.exists()


def test_cfg_apply_merge_into_a_file_that_is_not_there_yet(portage: Path, tmp_path) -> None:
    """`expect: null` means "this file should not exist yet" — the shape a new
    configuration file arrives in."""
    candidate = tmp_path / "etc" / "._cfg0000_brand-new"
    candidate.write_text("new\n", encoding="utf-8")

    answer = call(
        "cfg_apply", path=str(candidate), decision="merge", content="merged\n", expect=None
    )

    assert answer["ok"], answer
    assert (tmp_path / "etc" / "brand-new").read_text(encoding="utf-8") == "merged\n"


def test_cfg_apply_refuses_a_directory_others_can_write(
    portage: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rule in _only_root_can_write has to hold where the file really is.

    /etc passes that rule on every machine there has ever been, so asking only
    about the CONFIG_PROTECT entry answered nothing about a loose directory
    underneath it — and a loose directory is exactly where somebody who is not
    root could have put the ``._cfg`` file this operation trusts.
    """
    loose = tmp_path / "etc" / "loose"
    loose.mkdir()
    loose.chmod(0o777)
    (loose / "victim.conf").write_text("harmless\n", encoding="utf-8")
    (loose / "._cfg0000_victim.conf").write_text("planted\n", encoding="utf-8")
    # The check is deliberately asleep when we are not root; this test is about
    # what it says when we are.
    monkeypatch.setattr(helper.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        helper, "_only_root_can_write", lambda path: Path(path) != loose
    )

    answer = call(
        "cfg_apply", path=str(loose / "._cfg0000_victim.conf"), decision="accept"
    )

    assert answer["ok"] is False
    assert answer["code"] == "unsafe_directory"
    assert (loose / "victim.conf").read_text(encoding="utf-8") == "harmless\n"
    assert (loose / "._cfg0000_victim.conf").exists()


def test_cfg_apply_still_works_where_only_root_can_write(portage: Path, tmp_path) -> None:
    """The refusal above must not have cost the operation its reason to exist."""
    target = tmp_path / "etc" / "fstab"
    target.write_text("old\n", encoding="utf-8")
    candidate = tmp_path / "etc" / "._cfg0000_fstab"
    candidate.write_text("new\n", encoding="utf-8")

    assert call("cfg_apply", path=str(candidate), decision="accept")["ok"]
    assert target.read_text(encoding="utf-8") == "new\n"


# -- the two variables whose value is the question --------------------------


@pytest.mark.parametrize(
    "value",
    [
        "-sandbox",
        "-usersandbox -network-sandbox",
        "-userpriv",
        "parallel-fetch -sandbox",
        "-rsync-verify",
        "-webrsync-gpg",
        "-strict",
        "-collision-protect",
        "-preserve-libs",
    ],
)
def test_features_may_not_switch_a_protection_off(portage: Path, value: str) -> None:
    """The nine variables are on the list because they were taken to decide
    *which packages* get installed rather than *what Portage does*.

    FEATURES does not meet that test, and the character set cannot tell:
    ``-sandbox`` is ordinary letters and a hyphen. Written once, it takes the
    walls off every build the machine does afterwards — which is not a package
    being installed, and not what the dialog in front of this program says.
    """
    target = portage / "make.conf"
    target.write_text('USE="X"\n', encoding="utf-8")

    answer = call("append_line", path=str(target), line=f'FEATURES="{value}"')

    assert answer["code"] == "make_conf_line", answer
    assert target.read_text(encoding="utf-8") == 'USE="X"\n'


@pytest.mark.parametrize(
    "value", ["ccache", "-candy", "parallel-fetch ccache buildpkg", "sandbox", "test"]
)
def test_features_the_settings_screen_offers_still_go_through(
    portage: Path, value: str
) -> None:
    """Turning a protection *on* is always allowed, and a preference either way."""
    target = portage / "make.conf"
    target.write_text("# notes\n", encoding="utf-8")
    assert call("append_line", path=str(target), line=f'FEATURES="{value}"')["ok"]


@pytest.mark.parametrize(
    "value",
    [
        "-j1 -f/home/someone/theirs.mk",
        "-f/tmp/x.mk",
        "--eval=x",
        "-j4 --directory=/tmp",
        "-I/tmp",
    ],
)
def test_makeopts_takes_only_parallelism_options(portage: Path, value: str) -> None:
    """MAKEOPTS is a command line for make, which emake expands unquoted.

    ``-f`` in it names a makefile, so it replaces the one the ebuild shipped —
    and every character of that fits the allowed alphabet.
    """
    target = portage / "make.conf"
    target.write_text('USE="X"\n', encoding="utf-8")

    answer = call("append_line", path=str(target), line=f'MAKEOPTS="{value}"')

    assert answer["code"] == "make_conf_line", answer
    assert target.read_text(encoding="utf-8") == 'USE="X"\n'


@pytest.mark.parametrize(
    "value", ["-j4", "-j4 -l4", "-j16 -l16", "-l4.5", "--jobs=8", "--load-average=4.5"]
)
def test_the_makeopts_the_screen_suggests_still_go_through(
    portage: Path, value: str
) -> None:
    target = portage / "make.conf"
    target.write_text("# notes\n", encoding="utf-8")
    assert call("append_line", path=str(target), line=f'MAKEOPTS="{value}"')["ok"]


def test_what_suggest_makeopts_produces_is_what_the_helper_accepts(portage: Path) -> None:
    """The screen's own suggestion has to survive the boundary it is written
    across — otherwise the one value Gentstore proposes is one it refuses."""
    from gentstore.core import makeconf  # noqa: PLC0415

    target = portage / "make.conf"
    target.write_text("# notes\n", encoding="utf-8")
    suggestion = makeconf.suggest_makeopts().value

    line = makeconf.format_line("MAKEOPTS", suggestion)
    assert call("append_line", path=str(target), line=line)["ok"], suggestion


def test_the_helper_and_the_interface_agree_on_features() -> None:
    """The third copied list, and the same rent as the other two."""
    from gentstore.core import makeconf  # noqa: PLC0415

    assert helper.FEATURES_OPTIONAL == makeconf.FEATURES_OPTIONAL
    assert helper.FEATURES_PROTECTIVE == makeconf.FEATURES_PROTECTIVE
    # No token may be in both: "may be switched off" and "protects something"
    # are the two halves of one question.
    assert not (helper.FEATURES_OPTIONAL & helper.FEATURES_PROTECTIVE)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("FEATURES", "-sandbox"),
        ("FEATURES", "not-a-real-feature"),
        ("MAKEOPTS", "-f/tmp/x.mk"),
        ("MAKEOPTS", "--eval=x"),
    ],
)
def test_the_screen_refuses_what_the_helper_refuses(name: str, value: str) -> None:
    """The other direction of the seam.

    A stricter helper than the screen it serves is a refusal the user cannot
    act on; the screen has to say no first, while they are still looking at
    what they typed.
    """
    from gentstore.core import makeconf  # noqa: PLC0415

    assert makeconf.unsafe_value(name, value) is not None


# -- what counts as one line ------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "app-x/y flag\rsys-apps/portage -rsync-verify",
        "app-x/y flag\r\nsys-apps/portage -rsync-verify",
        "app-x/y flag\vsys-apps/portage -rsync-verify",
        "app-x/y flag\fsys-apps/portage -rsync-verify",
        "app-x/y flag sys-apps/portage -rsync-verify",
        "app-x/y flag\u0085sys-apps/portage -rsync-verify",
        "app-x/y flag\x1csys-apps/portage -rsync-verify",
    ],
)
def test_a_line_another_program_would_read_as_two_is_not_one_line(
    portage: Path, line: str
) -> None:
    """The check was against "\\n", and that is not what a line is to the
    program that reads these files afterwards.

    portage.util.grablines opens them in universal-newline mode, so a "\\r" in
    the middle of what this program called one line is a line break to Portage:
    the request wrote two configuration entries and the preview the user agreed
    to had shown one.
    """
    target = portage / "package.use"
    target.write_text("media-video/mpv vulkan\n", encoding="utf-8")

    answer = call("append_line", path=str(target), line=line)

    assert answer["code"] == "multiline", answer
    assert target.read_bytes() == b"media-video/mpv vulkan\n"


def test_a_grouped_write_counts_a_line_the_same_way(portage: Path) -> None:
    """Every entry is checked exactly as if it had arrived on its own."""
    (portage / "package.use").mkdir()
    answer = call(
        "append_lines",
        entries=[
            {"path": str(portage / "package.use" / "mpv"), "line": "media-video/mpv vulkan"},
            {
                "path": str(portage / "package.use" / "other"),
                "line": "app-x/y flag\rsys-apps/portage -rsync-verify",
            },
        ],
    )

    assert answer["code"] == "multiline", answer
    assert answer["error"].startswith("entry 2")
    assert not (portage / "package.use" / "mpv").exists()


def test_what_this_program_calls_a_line_is_what_portage_calls_a_line(
    portage: Path,
) -> None:
    """The two have to agree, so ask the one that decides.

    ``_lines`` used to be ``splitlines()``, which breaks on \\v, \\f, U+0085 and
    U+2028 as well — none of which Portage treats as a line ending. A file
    holding one of those had more lines here than it had there, and "exactly
    one line matches" was then a statement about a different file.
    """
    portage_util = pytest.importorskip("portage.util")

    target = portage / "package.use"
    body = "media-video/mpv vulkan\napp-x/y flag still-the-same-line\nsys-apps/portage x\n"
    target.write_text(body, encoding="utf-8")

    theirs = [line.rstrip("\n") for line in portage_util.grablines(str(target))]
    assert helper._lines(helper._read(target)) == theirs


def test_the_file_keeps_its_shape_when_a_line_is_replaced(portage: Path) -> None:
    """Docs/04-privileges.md §4: the rest of the file, comments and blank lines
    included, is left exactly as it was."""
    target = portage / "make.conf"
    body = '# tuned for this box\n\nUSE="X"\n\n# keep this comment\nMAKEOPTS="-j4"\n'
    target.write_text(body, encoding="utf-8")

    answer = call(
        "replace_line",
        path=str(target),
        line='USE="X wayland"',
        match_kind="assignment",
        match_literal="USE",
    )

    assert answer["ok"], answer
    assert target.read_text(encoding="utf-8") == body.replace('USE="X"', 'USE="X wayland"')


def test_a_line_that_is_already_there_is_recognised_as_already_there(
    portage: Path,
) -> None:
    """The duplicate check compares against _lines, so the two notions of a
    line have to be the same one or the promise in Docs §4 quietly stops
    holding."""
    target = portage / "package.use"
    target.write_text("media-video/mpv vulkan\n", encoding="utf-8")

    first = call("append_line", path=str(target), line="app-x/y flag")
    second = call("append_line", path=str(target), line="app-x/y flag")

    assert first["changed"] is True
    assert second["changed"] is False
    assert target.read_text(encoding="utf-8").count("app-x/y flag") == 1


# -- the contract: one JSON answer, always ----------------------------------


def test_a_deeply_nested_request_is_a_refusal_not_a_traceback() -> None:
    """RecursionError is a RuntimeError, so the sieve in main() never saw it.

    json.loads raises it on deeply nested input, and this program then answered
    a request with a traceback on stderr and no JSON at all — which the client
    reads as "no_answer" with an empty message, the least informative outcome
    there is. The comment above that sieve already said a traceback instead of
    an answer is a worse bug than whatever caused it.
    """
    stdout = io.StringIO()
    helper.main(io.StringIO("[" * 200_000 + "]" * 200_000), stdout)

    answer = json.loads(stdout.getvalue())
    assert answer["ok"] is False
    assert answer["code"] == "bad_json"


def test_a_request_larger_than_the_limit_is_refused() -> None:
    """Standard input is chosen by the caller, who is not obliged to be
    Gentstore and is talking to a process running as root."""
    stdout = io.StringIO()
    payload = '{"op": "backup", "pad": "' + "x" * helper.STDIN_MAX + '"}'
    helper.main(io.StringIO(payload), stdout)

    answer = json.loads(stdout.getvalue())
    assert answer["code"] == "too_large"


def test_the_answer_is_json_whatever_arrives(portage: Path) -> None:
    """The whole contract of this program, as one test."""
    for payload in (
        "",
        "not json",
        "[" * 100_000 + "]" * 100_000,
        '{"op": "append_line"}',
        '{"op": "nonsense"}',
        "[1, 2, 3]",
        '{"op": "append_line", "path": 7, "line": null}',
    ):
        stdout = io.StringIO()
        helper.main(io.StringIO(payload), stdout)
        answer = json.loads(stdout.getvalue())
        assert answer["ok"] is False, payload
        assert answer["code"], payload
