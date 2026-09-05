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

"""Tests for running commands and for deciding how to become root.

Nothing here runs anything privileged: the tests that matter are about what the
launcher refuses, how a command line is assembled, and whether a running command
can actually be stopped — and that last one is checked against a real process.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from gentstore.core import backup as backup_core
from gentstore.helper import gentstore_helper as helper
from gentstore.helper import gentstore_launcher as launcher
from gentstore.runner import emerge, eselect, privilege
from gentstore.runner.command import Command, CommandError, CommandSpec
from gentstore.ui.widgets.log_view import classify

# -- the launcher's allowlist ----------------------------------------------


def test_the_launcher_runs_only_the_programs_gentstore_drives() -> None:
    with pytest.raises(launcher.LauncherError, match="not one of"):
        launcher.resolve("rm")


def test_the_launcher_refuses_a_path_instead_of_a_name() -> None:
    """Otherwise the allowlist could be walked around with /bin/../bin/sh."""
    with pytest.raises(launcher.LauncherError, match="not a path"):
        launcher.resolve("/bin/sh")
    with pytest.raises(launcher.LauncherError, match="not a path"):
        launcher.resolve("../../bin/sh")


def test_the_launcher_finds_emerge_where_it_lives() -> None:
    if not any((directory / "emerge").exists() for directory in launcher.SEARCH_PATH):
        pytest.skip("Portage is not installed here")
    assert launcher.resolve("emerge").name == "emerge"


def test_the_launcher_ignores_a_planted_path(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """PATH is the obvious thing to bend under the sudo fallback."""
    fake = tmp_path / "emerge"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))

    if not any((directory / "emerge").exists() for directory in launcher.SEARCH_PATH):
        pytest.skip("Portage is not installed here")
    assert launcher.resolve("emerge").parent in launcher.SEARCH_PATH


def test_the_launcher_no_longer_offers_an_editor() -> None:
    """dispatch-conf and etc-update spawn one, and nothing here asks for them."""
    assert "dispatch-conf" not in launcher.ALLOWED
    assert "etc-update" not in launcher.ALLOWED


def every_emerge_command() -> tuple[object, ...]:
    """Every ``emerge`` command line the interface can build, options and all.

    Written out rather than discovered by walking the module. The point of the
    list is to notice a builder growing an option or losing one, and anything
    that found the commands by following the code would follow it there too and
    keep agreeing with itself.

    Both halves of each optional flag appear, because "with ``--getbinpkg``" and
    "without it" are two different command lines as far as the launcher's table
    is concerned.
    """
    return (
        emerge.install(["media-video/mpv"]),
        emerge.install(["media-video/mpv"], oneshot=True, binaries=True),
        emerge.install(["media-video/mpv"], binaries=True),
        emerge.install(["media-video/mpv", "www-client/firefox"], oneshot=True),
        # Unprivileged, so these never reach the launcher today. They are here
        # because the table describes what the interface builds, and a preview
        # that started needing root would otherwise fail at the last moment.
        emerge.pretend(["media-video/mpv"]),
        emerge.pretend(["media-video/mpv"], oneshot=True),
        emerge.analyse(["media-video/mpv"]),
        emerge.analyse(["media-video/mpv"], binaries=True),
        emerge.analyse(["media-video/mpv"], oneshot=True, binaries=True),
        emerge.unmerge_pretend(["media-video/mpv"]),
        emerge.update_world_pretend(),
        emerge.update_world_pretend(binaries=True),
        emerge.depclean_pretend(),
        emerge.update_world(),
        emerge.unmerge(["media-video/mpv"]),
        emerge.deselect(["media-video/mpv"]),
        emerge.select(["media-video/mpv"]),
        emerge.update_world(binaries=True),
        emerge.depclean(),
        emerge.preserved_rebuild(),
    )


def test_the_launcher_accepts_every_command_the_interface_builds() -> None:
    """The grammar in the launcher and the two builders have to stay in step.

    If this fails after a command was added to runner/emerge.py or
    runner/eselect.py, the command is the thing that is new — say so in the
    launcher too. That file is the list of what one authentication buys.
    """
    for spec in (
        *every_emerge_command(),
        emerge.sync_all(),
        eselect.enable("guru"),
        eselect.add("myrepo", "git", "https://github.com/x/y.git"),
        eselect.disable("guru", force=True),
        eselect.remove("guru"),
        eselect.sync("guru"),
        eselect.read_news(privileged=True),
        eselect.fix_glsa(),
        eselect.fix_glsa(("202501-15",)),
        eselect.set_profile(7),
    ):
        launcher.check_arguments(spec.argv[0], list(spec.argv[1:]))


@pytest.mark.parametrize(
    ("program", "arguments"),
    [
        # --config runs a package's own configuration script as root.
        ("emerge", ["--config", "sys-apps/portage"]),
        ("emerge", ["--root=/tmp/somewhere", "media-video/mpv"]),
        ("emerge", ["--sync"]),
        # The analysis is allowed; these two turn it into something that edits
        # /etc/portage on its own, which is the helper's job and only its job.
        (
            "emerge",
            [
                "--ignore-default-opts", "--color=n", "--nospinner", "--pretend",
                "--verbose", "--autounmask", "--autounmask-write", "media-video/mpv",
            ],
        ),
        (
            "emerge",
            [
                "--ignore-default-opts", "--color=n", "--nospinner", "--pretend",
                "--verbose", "--autounmask", "--autounmask-continue", "media-video/mpv",
            ],
        ),
        (
            "emerge",
            [
                "--ignore-default-opts", "--color=n", "--nospinner", "--pretend",
                "--verbose", "--autounmask", "--autounmask-license=y", "--ask",
                "media-video/mpv",
            ],
        ),
        # --autounmask-license takes a value, and only the one the builder sends.
        (
            "emerge",
            [
                "--ignore-default-opts", "--color=n", "--nospinner", "--pretend",
                "--verbose", "--autounmask", "--autounmask-license=n", "media-video/mpv",
            ],
        ),
        ("emerge", ["--usepkgonly", "media-video/mpv"]),
        # An option carrying a value is a place to hide one.
        ("emerge", ["--color=y", "media-video/mpv"]),
        # emerge reads these as a file to merge, not as a package to look up.
        ("emerge", ["/tmp/evil.ebuild"]),
        ("emerge", ["tmp/evil.ebuild"]),
        ("eselect", ["modules", "list"]),
        # git reads ext:: as "run this command"; the "://" is decoration.
        ("eselect", ["repository", "add", "evil", "git", "ext::sh -c 'id' ://"]),
        ("emaint", ["merges", "-f"]),
        ("glsa-check", ["-f", "; id"]),
    ],
)
def test_the_launcher_refuses_arguments_the_interface_never_builds(
    program: str, arguments: list[str]
) -> None:
    """One authentication buys the commands Gentstore runs, and no others.

    Anything running as the user can reach this program, and the dialog in front
    of it says only "install, update or remove packages". What is behind it has
    to be worth no more than that.
    """
    with pytest.raises(launcher.LauncherError):
        launcher.check_arguments(program, arguments)


@pytest.mark.parametrize(
    "arguments",
    [
        # Removing the system. A set is a literal in the two rows that take
        # one, so it cannot appear where a package is expected.
[*launcher._EMERGE_BASE, "--unmerge", "@world"],
[*launcher._EMERGE_BASE, "--unmerge", "@system"],
[*launcher._EMERGE_BASE, "--unmerge", "@preserved-rebuild"],
[*launcher._EMERGE_BASE, "--pretend", "--verbose", "--unmerge", "@world"],
        # --depclean works out for itself what is orphaned. Given a package it
        # means something else, and the update screen never asks for it.
[*launcher._EMERGE_BASE, "--depclean", "media-video/mpv"],
[*launcher._EMERGE_BASE, "--pretend", "--depclean", "media-video/mpv"],
[*launcher._EMERGE_BASE, "--depclean", "@world"],
        # Options the interface never puts together, each one allowed on its
        # own by the old set of permitted options.
[*launcher._EMERGE_BASE, "--unmerge", "--getbinpkg", "media-video/mpv"],
[*launcher._EMERGE_BASE, "--deselect", "--oneshot", "media-video/mpv"],
[*launcher._EMERGE_BASE, "--select", "media-video/mpv"],
[*launcher._EMERGE_BASE, "--unmerge", "--deselect", "media-video/mpv"],
[*launcher._EMERGE_BASE, "--verbose", "--depclean", "media-video/mpv"],
        # The right options in an order nothing builds.
[*launcher._EMERGE_BASE, "--verbose", "--oneshot", "--getbinpkg", "media-video/mpv"],
        ["--ignore-default-opts", "--nospinner", "--color=n", "--verbose", "media-video/mpv"],
        # A world update has to be a world update.
[*launcher._EMERGE_BASE, "--verbose", "--update", "--deep", "--newuse"],
[*launcher._EMERGE_BASE, "--verbose", "--update", "--deep", "--newuse", "@system"],
        # Nothing to work on.
[*launcher._EMERGE_BASE, "--verbose"],
[*launcher._EMERGE_BASE, "--unmerge"],
    ],
)
def test_the_launcher_refuses_emerge_commands_the_interface_never_builds(
    arguments: list[str],
) -> None:
    """The whole point of a table of commands rather than a set of options.

    Every option in these lines was on the old permitted list, and every one of
    these lines was therefore allowed. ``emerge --unmerge @world`` is the one
    that matters — it is not "remove packages", it is "remove the system" — but
    ``--depclean`` with a package beside it is a different operation from the
    one the update screen previews, and neither is something a button here can
    produce.
    """
    with pytest.raises(launcher.LauncherError):
        launcher.check_arguments("emerge", arguments)


# -- EMERGE_DEFAULT_OPTS ----------------------------------------------------


def test_every_emerge_command_ignores_the_users_default_options() -> None:
    """Otherwise the command that runs is not the command that was checked.

    ``emerge`` reads ``EMERGE_DEFAULT_OPTS`` from ``make.conf`` and puts it in
    front of the argument list before working out what it has been asked to do
    (``_emerge/main.py``: ``if "--ignore-default-opts" not in myopts``). Every
    validator in this project looks at the argv Gentstore built, so without this
    flag all of them are checking a prefix of the real command.
    """
    for spec in every_emerge_command():
        assert "--ignore-default-opts" in spec.argv, spec.display


def test_the_preview_and_the_real_thing_have_the_same_policy() -> None:
    """A preview that ignores the default options and a run that does not would
    be the worst of the three possible arrangements: the table on screen would
    be right about a command nobody was going to run.

    Checked as pairs, because that is the property — not "both contain a flag"
    but "the option that decides this is the same on both sides".
    """
    pairs = (
        (emerge.pretend(["media-video/mpv"]), emerge.install(["media-video/mpv"])),
        (emerge.unmerge_pretend(["media-video/mpv"]), emerge.unmerge(["media-video/mpv"])),
        (emerge.update_world_pretend(), emerge.update_world()),
        (emerge.depclean_pretend(), emerge.depclean()),
    )
    for preview, real in pairs:
        assert ("--ignore-default-opts" in preview.argv) is (
            "--ignore-default-opts" in real.argv
        ), preview.display


def test_the_launcher_and_the_builders_agree_on_the_base() -> None:
    """Two files, three options, one order. Compared rather than assumed.

    The launcher's rows all start with its own copy of the base. If the two
    drifted, every row would describe a command the interface no longer builds
    and the suite would say so somewhere else — but it would say it eighteen
    times, about the wrong thing.
    """
    assert emerge._BASE[0] == "emerge"
    assert emerge._BASE[1:] == launcher._EMERGE_BASE


def test_a_command_without_the_flag_is_not_a_command_gentstore_runs() -> None:
    """The launcher requires it rather than tolerating it.

    A command arriving here without it is one whose meaning this program cannot
    vouch for, whoever built it — the argv says one thing and Portage would do
    that plus whatever is in the user's make.conf.
    """
    for spec in every_emerge_command():
        stripped = [
            argument for argument in spec.argv[1:] if argument != "--ignore-default-opts"
        ]
        with pytest.raises(launcher.LauncherError):
            launcher.check_arguments("emerge", stripped)


def test_the_installed_emerge_still_understands_the_flag(portage_env) -> None:
    """The whole fix rests on one option of somebody else's program.

    Not a run of ``emerge`` — nothing here is worth starting a real one for.
    ``parse_opts`` is the function ``main()`` calls on the argv before deciding
    whether to prepend ``EMERGE_DEFAULT_OPTS``, so a flag it puts in ``myopts``
    is a flag that decision can see.
    """
    main = pytest.importorskip("_emerge.main")

    _action, options, _files = main.parse_opts(
        ["--ignore-default-opts", "--pretend", "--verbose", "sys-apps/portage"], silent=True
    )
    assert "--ignore-default-opts" in options

    # And it is not simply ignored as an unknown word: without it the same parse
    # does not invent it.
    _action, without, _files = main.parse_opts(
        ["--pretend", "--verbose", "sys-apps/portage"], silent=True
    )
    assert "--ignore-default-opts" not in without


# -- the table and the builders, in both directions --------------------------


def test_every_launcher_template_belongs_to_a_command_the_interface_builds() -> None:
    """The direction the other test does not cover.

    A builder can be changed or dropped and its row left behind, and nothing
    would fail: the row would go on granting a command through one
    authentication that the application has no way to ask for. Checked against
    the same written-out list, so the two directions cannot both be satisfied by
    editing one place.
    """
    built = [list(spec.argv[1:]) for spec in every_emerge_command()]
    orphaned = [
        " ".join(template)
        for template in launcher.EMERGE_COMMANDS
        if not any(launcher._matches(template, arguments) for arguments in built)
    ]
    assert orphaned == [], "no builder produces these rows any more"


def test_the_child_gets_an_unbuffered_environment() -> None:
    environment = launcher.child_environment()
    assert environment["PYTHONUNBUFFERED"] == "1"
    assert "PATH" in environment


def test_the_launcher_stops_a_child_when_told_to_abort() -> None:
    """The whole reason the launcher exists: the interface cannot signal root."""
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True
    )
    try:
        launcher.watch_for_abort(process, iter(["abort\n"]))
        assert process.poll() is not None, "the child should have been stopped"
    finally:
        if process.poll() is None:  # pragma: no cover - only if the test failed
            process.kill()


def test_end_of_input_also_stops_the_child() -> None:
    """If the interface died, its build should not carry on unattended."""
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True
    )
    try:
        launcher.watch_for_abort(process, iter([]))
        assert process.poll() is not None
    finally:
        if process.poll() is None:  # pragma: no cover
            process.kill()


# -- becoming root ----------------------------------------------------------


def test_pkexec_is_preferred_when_it_is_there(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(privilege.shutil, "which", lambda name: f"/usr/bin/{name}")
    escalation = privilege.detect()
    assert escalation.kind == "pkexec"
    assert escalation.is_available


def test_sudo_is_the_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        privilege.shutil, "which", lambda name: "/usr/bin/sudo" if name == "sudo" else None
    )
    monkeypatch.setenv("SUDO_ASKPASS", "/usr/bin/ssh-askpass")
    escalation = privilege.detect()
    assert escalation.kind == "sudo"
    assert escalation.wrap(("emerge", "-pv"))[:2] == ("/usr/bin/sudo", "-A")


def test_sudo_without_a_way_to_ask_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        privilege.shutil, "which", lambda name: "/usr/bin/sudo" if name == "sudo" else None
    )
    monkeypatch.delenv("SUDO_ASKPASS", raising=False)
    monkeypatch.setattr(privilege.sys, "stdin", None)

    escalation = privilege.detect()
    assert not escalation.is_available
    assert "SUDO_ASKPASS" in (escalation.problem or "")


def test_running_as_root_needs_no_escalation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(privilege.os, "geteuid", lambda: 0)
    escalation = privilege.detect()
    assert escalation.kind == "direct"
    assert escalation.is_available
    assert escalation.wrap(("emerge", "-pv")) == ("emerge", "-pv")


def test_no_way_to_become_root_at_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(privilege.shutil, "which", lambda _name: None)
    escalation = privilege.detect()
    assert escalation.kind == "none"
    assert not escalation.is_available


# -- an alternate root ------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("ROOT", "/mnt/gentoo"),
        ("PORTAGE_CONFIGROOT", "/mnt/gentoo"),
        ("SYSROOT", "/mnt/gentoo"),
        ("EPREFIX", "/opt/prefix"),
    ],
)
def test_nothing_runs_as_root_while_portage_describes_another_system(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    """The preview and the change have to be about the same machine.

    ``create_trees(env=os.environ)`` honours all four of these, so the interface
    would describe whatever they point at. Nothing privileged follows them: the
    helper's root is the constant ``/etc/portage`` and the launcher's child gets
    a fixed environment. Showing a change to one system and making it to another
    is the failure this refuses.
    """
    for variable in privilege.ALTERNATE_ROOT_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv(name, value)

    escalation = privilege.detect()

    assert escalation.is_available is False
    assert escalation.problem is not None
    assert name in escalation.problem
    assert value in escalation.problem


def test_the_refusal_reaches_both_privileged_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """One check, because both paths ask :func:`detect` the same question."""
    from gentstore.runner import helper_client

    for variable in privilege.ALTERNATE_ROOT_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("ROOT", "/mnt/gentoo")

    answer = helper_client.request("append_line", path="/etc/portage/package.use/x", line="y")

    assert answer.ok is False
    assert answer.code == "no_privilege"
    assert "ROOT" in answer.error


@pytest.mark.parametrize(
    "environ",
    [
        {},
        {"ROOT": "/"},
        {"ROOT": "//"},
        {"ROOT": "/."},
        {"PORTAGE_CONFIGROOT": "/", "SYSROOT": "/", "EPREFIX": ""},
        {"ROOT": ""},
    ],
)
def test_an_ordinary_system_is_not_mistaken_for_a_chroot(environ: dict) -> None:
    """``ROOT=/`` is what a normal Gentoo sets; refusing it would refuse everybody."""
    assert privilege.alternate_root(environ) is None


def test_the_helper_is_found_where_it_is_installed() -> None:
    """Installed is the case that works without anybody asking for it."""
    program = privilege.helper_command()
    if program is None:
        pytest.skip("the helper is not installed and the development opt-in is off")

    assert not program.is_development_copy
    assert Path(program.argv[-1]).name == privilege.HELPER_NAME
    assert Path(program.argv[0]).parent == privilege.INSTALL_DIR


def test_the_source_copy_is_not_run_as_root_unless_asked_for(tmp_path, monkeypatch) -> None:
    """A checkout is files the user can write; pkexec checks python3, not them.

    So the fallback that runs `python3 …/gentstore_helper.py` as root is off
    unless somebody turns it on. Anything able to write into the checkout would
    otherwise be one authentication away from root — and the dialog would be
    the generic "run a program as another user" one, because polkit has no
    action registered for that path.
    """
    source = tmp_path / "gentstore_helper.py"
    source.write_text("print('hello')\n", encoding="utf-8")
    monkeypatch.setattr(privilege, "INSTALL_DIR", tmp_path / "nothing-installed")
    monkeypatch.delenv(privilege.DEV_VARIABLE, raising=False)

    assert privilege._locate(privilege.HELPER_NAME, source) is None

    monkeypatch.setenv(privilege.DEV_VARIABLE, "1")
    program = privilege._locate(privilege.HELPER_NAME, source)
    assert program is not None
    assert program.is_development_copy
    assert program.argv == (sys.executable, str(source))


def test_a_file_other_users_can_write_is_never_run_as_root(tmp_path, monkeypatch) -> None:
    """The opt-in is for a machine you develop on, not for a shared one."""
    monkeypatch.setattr(privilege, "INSTALL_DIR", tmp_path / "nothing-installed")
    monkeypatch.setenv(privilege.DEV_VARIABLE, "1")

    writable = tmp_path / "gentstore_helper.py"
    writable.write_text("print('hello')\n", encoding="utf-8")
    writable.chmod(0o666)
    assert privilege._locate(privilege.HELPER_NAME, writable) is None

    # A directory is enough: whoever can write one can swap the file inside it.
    loose = tmp_path / "loose"
    loose.mkdir()
    loose.chmod(0o777)
    inside = loose / "gentstore_helper.py"
    inside.write_text("print('hello')\n", encoding="utf-8")
    inside.chmod(0o644)
    assert privilege._locate(privilege.HELPER_NAME, inside) is None


def test_a_stale_installed_copy_is_noticed() -> None:
    """The two halves are versioned together, so a mismatch has to be visible.

    Not asserted as a failure: whether the machine running the tests has
    reinstalled after the last change is not a property of the code. What *is*
    a property of the code is that it can tell, and this checks that it can.
    """
    status = privilege.installed_status(privilege.HELPER_NAME, refresh=True)
    if not status.installed:
        pytest.skip("the helper is not installed on this machine")

    source = Path(privilege.__file__).resolve().parent.parent / "helper" / "gentstore_helper.py"
    # Bodies, not bytes. The ``#!`` line is deliberately left out of the
    # comparison — a correctly installed copy has had it rewritten to the exact
    # interpreter the package was built for — so comparing raw bytes here would
    # be a stricter question than the code asks and would fail on a machine
    # where the install had worked. That the shebang alone is not staleness has
    # a test of its own in the packaging suite.
    same = privilege._body(status.path.read_bytes()) == privilege._body(source.read_bytes())
    assert status.current is same
    assert status.is_stale is not same


def test_a_matching_copy_is_not_reported_as_stale(tmp_path, monkeypatch) -> None:
    source = tmp_path / "gentstore_helper.py"
    source.write_text("print('hello')\n", encoding="utf-8")
    installed = tmp_path / "installed"
    installed.mkdir()
    (installed / privilege.HELPER_NAME).write_text("print('hello')\n", encoding="utf-8")

    monkeypatch.setattr(privilege, "INSTALL_DIR", installed)
    monkeypatch.setattr(privilege, "_PROGRAMS", {privilege.HELPER_NAME: source})

    status = privilege.installed_status(privilege.HELPER_NAME, refresh=True)
    assert status.installed and status.current and not status.is_stale
    assert privilege.stale_programs(refresh=True) == ()


def test_a_differing_copy_is_reported_as_stale(tmp_path, monkeypatch) -> None:
    """The case that produced a baffling refusal until it was detected.

    An installed helper from before ``cfg_apply`` learned to reach outside
    /etc/portage refuses a perfectly ordinary configuration-file decision with
    "outside_root", and nothing in the interface explains why.
    """
    source = tmp_path / "gentstore_helper.py"
    source.write_text("print('new')\n", encoding="utf-8")
    installed = tmp_path / "installed"
    installed.mkdir()
    (installed / privilege.HELPER_NAME).write_text("print('old')\n", encoding="utf-8")

    monkeypatch.setattr(privilege, "INSTALL_DIR", installed)
    monkeypatch.setattr(privilege, "_PROGRAMS", {privilege.HELPER_NAME: source})

    assert privilege.installed_status(privilege.HELPER_NAME, refresh=True).is_stale
    assert [s.name for s in privilege.stale_programs(refresh=True)] == [privilege.HELPER_NAME]


def test_reinstalling_is_noticed_without_being_asked_to_look_again(
    tmp_path, monkeypatch
) -> None:
    """The advice has to stop once it has been taken.

    ``installed_status`` remembers its answer, and every other test here passes
    ``refresh=True`` — which is exactly how this went unnoticed. In the running
    application nothing passes it: the status bar asks once at start-up and
    ``helper_client._annotate`` asks again on every refusal. So the interface
    said "the installed helper is from an older version, run
    `sudo make install-system`", somebody ran it, and the memo went on saying it
    for the rest of the session, about a file that had since been replaced.

    A stat is what tells the memo its subject has moved.
    """
    from gentstore.runner import helper_client

    source = tmp_path / "gentstore_helper.py"
    source.write_text("new\n", encoding="utf-8")
    installed = tmp_path / "installed"
    installed.mkdir()
    copy = installed / privilege.HELPER_NAME
    copy.write_text("old\n", encoding="utf-8")
    monkeypatch.setattr(privilege, "INSTALL_DIR", installed)
    monkeypatch.setattr(privilege, "_PROGRAMS", {privilege.HELPER_NAME: source})

    assert privilege.stale_programs()  # asked the way the application asks
    assert "make install-system" in helper_client._annotate("outside_root")

    # `sudo make install-system`, in the only way that matters here.
    copy.unlink()
    copy.write_text("new\n", encoding="utf-8")

    assert privilege.stale_programs() == ()
    assert helper_client._annotate("outside_root") == "outside_root"


def test_a_refusal_says_when_a_stale_helper_may_be_the_reason(tmp_path, monkeypatch) -> None:
    from gentstore.runner import helper_client

    source = tmp_path / "gentstore_helper.py"
    source.write_text("new\n", encoding="utf-8")
    installed = tmp_path / "installed"
    installed.mkdir()
    (installed / privilege.HELPER_NAME).write_text("old\n", encoding="utf-8")
    monkeypatch.setattr(privilege, "INSTALL_DIR", installed)
    monkeypatch.setattr(privilege, "_PROGRAMS", {privilege.HELPER_NAME: source})
    privilege.stale_programs(refresh=True)

    annotated = helper_client._annotate("outside_root: /etc/fstab is outside /etc/portage")
    assert "older version" in annotated
    assert "make install-system" in annotated


# -- the command lines ------------------------------------------------------


def test_pretend_needs_no_privileges() -> None:
    spec = emerge.pretend(["media-video/mpv"])
    assert not spec.privileged
    assert "--pretend" in spec.argv


def test_installing_does_need_them() -> None:
    assert emerge.install(["media-video/mpv"]).privileged


def test_every_emerge_command_turns_colour_and_the_spinner_off() -> None:
    for spec in (
        emerge.pretend(["x"]),
        emerge.install(["x"]),
        emerge.unmerge(["x"]),
        emerge.update_world(),
    ):
        assert "--color=n" in spec.argv
        assert "--nospinner" in spec.argv


def test_oneshot_keeps_a_package_out_of_world() -> None:
    assert "--oneshot" in emerge.install(["x"], oneshot=True).argv
    assert "--oneshot" not in emerge.install(["x"]).argv


def test_removing_is_unmerge_and_never_depclean() -> None:
    """--unmerge removes what it is given; --depclean decides for itself."""
    argv = emerge.unmerge(["media-video/mpv"]).argv
    assert "--unmerge" in argv
    assert "--depclean" not in argv


def test_the_display_string_is_what_somebody_would_type() -> None:
    spec = emerge.pretend(["media-video/mpv"])
    assert spec.display == (
        "emerge --ignore-default-opts --color=n --nospinner "
        "--pretend --verbose media-video/mpv"
    )


# -- running one ------------------------------------------------------------


def settle(seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QApplication.processEvents()


def _pkexec() -> privilege.Escalation:
    return privilege.Escalation("pkexec", "/usr/bin/pkexec")


@pytest.fixture
def runner(app):  # noqa: ANN001, ANN201 - conftest fixture
    """A Command that is always shut down, however the test ended.

    Letting one be garbage-collected with a process still attached is how the
    suite learned that Command needed a close() at all: the finished signal
    arrived at an object Python had already reclaimed, and the process aborted.
    """
    command = Command()
    yield command
    command.close()


def run_and_wait(runner: Command, spec: CommandSpec, seconds: float = 10.0) -> list:
    lines: list[str] = []
    codes: list[int] = []
    runner.output.connect(lines.append)
    runner.finished.connect(codes.append)
    runner.start(spec)

    deadline = time.monotonic() + seconds
    while runner.is_running() and time.monotonic() < deadline:
        QApplication.processEvents()
    settle(0.2)
    return [lines, codes]


def test_output_arrives_as_whole_lines(runner: Command) -> None:
    spec = CommandSpec(
        argv=(sys.executable, "-c", "print('first'); print('second')"),
    )
    lines, codes = run_and_wait(runner, spec)
    assert lines == ["first", "second"]
    assert codes == [0]


def test_a_non_zero_exit_is_reported_rather_than_treated_as_an_error(runner: Command) -> None:
    """A failing emerge is a normal outcome the user needs to read."""
    spec = CommandSpec(argv=(sys.executable, "-c", "raise SystemExit(7)"))
    _lines, codes = run_and_wait(runner, spec)
    assert codes == [7]


def test_only_one_command_runs_at_a_time(runner: Command) -> None:
    runner.start(CommandSpec(argv=(sys.executable, "-c", "import time; time.sleep(2)")))
    try:
        with pytest.raises(CommandError, match="still running"):
            runner.start(CommandSpec(argv=(sys.executable, "-c", "pass")))
    finally:
        runner.close()


def test_a_running_command_can_be_stopped(runner: Command) -> None:
    failures: list[str] = []
    runner.failed.connect(failures.append)
    runner.start(CommandSpec(argv=(sys.executable, "-c", "import time; time.sleep(30)")))
    settle(0.4)

    runner.abort()
    deadline = time.monotonic() + 10
    while runner.is_running() and time.monotonic() < deadline:
        QApplication.processEvents()

    assert not runner.is_running(), "SIGINT should have stopped it"
    assert failures, "stopping should be reported, not silently treated as success"


def test_a_privileged_command_needs_the_launcher(runner: Command, monkeypatch) -> None:
    monkeypatch.setattr(privilege, "launcher_command", lambda: None)
    monkeypatch.setattr(privilege, "detect", _pkexec)
    with pytest.raises(CommandError, match="launcher"):
        runner.start(emerge.install(["media-video/mpv"]))


def test_a_privileged_command_is_wrapped_in_both_layers(runner: Command, monkeypatch) -> None:
    """pkexec outside, the launcher inside, the command last.

    Both halves are supplied rather than looked up. Asking the machine for its
    launcher made this a test of whether `sudo make install-system` had been run
    here — green on the maintainer's machine, and a CommandError anywhere else,
    including every CI runner. The order is a property of the code.
    """
    monkeypatch.setattr(privilege, "detect", _pkexec)
    monkeypatch.setattr(
        privilege,
        "launcher_command",
        lambda: privilege.PrivilegedProgram(
            argv=(str(privilege.INSTALL_DIR / privilege.LAUNCHER_NAME),), installed=True
        ),
    )
    argv = runner._resolve(emerge.install(["media-video/mpv"]))
    assert argv[0] == "/usr/bin/pkexec"
    assert "emerge" in argv
    assert argv.index("/usr/bin/pkexec") < argv.index("emerge")


# -- the client and the helper, over a real subprocess ----------------------


WRAPPER = """
import json, sys
from pathlib import Path
from gentstore.helper import gentstore_helper as helper
helper.CONFIG_ROOT = Path(sys.argv[1])
helper.BACKUP_PARENT = Path(sys.argv[1]).parent
sys.exit(helper.main())
"""


@pytest.fixture
def local_helper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run the helper as an ordinary process against a throwaway /etc/portage.

    The privilege wrapper is replaced with nothing, so this exercises the real
    JSON protocol over a real subprocess without needing root — the one part of
    the privileged path that can be checked in a test.
    """
    root = tmp_path / "portage"
    root.mkdir()
    wrapper = tmp_path / "wrapper.py"
    wrapper.write_text(WRAPPER, encoding="utf-8")

    monkeypatch.setattr(
        privilege,
        "helper_command",
        lambda: privilege.PrivilegedProgram(
            (sys.executable, str(wrapper), str(root)), installed=False
        ),
    )
    monkeypatch.setattr(privilege, "detect", lambda: privilege.Escalation("direct", None))
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parent.parent))
    return root


