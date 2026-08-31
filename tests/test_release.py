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

"""Cutting a release, kept honest.

Four files state the version number and the release workflow derives everything
else from it. What can be checked here is that they still agree, that the script
which rewrites them actually rewrites all of them, and that the workflow and the
ebuild have not drifted apart on what a tag is called — a disagreement there is a
404 at fetch time for every user at once, and nothing before that would notice.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "release.py"
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
OVERLAY_WORKFLOW = ROOT / ".github" / "workflows" / "overlay.yml"
PUBLISHER = ROOT / "packaging" / "publish-overlay.sh"
EBUILDS = ROOT / "packaging" / "app-portage" / "gentstore"

#: The files the script owns, relative to the tree, and where each one has to be
#: copied to for the script to find it in a fixture.
STATED_IN = ("pyproject.toml", "gentstore/__init__.py", "README.md", "CHANGELOG.md")


def release(*arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT if cwd is None else cwd / "tools" / "release.py"), *arguments],
        capture_output=True,
        text=True,
        cwd=cwd or ROOT,
    )


@pytest.fixture(scope="module")
def workflow() -> str:
    return WORKFLOW.read_text()


#: Written into the copy rather than read out of the tree. Releasing empties
#: [Unreleased] — that is what releasing *is* — so a test that borrowed the real
#: section would be red in precisely the state every release tarball is cut in,
#: which is also where the ebuild runs this suite. 1.1.1 shipped exactly that: a
#: tarball that failed its own tests, and so failed to build under USE=test.
UNRELEASED_BODY = """### Added

- Something worth releasing, so that the bump has notes to move.
"""


def with_unreleased_work(changelog: Path, body: str = UNRELEASED_BODY) -> None:
    """Put *body* in the [Unreleased] section, whatever was there before."""
    text = changelog.read_text()
    start = text.index("## [Unreleased]")
    end = text.index("## [", start + len("## [Unreleased]"))
    changelog.write_text(f"{text[:start]}## [Unreleased]\n\n{body}\n{text[end:]}")


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A copy of just the files a bump touches, plus the script that touches them.

    Enough for the rewrite to run for real rather than against a mock, and cheap
    enough that a failing case can be built by editing one file. The [Unreleased]
    section is set here rather than inherited, so that where the real tree
    happens to sit in the release cycle cannot decide whether these tests pass.
    """
    for name in STATED_IN:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / name, target)
    (tmp_path / "tools").mkdir()
    shutil.copy(SCRIPT, tmp_path / "tools" / "release.py")
    with_unreleased_work(tmp_path / "CHANGELOG.md")
    return tmp_path


# -- the tree states one version --------------------------------------------

def test_every_file_states_the_same_version() -> None:
    """1.1.0 shipped with the README still announcing 1.0.0.

    Nothing was watching, because each of the four is edited on its own. This
    is the check the release workflow runs against a tag before it publishes.
    """
    done = release("check")
    assert done.returncode == 0, done.stderr


def test_the_changelog_has_somewhere_to_write_the_next_release() -> None:
    """``bump`` moves [Unreleased] into a dated section; without the heading
    there is nothing to move, and the notes would have to be reconstructed
    afterwards. Whether anything is *under* it is deliberately not checked: the
    section is empty for as long as a release is the newest thing that happened,
    and that is the state a release tarball is cut in."""
    assert "## [Unreleased]" in (ROOT / "CHANGELOG.md").read_text()


# -- the rewrite ------------------------------------------------------------

def test_a_bump_rewrites_every_place_at_once(tree: Path) -> None:
    """The point of the script: four edits that cannot be made separately."""
    done = release("bump", "9.9.9", "--date", "2026-01-01", cwd=tree)
    assert done.returncode == 0, done.stderr

    assert release("check", "9.9.9", cwd=tree).returncode == 0
    assert 'version = "9.9.9"' in (tree / "pyproject.toml").read_text()
    assert '__version__ = "9.9.9"' in (tree / "gentstore" / "__init__.py").read_text()
    assert "> **Version 9.9.9.**" in (tree / "README.md").read_text()

    changelog = (tree / "CHANGELOG.md").read_text()
    assert "## [9.9.9] — 2026-01-01" in changelog
    assert "## [Unreleased]" in changelog, "the next release needs somewhere to accumulate"
    assert "[9.9.9]: https://github.com/JamJan05/GentStore/compare/" in changelog
    assert re.search(r"^\[Unreleased\]: \S+v9\.9\.9\.\.\.HEAD$", changelog, re.M), \
        "the Unreleased link still compares against the version just released"


