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

"""The two ways Gentstore gets installed, kept honest.

Neither the ebuild nor the overlay script can be run here — both need root and
a real Portage sandbox. What can be checked is that they stay consistent with
the tree they install from: every file they reach for exists, every path they
write matches the one the running code looks in, and the shell does not run
anything the script only meant to say.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree

import pytest

from gentstore import DESKTOP_ID, ICON_NAME
from gentstore.runner import privilege

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging"
EBUILD = PACKAGING / "app-portage" / "gentstore" / "gentstore-9999.ebuild"
SCRIPT = PACKAGING / "make-overlay.sh"
DESKTOP = ROOT / "data" / f"{DESKTOP_ID}.desktop"


@pytest.fixture(scope="module")
def ebuild() -> str:
    return EBUILD.read_text()


@pytest.fixture(scope="module")
def script() -> str:
    return SCRIPT.read_text()


def phase_body(ebuild: str, phase: str) -> str:
    """The lines between ``phase() {`` and the closing brace in column zero."""
    match = re.search(rf"^{re.escape(phase)}\(\) \{{\n(.*?)^\}}$", ebuild, re.M | re.S)
    assert match, f"{phase} is not defined in the ebuild"
    return match.group(1)


# -- the shell scripts parse ------------------------------------------------

@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
@pytest.mark.parametrize("path", [EBUILD, SCRIPT], ids=lambda p: p.name)
def test_the_shell_files_parse(path: Path) -> None:
    """A syntax error here surfaces as a failed emerge and nothing else."""
    result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_the_script_is_executable() -> None:
    assert SCRIPT.stat().st_mode & 0o111, f"{SCRIPT.name} needs its execute bit"


def test_no_command_substitution_in_the_heredocs(script: str) -> None:
    """Backticks inside an unquoted heredoc run, they do not print.

    This is not hypothetical: the first draft wrote a comment mentioning
    ``emaint sync -a`` into repos.conf, and the shell obligingly ran it — as
    root, from a script whose whole point is to be predictable.
    """
    offenders = []
    delimiter: str | None = None
    quoted = False
    for number, line in enumerate(script.splitlines(), start=1):
        if delimiter is None:
            opening = re.search(r"<<-?\s*(['\"]?)(\w+)\1", line)
            if opening:
                quoted = bool(opening.group(1))
                delimiter = opening.group(2)
            continue
        if line.strip() == delimiter:
            delimiter = None
            continue
        if not quoted and ("`" in line or "$(" in line):
            offenders.append(f"{number}: {line.strip()}")
    assert delimiter is None, f"unterminated heredoc {delimiter}"
    assert not offenders, "command substitution in an unquoted heredoc:\n" + "\n".join(offenders)


# -- the ebuild and the tree agree ------------------------------------------

def test_every_file_the_ebuild_installs_exists(ebuild: str) -> None:
    """``newexe``/``doins``/``domenu``/``doicon`` all name real paths."""
    referenced = re.findall(r"^\s*(?:newexe|doins|domenu|doicon(?: -s \w+)?)\s+(\S+)", ebuild, re.M)
    assert referenced, "the ebuild installs nothing — the pattern stopped matching"
    for name in referenced:
        assert (ROOT / name).is_file(), f"the ebuild installs {name}, which is not in the tree"


#: ``dodoc README.md`` and ``dodoc -r Docs`` — the ``-r`` names a directory.
_DODOC = re.compile(r"^\s*dodoc(?:\s+-r)?\s+(\S+)", re.M)


def _holds(tree: set[str], name: str) -> bool:
    """Whether *name* is a file in *tree*, or a directory something in it sits under."""
    return name in tree or any(entry.startswith(f"{name}/") for entry in tree)


def _tree_at(tag: str) -> set[str] | None:
    """Every path at *tag*, or ``None`` when git cannot answer.

    Returns None rather than failing: inside an unpacked release tarball there
    is no repository to ask, and the ebuild's own test run is exactly where
    that happens.
    """
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", tag],
        capture_output=True, text=True, check=False,
    )
    return set(result.stdout.splitlines()) if result.returncode == 0 else None


def test_every_document_the_live_ebuild_installs_exists(ebuild: str) -> None:
    """``dodoc`` on a path that is not there is a die, not a warning.

    The sibling check above stops at newexe/doins/domenu/doicon, so a dodoc
    line was installing nothing anybody verified. The live ebuild builds from
    the tip, which in a checkout is this tree; in a release tarball it is the
    snapshot that tarball was cut from, and either way the files have to be
    here.
    """
    referenced = _DODOC.findall(ebuild)
    assert referenced, "the ebuild documents nothing — the pattern stopped matching"
    for name in referenced:
        target = ROOT / name
        assert target.is_file() or target.is_dir(), (
            f"the ebuild installs {name}, which is not in the tree"
        )


def test_a_release_ebuild_documents_only_what_its_own_tarball_holds() -> None:
    """A release builds from its tag, not from whatever main has grown since.

    CHANGELOG.md was written after 1.0.0 and 1.1.0 were tagged, so it is in
    neither tarball; giving their ebuilds a dodoc line for it would have broken
    the build for everyone installing a release, with nothing to catch it.
    """
    checked = 0
    for path in sorted((PACKAGING / "app-portage" / "gentstore").glob("*.ebuild")):
        text = path.read_text()
        if not re.search(r"^SRC_URI=", text, re.M):
            continue
        tag = "v" + path.stem.removeprefix("gentstore-")
        tree = _tree_at(tag)
        if tree is None:
            continue
        checked += 1
        for name in _DODOC.findall(text):
            assert _holds(tree, name), (
                f"{path.name} installs {name}, which is not in the {tag} tarball"
            )
    if not checked:
        pytest.skip("no repository to read the release tags from")


def test_the_ebuild_installs_the_helpers_where_the_code_looks(ebuild: str) -> None:
    """``exeinto`` and ``privilege.INSTALL_DIR`` are one decision in two files."""
    assert f"exeinto {privilege.INSTALL_DIR}" in ebuild
    for name in (privilege.HELPER_NAME, privilege.LAUNCHER_NAME):
        assert f" {name}\n" in ebuild, f"the ebuild never installs {name}"


def test_the_ebuild_inherits_what_it_calls(ebuild: str) -> None:
    """Every eclass function used is one of the eclasses named on the inherit line."""
    inherited = set(re.search(r"^inherit (.+)$", ebuild, re.M).group(1).split())
    needs = {
        "domenu": "desktop", "doicon": "desktop",
        "optfeature": "optfeature",
        "xdg_pkg_postinst": "xdg",
        "python_setup": "distutils-r1", "epytest": "distutils-r1",
        "distutils_enable_tests": "distutils-r1",
        "EGIT_REPO_URI": "git-r3",
    }
    for function, eclass in needs.items():
        if function in ebuild:
            assert eclass in inherited, f"{function} needs {eclass}.eclass on the inherit line"


def test_the_translations_are_built_before_the_wheel(ebuild: str) -> None:
    """After python_compile the catalogues exist but are not in the package.

    PEP 517 builds each wheel from the source tree, so a .qm file generated in
    python_compile_all is produced too late to be installed at all.
    """
    assert "tools/i18n.py compile" in ebuild, "the ebuild never builds the catalogues"
    # In python_prepare_all specifically, not merely somewhere above the tests:
    # python_compile_all also runs before them and is already too late.
    assert "tools/i18n.py compile" in phase_body(ebuild, "python_prepare_all")


def test_the_live_ebuild_carries_no_keywords(ebuild: str) -> None:
    """It clones a moving branch; keywording that would be a lie."""
    assert re.search(r'^KEYWORDS=""$', ebuild, re.M)


# -- the script and the ebuild agree ----------------------------------------

def test_the_script_copies_the_ebuild_that_is_here(script: str) -> None:
    """The atom the script installs is the directory the ebuild actually sits in."""
    atom = re.search(r'^ATOM="(.+)"$', script, re.M).group(1)
    assert EBUILD.parent == PACKAGING / atom
    assert "=${ATOM}-9999 **" in script, "the accepted atom is not built from ATOM"


def test_the_script_accepts_the_version_the_ebuild_provides(script: str) -> None:
    """A live ebuild is masked by default; the accepted atom has to be its own."""
    assert "-9999 **" in script
    assert EBUILD.name.endswith("-9999.ebuild")


def test_local_mode_repoints_the_ebuild_it_copies(script: str, ebuild: str) -> None:
    """--local rewrites the copy in the overlay, not the one in the tree.

    A private upstream fails in the unpack phase, where the message is about
    git credentials and not about the decision that caused it. The rewrite has
    to land on the line the ebuild actually declares.
    """
    assert "--local" in script
    substitution = re.search(r"sed -i \"s\|(\^EGIT_REPO_URI=[^|]*)\|", script)
    assert substitution, "--local no longer rewrites EGIT_REPO_URI"
    assert re.search(substitution.group(1), ebuild, re.M), \
        "the pattern --local substitutes on does not match the ebuild"


def test_the_overlay_uses_thin_manifests(script: str, ebuild: str) -> None:
    """Thin manifests drop the ebuild checksums — not the DIST lines.

    The live ebuild has no ``SRC_URI`` and so needs no Manifest entry at all;
    the release ebuilds do, which
    :func:`test_every_release_ebuild_has_its_dist_entry` checks separately.
    """
    assert "thin-manifests = true" in script
    assert not re.search(r"^SRC_URI=", ebuild, re.M), \
        "the live ebuild grew a SRC_URI; it is supposed to clone, not fetch"


# -- installing without a clone ---------------------------------------------


def test_the_raw_url_and_the_ebuild_name_the_same_repository(
    script: str, ebuild: str
) -> None:
    """Fetched on its own, the script downloads from where the ebuild builds from.

    These are two independent strings for one repository, and they are edited at
    different times — the day they disagree, the one-liner quietly installs an
    ebuild pointing somewhere else.
    """
    raw = re.search(r'RAW_BASE="https://raw\.githubusercontent\.com/([^/]+/[^/"]+)', script)
    assert raw, "the script no longer has a raw.githubusercontent.com base"
    upstream = re.search(r'EGIT_REPO_URI="https://github\.com/([^/]+/[^/".]+)', ebuild)
    assert upstream, "the ebuild no longer clones from github.com"
    assert raw.group(1) == upstream.group(1), (
        f"the script fetches from {raw.group(1)} but the ebuild builds "
        f"{upstream.group(1)}"
    )


def test_running_without_a_clone_is_recognised_rather_than_crashing() -> None:
    """Piped into bash there is no BASH_SOURCE, so there is no tree to read.

    ``--help`` is the one path that reaches the decision without needing root or
    the network, which makes it the way to check the decision was reached.
    """
    piped = subprocess.run(
        ["bash", "-s", "--", "--help"],
        input=SCRIPT.read_text(),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "curl" in piped.stdout, "the piped help does not say how it was invoked"
    # The URL ends in that path too, so it is the *local invocation* that must
    # be absent — a reader who piped the script has no such file to run.
    assert "sudo packaging/make-overlay.sh" not in piped.stdout, (
        "the piped help offers a path that the reader does not have"
    )

    from_a_clone = subprocess.run(
        ["bash", str(SCRIPT), "--help"], capture_output=True, text=True, check=True
    )
    assert "sudo packaging/make-overlay.sh" in from_a_clone.stdout


def test_local_mode_refuses_to_run_without_a_clone() -> None:
    """--local builds from a working tree; fetched on its own there is none.

    Left unguarded it would fall through to the ordinary path and build from the
    remote, which is the one thing --local exists to avoid.
    """
    result = subprocess.run(
        ["bash", "-s", "--", "--local"],
        input=SCRIPT.read_text(),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "no clone" in result.stderr


def test_nothing_is_written_before_the_download_is_checked(script: str) -> None:
    """A 404 page is still a 200 to the shell, so the ebuild is inspected first.

    The guard has to sit between the download and the copy into the overlay; a
    captive portal's login page installed as an ebuild is a poor way to find out.
    """
    body = script[script.index("fetch_sources()") : script.index("remove()")]
    assert "mktemp -d" in body, "the download no longer lands somewhere disposable"
    assert "trap " in body, "the temporary directory is not cleaned up"
    assert re.search(r"grep -q '\^EGIT_REPO_URI=' \"\$\{EBUILD\}\"", body), (
        "what came back from the network is no longer checked for being an ebuild"
    )


# -- the synced overlay ------------------------------------------------------

PUBLISH = PACKAGING / "publish-overlay.sh"


@pytest.fixture(scope="module")
def publish() -> str:
    return PUBLISH.read_text()


def test_the_synced_overlay_and_the_publisher_agree_on_the_branch(
    script: str, publish: str
) -> None:
    """One writes the branch, the other tells Portage to clone it.

    Two independent strings for one branch name: the day they disagree, the
    first sync clones something that is not there.
    """
    told = re.search(r'OVERLAY_BRANCH="([^"]+)"', script)
    written = re.search(r'BRANCH="([^"]+)"', publish)
    assert told and written, "the branch name is no longer a constant in both"
    assert told.group(1) == written.group(1)


def test_the_live_ebuild_is_not_accepted_unless_it_was_asked_for(script: str) -> None:
    """``9999`` outranks every release, so accepting it decides the install.

    This is the whole reason the installer asks. If ``=…-9999 **`` reached
    package.accept_keywords by default, a plain ``emerge app-portage/gentstore``
    would resolve to the git tip for everyone — including people who piped the
    installer somewhere with no terminal and were never offered the choice.
    Verified against Portage's resolver on a stable profile: with that line the
    bare atom gives 9999, without it, 1.0.0.
    """
    # The if/else that writes the accept file, sliced on its own indentation so
    # that an `else` belonging to some inner block cannot be mistaken for it.
    block = re.search(
        r"\n\tif \$\{LIVE\}; then\n(?P<live>.*?)\n\telse\n(?P<default>.*?)\n\tfi\n",
        script,
        re.S,
    )
    assert block, "the accept file is no longer written by one if/else"

    def written(branch: str) -> str:
        """Only the lines that reach the file — the comments explain how to opt
        into the live ebuild and naturally quote the very line under test."""
        return "\n".join(
            line for line in branch.splitlines() if not line.lstrip().startswith("#")
        )

    assert "=${ATOM}-9999 **" in written(block["live"]), \
        "--live no longer accepts the live ebuild"
    assert "=${ATOM}-9999 **" not in written(block["default"]), (
        "the default accept file accepts 9999, which makes it win by default"
    )
    assert "${ATOM} ~amd64" in written(block["default"]), "the release is no longer accepted"


def test_the_choice_is_read_from_the_terminal_not_from_stdin(script: str) -> None:
    """Piped into bash, stdin *is* the script.

    A ``read`` there consumes the script's own remaining lines instead of
    waiting for an answer — the installer would both misread the reply and
    truncate itself.
    """
    assert "read -r reply < /dev/tty" in script, "the prompt no longer reads from the tty"
    assert re.search(r"have_tty\(\)\s*\{\s*\{ : < /dev/tty; \} 2>/dev/null", script), (
        "the tty probe must open the device inside braces, so that a failure to "
        "open is silenced rather than printed"
    )


def test_every_release_ebuild_has_its_dist_entry(ebuild: str) -> None:
    """SRC_URI without a Manifest line is a fetch failure for everybody.

    Thin manifests drop the ebuild checksums, never the DIST lines.
    """
    manifest_path = PACKAGING / "app-portage" / "gentstore" / "Manifest"
    manifest = manifest_path.read_text() if manifest_path.exists() else ""
    for path in sorted((PACKAGING / "app-portage" / "gentstore").glob("*.ebuild")):
        text = path.read_text()
        if not re.search(r"^SRC_URI=", text, re.M):
            continue
        version = path.stem.removeprefix("gentstore-")
        assert f"gentstore-{version}.tar.gz" in manifest, (
            f"{path.name} has SRC_URI but no DIST entry in the Manifest"
        )


def test_the_release_ebuild_does_not_inherit_git_r3(script: str) -> None:
    """A tarball build must not also try to clone: git-r3 would win and the
    version number would stop meaning anything."""
    for path in (PACKAGING / "app-portage" / "gentstore").glob("*.ebuild"):
        text = path.read_text()
        has_src = bool(re.search(r"^SRC_URI=", text, re.M))
        has_git = "git-r3" in text
        assert not (has_src and has_git), f"{path.name} has both SRC_URI and git-r3"
        assert has_src or has_git, f"{path.name} fetches from nowhere"


def test_the_live_ebuild_lands_in_portages_live_rebuild_set(ebuild: str) -> None:
    """``@live-rebuild`` selects on PROPERTIES=live, which git-r3 appends.

    Dropping the inherit to hand-roll the checkout would silently take the
    package out of the one set that rebuilds it.
    """
    assert "git-r3" in ebuild, "the live ebuild no longer inherits git-r3"


# -- which python runs as root ----------------------------------------------

PRIVILEGED_SOURCES = (
    ROOT / "gentstore" / "helper" / "gentstore_helper.py",
    ROOT / "gentstore" / "helper" / "gentstore_launcher.py",
)


@pytest.mark.parametrize("path", PRIVILEGED_SOURCES, ids=lambda p: p.name)
def test_the_privileged_programs_do_not_ask_path_which_python_they_are(
    path: Path,
) -> None:
    """``#!/usr/bin/env python3`` resolves through ``PATH``, and these run as root.

    pkexec sanitises the environment it passes on and the ``sudo`` fallback has
    a secure_path of its own, so this was never the easy hole it looks like. It
    is still one fewer thing between an authentication dialog and the program
    the user agreed to run, and it costs a line.
    """
    first = path.read_text(encoding="utf-8").splitlines()[0]
    assert first == "#!/usr/bin/python3", first


def test_the_live_ebuild_pins_the_interpreter_the_gentoo_way(ebuild: str) -> None:
    """``python_fix_shebang`` is the mechanism, not a hardcoded path.

    It rewrites ``#!/usr/bin/python3`` to the exact interpreter the package was
    built for, so what root executes does not move when somebody runs
    ``eselect python set``. Hardcoding a version here instead would break
    multi-python packaging, which is the thing the eclass exists to get right.
    """
    body = phase_body(ebuild, "python_install_all")
    # Comments in this phase name both functions while explaining them; what is
    # being checked is the order they are called in.
    calls = "\n".join(
        line for line in body.splitlines() if not line.lstrip().startswith("#")
    )

    assert "python_fix_shebang" in calls, "the installed programs keep a generic shebang"
    for name in ("gentstore-helper", "gentstore-launcher"):
        assert name in calls.split("python_fix_shebang", 1)[1], name
    # python_fix_shebang reads EPYTHON, which the all-phase does not set on its own.
    assert calls.index("python_setup") < calls.index("python_fix_shebang")


def test_a_rewritten_shebang_is_not_mistaken_for_an_out_of_date_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half of pinning it: the interface must not then cry stale.

    ``installed_status()`` compares the installed copy with the source. A
    correctly installed copy differs from the source in exactly one line — the
    one the eclass rewrote — and reporting that as "from an older version of
    Gentstore, run sudo make install-system" would send everybody chasing a
    problem that is the install working.
    """
    source = PRIVILEGED_SOURCES[0]
    installed_dir = tmp_path / "libexec"
    installed_dir.mkdir()
    installed = installed_dir / privilege.HELPER_NAME
    body = source.read_text(encoding="utf-8").split("\n", 1)[1]
    installed.write_text(f"#!/usr/bin/python3.12\n{body}", encoding="utf-8")

    monkeypatch.setattr(privilege, "INSTALL_DIR", installed_dir)
    status = privilege.installed_status(privilege.HELPER_NAME, refresh=True)

    assert status.installed
    assert status.is_stale is False

    # A change anywhere else is still a change.
    installed.write_text(f"#!/usr/bin/python3.12\n{body}\n# and one more thing\n", "utf-8")
    assert privilege.installed_status(privilege.HELPER_NAME, refresh=True).is_stale


# -- the polkit policy ------------------------------------------------------

POLICY = ROOT / "data" / "org.gentoo.gentstore.policy"


def test_every_privileged_action_asks_every_time() -> None:
    """No ``auth_admin_keep`` anywhere in the policy.

    What the "keep" form remembers is not "this window may carry on" but "this
    user has authenticated for this action", so for the length of the window
    anything else running as that user reaches the same two programs with no
    dialog of its own. The two programs are narrow on purpose, but narrow is not
    nothing, and a six-step update asking six times is the honest description of
    a six-step update.
    """
    actions = ElementTree.parse(POLICY).getroot().findall("action")
    assert actions, "the policy declares no actions at all"
    for action in actions:
        defaults = action.find("defaults")
        assert defaults is not None, action.get("id")
        granted = {element.text for element in defaults}
        assert granted == {"auth_admin"}, f'{action.get("id")} grants {granted}'


def test_the_policy_names_the_programs_the_code_runs() -> None:
    """The exec path in the policy is what picks the action for a dialog.

    A path that does not exist is not an error anywhere — polkit simply falls
    back to the generic "run a program as another user" wording, and the whole
    point of naming the actions is lost quietly.
    """
    paths = {
        annotation.text
        for annotation in ElementTree.parse(POLICY).getroot().iter("annotate")
        if annotation.get("key") == "org.freedesktop.policykit.exec.path"
    }
    expected = {
        str(privilege.INSTALL_DIR / name)
        for name in (privilege.HELPER_NAME, privilege.LAUNCHER_NAME)
    }
    assert paths == expected


def test_the_policy_points_at_somewhere_that_exists() -> None:
    """The vendor URL is what the dialog's "vendor" link opens."""
    url = ElementTree.parse(POLICY).getroot().findtext("vendor_url")
    assert url is not None and "Gentstore-alpha" not in url, "that repository was renamed"
    assert url == "https://www.gentstore.dev"


# -- the desktop entry and the running application agree --------------------

def desktop_entry() -> dict[str, str]:
    """``[Desktop Entry]`` as a mapping, localised keys and comments dropped."""
    keys = {}
    for line in DESKTOP.read_text().splitlines():
        if "=" in line and not line.startswith("#") and "[" not in line.split("=", 1)[0]:
            name, value = line.split("=", 1)
            keys[name] = value
    return keys


def test_the_entry_is_named_what_the_application_announces() -> None:
    """On Wayland the two are joined by a filename and nothing else.

    There is no WM_CLASS to fall back on: the compositor takes the app_id Qt
    sends, appends ``.desktop``, and looks for that file. Qt builds the app_id
    from ``setDesktopFileName``, so if this constant and this filename ever
    drift the window loses its name and its icon together and nothing else
    breaks — which is how it went unnoticed before 1.3.0, where the app_id was
    left unset and came out as the interpreter's own name.
    """
    assert DESKTOP.is_file(), f"there is no {DESKTOP.name} for the app_id to find"


def test_the_entry_names_an_icon_that_ships() -> None:
    assert desktop_entry()["Icon"] == ICON_NAME
    assert (ROOT / "data" / "icons" / f"{ICON_NAME}.svg").is_file()


def test_the_icon_is_looked_for_where_the_installers_put_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``make install-desktop`` and :func:`app_icon_search_paths` are one path.

    The ebuild's ``doicon -s scalable`` lands in the same place; the Makefile is
    checked here because it spells the directory out and so can drift on its own.
    """
    from gentstore.ui.theme.icons import app_icon_search_paths  # noqa: PLC0415 - needs Qt

    line = re.search(r"^ICONS\s*:=\s*(.+)$", (ROOT / "Makefile").read_text(), re.M)
    assert line, "the Makefile no longer says where the icon goes"
    installed = line.group(1).replace("$(DESTDIR)", "").replace("$(PREFIX)", "/usr")

    monkeypatch.setenv("XDG_DATA_DIRS", "/usr/share")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert Path(installed) / f"{ICON_NAME}.svg" in set(app_icon_search_paths())