def test_the_client_and_the_helper_speak_the_same_protocol(local_helper: Path) -> None:
    from gentstore.runner import helper_client

    target = local_helper / "package.use"
    result = helper_client.request("append_line", path=str(target), line="media-video/mpv vulkan")

    assert result.ok, result.error
    assert result.changed
    assert target.read_text(encoding="utf-8") == "media-video/mpv vulkan\n"


def test_a_refusal_comes_back_as_a_code_the_interface_can_act_on(local_helper: Path) -> None:
    from gentstore.runner import helper_client

    result = helper_client.request("append_line", path="/etc/passwd", line="x")

    assert not result.ok
    assert result.code == "outside_root"
    assert result.error


def test_the_client_reports_a_missing_way_to_become_root(monkeypatch) -> None:
    from gentstore.runner import helper_client

    monkeypatch.setattr(
        privilege, "detect", lambda: privilege.Escalation("none", None, "nothing here")
    )
    result = helper_client.request("backup")
    assert result.code == "no_privilege"


# -- the log ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("!!! ERROR: media-video/mpv failed", "error"),
        (" * Warning: something", "warning"),
        ("*** deprecated", "warning"),
        (">>> Emerging (1 of 3) media-video/mpv-0.41.0", "step"),
        ("[ebuild  N     ] media-video/mpv-0.41.0", "plain"),
    ],
)
def test_log_lines_are_classified_by_portages_own_markers(line: str, expected: str) -> None:
    assert classify(line) == expected