def test_the_new_section_takes_the_unreleased_notes_unaltered(tree: Path) -> None:
    """Whatever was written as the work happened is what goes out.

    1.1.0's notes were written from a session's own diff instead and claimed
    "No functional changes" across twenty-one commits.
    """
    before = release("notes", "Unreleased", cwd=tree).stdout
    assert before.strip() == UNRELEASED_BODY.strip(), "the fixture no longer sets the section"
    release("bump", "9.9.9", "--date", "2026-01-01", cwd=tree)
    assert release("notes", "9.9.9", cwd=tree).stdout == before


def test_a_release_with_no_notes_is_refused(tree: Path) -> None:
    """An empty [Unreleased] section means nobody wrote down what changed."""
    with_unreleased_work(tree / "CHANGELOG.md", body="")

    done = release("bump", "9.9.9", cwd=tree)
    assert done.returncode != 0
    assert "empty" in done.stderr


def test_a_bump_that_goes_backwards_is_refused(tree: Path) -> None:
    """Re-releasing a number that is already published, usually as a typo."""
    done = release("bump", "0.0.1", cwd=tree)
    assert done.returncode != 0
    assert "does not come after" in done.stderr


def test_nothing_is_written_when_the_bump_is_refused(tree: Path) -> None:
    """A refusal halfway through would leave the tree stating two versions."""
    before = {name: (tree / name).read_text() for name in STATED_IN}
    assert release("bump", "0.0.1", cwd=tree).returncode != 0
    for name, text in before.items():
        assert (tree / name).read_text() == text, f"{name} was written to anyway"


# -- the workflow and the tree agree ----------------------------------------

def test_the_workflow_only_calls_subcommands_that_exist(workflow: str) -> None:
    """A renamed subcommand would fail in the middle of a release, not before."""
    known = re.findall(r'^\s{4}"(\w+)": do_\w+,$', SCRIPT.read_text(), re.M)
    assert known, "the script's command table stopped being readable"
    called = set(re.findall(r"tools/release\.py (\w+)", workflow))
    assert called, "the workflow no longer calls the release script at all"
    assert called <= set(known), f"the workflow calls {called - set(known)}"


def test_the_workflow_tags_what_the_release_ebuild_fetches(workflow: str) -> None:
    """``SRC_URI`` names a tag by name. Disagree, and every fetch is a 404.

    The ebuild builds the URL from ``${PV}``, so the prefix in front of it is
    the whole contract: the workflow writes ``v1.2.0`` and the ebuild asks for
    ``v${PV}``. Two independent strings for one decision.
    """
    release_ebuilds = [
        path for path in sorted(EBUILDS.glob("*.ebuild"))
        if re.search(r"^SRC_URI=", path.read_text(), re.M)
    ]
    assert release_ebuilds, "there is no release ebuild to check against"
    for path in release_ebuilds:
        assert 'releases/download/v${PV}/${P}.tar.gz' in path.read_text(), \
            f"{path.name} no longer fetches a v-prefixed tag's asset"
    assert 'echo "TAG=v${version}"' in workflow, "the workflow no longer tags with a v prefix"
    assert re.search(r'tags: \["v\[0-9\]', workflow), \
        "the workflow no longer triggers on a v-prefixed tag"


def test_the_workflow_commits_the_ebuild_after_the_tag(workflow: str) -> None:
    """A release ebuild must not be inside its own tarball.

    It carries ``SRC_URI`` and the Manifest entry describing that very tarball
    cannot exist until the tarball does, so an ebuild shipped inside it has
    ``SRC_URI`` and no ``DIST`` line — which
    :func:`tests.test_packaging.test_every_release_ebuild_has_its_dist_entry`
    fails on, during ``emerge``, on the user's machine.
    """
    steps = [
        workflow.index("git tag -a"),
        workflow.index("git archive"),
        workflow.index('cp "${previous}" "${new}"'),
        workflow.index('git commit -m "packaging: the ${VERSION} ebuild'),
    ]
    assert steps == sorted(steps), "the ebuild is no longer written after the tarball is cut"


