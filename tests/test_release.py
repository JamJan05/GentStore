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


def test_every_version_a_file_states_is_one_the_script_rewrites() -> None:
    """A second mention added by hand is one the next release will not move.

    The README grew exactly that: the installer transcript quoted 1.0.0 long
    after 1.0.0 stopped being the release, because only the claim above it was
    ever rewritten. Any X.Y.Z in a file the script owns has to be one of the
    mentions it knows about.

    Every number, not only today's. Filtering to ``current()`` made this test
    blind to the very failure it cites: the stale ``1.0.0`` in the README was
    not the current version — that was the whole problem with it — so the loop
    skipped it and the test stayed green with the bug in front of it. It only
    ever fired inside the window where a drifted mention still happened to equal
    the current number, and one bump closes that window for good.

    The cost is that a deliberate historical citation ("changed in 1.1.0") in one
    of these three files now stops this test. That is the intended shape: such a
    line either needs a pattern of its own, or it belongs in CHANGELOG.md, which
    this script does not own. Both are decisions worth stopping for.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    import release as release_module

    for path, patterns in release_module.VERSION_IN.items():
        body = path.read_text()
        # The spans the patterns cover, so the check is exact rather than "near".
        owned = [m.span() for pattern in patterns for m in pattern.finditer(body)]
        for match in re.finditer(r"\b\d+\.\d+\.\d+\b", body):
            assert any(start <= match.start() < end for start, end in owned), (
                f"{path.relative_to(ROOT)}:{body[:match.start()].count(chr(10)) + 1} "
                f"states {match.group()} where nothing rewrites it"
            )


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
    # Asked of the fixture rather than written down. `\b1\.1\.\d\b` was the
    # assertion below, and on 1.2.x it would match nothing in the copied README
    # whatever the bump did — a guard that stops guarding without saying so.
    replaced = release("current", cwd=tree).stdout.strip()
    done = release("bump", "9.9.9", "--date", "2026-01-01", cwd=tree)
    assert done.returncode == 0, done.stderr

    assert release("check", "9.9.9", cwd=tree).returncode == 0
    assert 'version = "9.9.9"' in (tree / "pyproject.toml").read_text()
    assert '__version__ = "9.9.9"' in (tree / "gentstore" / "__init__.py").read_text()

    # The README states it twice — once as a claim, once inside the installer
    # transcript it quotes — and a file that moves one and not the other
    # contradicts itself in public.
    readme = (tree / "README.md").read_text()
    assert "> **Version 9.9.9.**" in readme
    assert "  1) 9.9.9 — the release." in readme
    assert replaced not in readme, f"{replaced}, which this bump replaced, is still quoted"

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


def test_nothing_is_written_when_a_pattern_stops_matching(tree: Path) -> None:
    """The refusal that used to arrive after three of the four files were written.

    Every other refusal happens before anything is touched. This one could not:
    the loop wrote each file as it finished it, so a mention that had been
    reworded out from under its pattern refused only when the loop reached it —
    with pyproject.toml, __init__.py and the changelog already rewritten, and the
    tree therefore stating two different versions at once. Which is the exact
    state the test above says must never happen, reached by the one door it did
    not cover.
    """
    readme = tree / "README.md"
    readme.write_text(
        readme.read_text().replace(" — the release.", " - the release (reworded)."),
        encoding="utf-8",
    )
    before = {name: (tree / name).read_text() for name in STATED_IN}

    done = release("bump", "9.9.9", "--date", "2026-01-01", cwd=tree)
    assert done.returncode != 0
    # And it says which of the README's two mentions drifted, not merely that
    # the README did: with two patterns on one file, "README.md" alone leaves
    # the reader to work out which of them to go and look at.
    assert "mention 2" in done.stderr, done.stderr

    for name, text in before.items():
        assert (tree / name).read_text() == text, f"{name} was written to anyway"


def test_a_version_stated_twice_in_one_form_moves_both_times(tree: Path) -> None:
    """1.1.2 fixed two *different* forms. One form used twice was still broken.

    ``search`` and ``count=1`` stop at the first match, so a second copy of a
    sentence the script already knows how to rewrite — a duplicated install
    transcript, a translated section — went stale exactly the way 1.0.0 did in
    the README, and ``check`` read only the first one and pronounced the file
    consistent.
    """
    readme = tree / "README.md"
    quoted = "  1) 1.1.2 — the release."
    body = readme.read_text()
    assert quoted in body, "the fixture no longer holds the mention this is about"
    readme.write_text(f"{body}\n\n{quoted}\n", encoding="utf-8")

    assert release("bump", "9.9.9", "--date", "2026-01-01", cwd=tree).returncode == 0
    after = readme.read_text()
    assert after.count("1) 9.9.9 — the release.") == 2
    assert "1.1.2" not in after

    # And a check run over a file where only one of them moved has to say so.
    readme.write_text(after.replace("9.9.9 — the release.", "1.1.2 — the release.", 1))
    refused = release("check", "9.9.9", cwd=tree)
    assert refused.returncode != 0
    assert "occurrence 1" in refused.stderr, refused.stderr


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


def test_every_ref_the_changelog_links_to_still_exists() -> None:
    """Deleting a tag breaks every link that compares against it.

    Withdrawing 1.1.1 took its tag with it, and left two dead links behind: its
    own, and 1.1.2's, which compared *from* it. One was noticed and the other
    was not, which is the argument for asking git rather than reading.
    """
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("no repository to resolve the refs against")

    text = (ROOT / "CHANGELOG.md").read_text()
    definitions = re.findall(r"^\[[^\]]+\]: \S+$", text, re.M)
    refs = re.findall(r"^\[[^\]]+\]: \S+/(?:compare|commit)/(\S+)$", text, re.M)
    # Every definition has to be understood, or this checks whatever it happened
    # to parse and passes. The first draft matched only the two links with no
    # dots in their ref, and was green with a dead tag in front of it.
    assert definitions and len(refs) == len(definitions), \
        f"{len(definitions) - len(refs)} link definitions the pattern does not understand"
    # "a...b" is two refs; "HEAD" always resolves and so says nothing.
    named = {part for ref in refs for part in ref.split("...")} - {"HEAD"}
    for ref in sorted(named):
        resolved = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
            capture_output=True, text=True, check=False,
        )
        assert resolved.returncode == 0, f"CHANGELOG.md links to {ref}, which is not in this repo"