# -- backups ----------------------------------------------------------------


def test_backups_are_listed_newest_first(tmp_path: Path) -> None:
    for stamp in ("2026-01-01T0900", "2026-03-04T1130", "2026-02-02T1000"):
        (tmp_path / f"portage.bak-{stamp}").mkdir()
    (tmp_path / "portage").mkdir()  # not a backup
    (tmp_path / "portage.bak-nonsense").mkdir()

    names = [b.label for b in backup_core.list_backups(tmp_path)]
    assert names == ["2026-03-04T1130", "2026-02-02T1000", "2026-01-01T0900"]


def test_an_unreadable_etc_is_simply_empty(tmp_path: Path) -> None:
    assert backup_core.list_backups(tmp_path / "absent") == ()


def test_one_backup_per_run_not_per_change() -> None:
    tracker = backup_core.BackupTracker()
    assert tracker.needs_backup()
    tracker.note("/etc/portage.bak-2026-01-01T0900")
    assert not tracker.needs_backup()
    assert tracker.taken.endswith("0900")
    tracker.reset()
    assert tracker.needs_backup()


def test_the_helper_and_the_core_agree_on_where_backups_live() -> None:
    """The constant is duplicated across the privilege boundary on purpose."""
    assert backup_core.BACKUP_PARENT == helper.BACKUP_PARENT
    assert backup_core.BACKUP_PREFIX == helper.BACKUP_PREFIX
    assert backup_core.BACKUP_KEEP == helper.BACKUP_KEEP