def test_the_overlay_workflow_watches_where_the_ebuilds_live() -> None:
    """The overlay branch is generated, and drifts the moment nothing regenerates it.

    A release republishes it at the end, which covers the release ebuilds. The
    live one changes between releases and on its own, so a push that touches the
    ebuild directory has to republish too — and a path filter that stops covering
    that directory is a mechanism that stops without saying so. This is not
    hypothetical: the branch had already drifted by a comment in
    gentstore-9999.ebuild before this workflow existed.
    """
    text = OVERLAY_WORKFLOW.read_text()
    block = re.search(r"^    paths:\n((?:      - .*\n)+)", text, re.M)
    assert block, "the overlay workflow no longer filters on paths"
    watched = re.findall(r'- "([^"]+)"', block.group(1))

    ebuilds = EBUILDS.relative_to(ROOT).as_posix()
    assert any(ebuilds.startswith(pattern.removesuffix("/**")) for pattern in watched), \
        f"none of {watched} covers {ebuilds}, where the ebuilds actually are"

    assert PUBLISHER.relative_to(ROOT).as_posix() in watched, \
        "changing the generator no longer republishes what it generates"


def test_both_workflows_republish_through_the_one_script(workflow: str) -> None:
    """Two places force-push the overlay branch; neither writes it itself.

    The branch cannot be assembled twice by two slightly different pieces of
    shell — that is the drift the script exists to prevent, reintroduced one
    level up.
    """
    for text in (workflow, OVERLAY_WORKFLOW.read_text()):
        assert "packaging/publish-overlay.sh --push" in text
        assert "GENTSTORE_OVERLAY_REMOTE" in text, \
            "the push would have no credentials to use"


def test_a_yanked_heading_is_still_a_section_boundary() -> None:
    """Without this the withdrawal is worse than not marking it at all.

    An unrecognised heading is not a boundary, so the release *above* a yanked
    one would quietly absorb its notes — and those notes are what the workflow
    publishes as the next release's description. Checked on a sample rather than
    on the real file, so it keeps testing the parser once 1.1.1 is old news.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    import release as release_module

    sample = (
        "## [Unreleased]\n\n"
        "## [2.0.0] — 2026-01-02\n\n- what 2.0.0 changed\n\n"
        "## [1.9.9] — 2026-01-01 [YANKED]\n\n- what the withdrawn one changed\n"
    )
    found = release_module.sections(sample)
    assert set(found) == {"Unreleased", "2.0.0", "1.9.9"}
    assert found["2.0.0"][0] == "- what 2.0.0 changed", \
        "the withdrawn release's notes leaked into the release above it"
    assert found["1.9.9"][1] == "2026-01-01", "a yanked release still has its date"
    assert release_module.yanked(sample) == {"1.9.9"}


def test_nothing_offers_to_install_a_yanked_release() -> None:
    """A withdrawn release has to be withdrawn from the overlay too.

    Marking it in CHANGELOG.md is the record; it is not the mechanism. As long
    as the ebuild is there Portage can still be asked for that exact version by
    atom, and it would fetch an asset that has been deleted — or, worse, build
    the thing that was withdrawn for being unbuildable. 1.1.1 is the first, and
    the reason this exists.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    import release as release_module

    withdrawn = release_module.yanked((ROOT / "CHANGELOG.md").read_text())
    manifest_path = EBUILDS / "Manifest"
    manifest = manifest_path.read_text() if manifest_path.exists() else ""
    for version in withdrawn:
        assert not (EBUILDS / f"gentstore-{version}.ebuild").exists(), \
            f"{version} is marked [YANKED] but its ebuild is still in the overlay"
        assert f"gentstore-{version}.tar.gz" not in manifest, \
            f"{version} is marked [YANKED] but the Manifest still describes its tarball"
