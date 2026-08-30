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

import pytest

from gentstore.runner import privilege

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging"
EBUILD = PACKAGING / "app-portage" / "gentstore" / "gentstore-9999.ebuild"
SCRIPT = PACKAGING / "make-overlay.sh"


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


def test_the_overlay_needs_no_manifest(script: str, ebuild: str) -> None:
    """Thin manifests plus no SRC_URI: nothing to checksum, nothing to sign."""
    assert "thin-manifests = true" in script
    assert not re.search(r"^SRC_URI=", ebuild, re.M)