def test_the_launcher_refuses_every_package_there_is() -> None:
    """``emerge --unmerge '*/*'`` is not "remove packages", it is "remove Gentoo".

    The atom shape allows a wildcard in either half and had nothing to say about
    both at once, so one command line got past every other check in the file —
    behind a dialog that said "install, update or remove packages". Nothing
    Gentstore runs needs it: the one place ``*/*`` is written is
    ``*/*::<overlay>`` into ``package.mask``, and that goes to the helper.
    """
    for atom in ("*/*", "*/*::guru", "=*/*-1", "!*/*", "*/*:0", "*/*[python]"):
        # The command Gentstore itself builds, with only the atom changed, so
        # the refusal can be about the atom and nothing else.
        assert launcher._is_package_atom(atom) is False, atom
        with pytest.raises(launcher.LauncherError):
            launcher.check_arguments(
                "emerge", [*launcher._EMERGE_BASE, "--unmerge", atom]
            )

    # A wildcard on one side is still an ordinary atom and stays allowed.
    launcher.check_arguments(
        "emerge", [*launcher._EMERGE_BASE, "--pretend", "--verbose", "media-video/*"]
    )


def test_the_overlay_dialog_and_the_launcher_agree_on_url_schemes() -> None:
    """Two lists of schemes in two files, with a user standing between them.

    ``svn`` was in one and not the other, so the "Add overlay" dialog enabled its
    OK button for an ``svn://`` URL and the launcher then refused the very
    command the dialog had just promised to run — a failure landing a long way
    from the decision that caused it. Compared by behaviour rather than by
    pattern, so a rewrite of either expression still has to keep the answers the
    same.
    """
    from gentstore.core import overlays

    candidates = (
        "http://example.org/o", "https://example.org/o", "git://example.org/o",
        "ssh://git@example.org/o", "rsync://example.org/o", "svn://example.org/o",
        "file:///srv/o", "ext::sh -c whoami://", "javascript:alert(1)://x",
        "ftp://example.org/o", "git@example.org:owner/repo", "not a url",
    )
    for uri in candidates:
        assert overlays.is_valid_uri(uri) is launcher._is_uri(uri), uri


def test_every_sync_type_the_dialog_offers_is_one_the_launcher_allows() -> None:
    """The other half of the same seam: the dialog's dropdown."""
    from gentstore.ui.widgets.add_overlay_dialog import SYNC_TYPES

    assert set(SYNC_TYPES) <= launcher._SYNC_TYPES
