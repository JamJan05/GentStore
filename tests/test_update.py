"""Tests for reading emerge's output, the news, and the security advisories.

Nearly all of this is parsing text that another program printed, so the tests
are mostly samples of that text. The samples are real: they were captured from
this machine, and where a situation could not be produced here — an upgrade on a
fully up-to-date system, a build failure — the line is copied from emerge's
documented format rather than invented.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from gentstore.core import glsa, news
from gentstore.core.emerge_parse import (
    Action,
    find_failure,
    parse_depclean,
    parse_pretend,
    parse_row,
    parse_size,
    parse_use,
)
from gentstore.models.update import format_size

# -- sizes ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0 KiB", 0),
        ("218 KiB", 218 * 1024),
        ("1445 KiB", 1445 * 1024),
        # Portage formats with the locale's thousands separator. The commands
        # are pinned to LC_ALL=C.UTF-8, but a stray one must not break the row.
        ("1 445 KiB", 1445 * 1024),
        ("14 164 KiB", 14164 * 1024),
        ("1,024 MiB", 1024 * 1024**2),
        ("7 MiB", 7 * 1024**2),
    ],
)
def test_sizes_survive_every_separator(text: str, expected: int) -> None:
    assert parse_size(text) == expected


def test_something_that_is_not_a_size_is_not_guessed_at() -> None:
    assert parse_size("USE=\"a b\"") is None


@pytest.mark.parametrize(
    ("size", "expected"), [(None, ""), (0, "0 B"), (1024, "1.0 KiB"), (7262208, "6.9 MiB")]
)
def test_sizes_are_formatted_for_a_column(size, expected) -> None:
    assert format_size(size) == expected


# -- USE flags in the output ------------------------------------------------


def test_the_three_marks_emerge_uses_are_read() -> None:
    flags = parse_use("X* -wayland% (-selinux) lcms")
    by_name = {item.flag: item for item in flags}

    assert by_name["X"].enabled and by_name["X"].changed
    assert not by_name["wayland"].enabled and by_name["wayland"].added
    assert by_name["selinux"].forced
    assert by_name["lcms"].enabled and not by_name["lcms"].is_interesting


def test_only_changed_flags_are_worth_a_column() -> None:
    flags = parse_use("a b* c% -d")
    assert [item.flag for item in flags if item.is_interesting] == ["b", "c"]


def test_an_empty_use_string_gives_no_flags() -> None:
    assert parse_use("") == ()


# -- one row at a time ------------------------------------------------------


def test_a_new_package_is_read_whole() -> None:
    row = parse_row(
        "[ebuild  N     ] media-video/mpv-0.41.0-r2:0/2::gentoo  "
        'USE="X alsa -jack" PYTHON_SINGLE_TARGET="python3_14" 7092 KiB'
    )
    assert row.action is Action.NEW
    assert row.cp == "media-video/mpv"
    assert row.version == "0.41.0-r2"
    assert row.slot == "0/2"
    assert row.repo == "gentoo"
    assert row.size == 7092 * 1024
    assert "PYTHON_SINGLE_TARGET" in row.variables
    assert not row.is_binary


def test_an_upgrade_reports_both_versions() -> None:
    row = parse_row(
        "[ebuild     U  ] www-client/firefox-155.0::gentoo [154.0::gentoo] "
        'USE="X* -wayland%" 78123 KiB'
    )
    assert row.action is Action.UPDATE
    assert row.old_version == "154.0"
    assert row.version_change == "154.0 → 155.0"


def test_a_downgrade_is_not_mistaken_for_an_upgrade() -> None:
    """emerge writes both letters for a downgrade, and D has to win."""
    row = parse_row("[ebuild     UD ] app-x/y-1.0::gentoo [2.0::gentoo] 0 KiB")
    assert row.action is Action.DOWNGRADE
    assert row.version_change == "2.0 → 1.0"


def test_a_binary_package_is_told_apart_from_a_build() -> None:
    row = parse_row('[binary   R    ] sys-apps/portage-3.0.82::gentoo  USE="ipc" 1200 KiB')
    assert row.is_binary
    assert row.action is Action.REBUILD


def test_a_blocker_keeps_the_explanation() -> None:
    row = parse_row(
        '[blocks B      ] <sys-apps/portage-3.0.9 ("<sys-apps/portage-3.0.9" is blocking app-x/y-1)'
    )
    assert row.action is Action.BLOCKED
    assert "is blocking" in row.note


def test_an_uninstall_row_is_recognised() -> None:
    assert parse_row("[uninstall     ] llvm-core/clang-22.1.8::gentoo").action is Action.UNINSTALL


def test_a_line_that_is_not_a_row_is_not_one() -> None:
    assert parse_row("Total: 8 packages (8 new), Size of downloads: 14164 KiB") is None
    assert parse_row("") is None


# -- a whole run ------------------------------------------------------------

REAL_PRETEND = """
These are the packages that would be merged, in order:

Calculating dependencies  ... done!
Dependency resolution took 0.98 s (backtrack: 0/20).

[ebuild  N     ] dev-lang/luajit-2.1.178:2/2.1.178::gentoo  USE="-static-libs" 1069 KiB
[ebuild  N     ] app-i18n/uchardet-0.0.8::gentoo  CPU_FLAGS_X86="sse2" 218 KiB
[binary   R    ] sys-apps/portage-3.0.81.3::gentoo  USE="ipc" 1200 KiB
[nomerge      ] dev-libs/glib-2.88.2::gentoo

Total: 3 packages (2 new, 1 reinstall), Size of downloads: 2487 KiB

 * IMPORTANT: 32 news items need reading for repository 'gentoo'.
"""


def test_a_whole_pretend_run_is_read() -> None:
    preview = parse_pretend(REAL_PRETEND)
    assert len(preview.rows) == 4
    assert len(preview.merges) == 3, "nomerge rows are context, not work"
    assert preview.total == 3
    assert preview.download_size == 2487 * 1024
    assert preview.binary_count == 1
    assert preview.count(Action.NEW) == 2


def test_an_empty_update_is_recognised_as_such() -> None:
    preview = parse_pretend(
        "\nTotal: 0 packages, Size of downloads: 0 KiB\n"
    )
    assert preview.is_empty
    assert preview.total == 0


REFUSED = """
The following USE changes are necessary to proceed:
 (see "package.use" in the portage(5) man page for more details)
# required by media-video/mpv-0.41.0
>=media-libs/libplacebo-7.349.0 vulkan

!!! The following updates have been skipped due to unsatisfied dependencies:
"""


def test_a_run_that_wants_configuration_changes_says_so() -> None:
    preview = parse_pretend(REFUSED)
    assert preview.needs_configuration
    change = preview.required_changes[0]
    assert change.heading.startswith("The following USE changes")
    assert any("libplacebo" in line for line in change.lines)
    assert preview.problems


# -- the lines emerge asks for ----------------------------------------------

#: Captured on this machine: sci-ml/lmstudio-bin needs squashfs-tools built
#: with zstd, and says so only after the licence and keyword were accepted.
DEPENDENCY_USE = """
[ebuild  N     ] sys-fs/squashfs-tools-4.7.5::gentoo  USE="xattr zstd -debug" 403 KiB
[ebuild  N    ~] sci-ml/lmstudio-bin-0.4.23::overlay-nuda  USE="-cuda" 986657 KiB

Total: 2 packages (2 new), Size of downloads: 987060 KiB

The following USE changes are necessary to proceed:
 (see "package.use" in the portage(5) man page for more details)
# required by sci-ml/lmstudio-bin-0.4.23::overlay-nuda
# required by =sci-ml/lmstudio-bin-0.4.23::overlay-nuda (argument)
>=sys-fs/squashfs-tools-4.7.5 zstd

Use --autounmask-write to write changes to config files (honoring
CONFIG_PROTECT).
"""


def test_a_required_change_becomes_a_line_somebody_can_write() -> None:
    """Heading to file, line to atom and tokens, comments to the reason."""
    change = parse_pretend(DEPENDENCY_USE).required_changes[0]
    assert change.file == "package.use"

    entry = change.entries[0]
    assert entry.atom == ">=sys-fs/squashfs-tools-4.7.5"
    assert entry.tokens == ("zstd",)
    assert entry.line == ">=sys-fs/squashfs-tools-4.7.5 zstd"
    # The demand comes from a package the user never asked about by name, so
    # carrying the "why" across is most of the value.
    assert any("lmstudio" in reason for reason in entry.required_by)


#: The same shape for the other three files. These lines start with "=", which
#: is the point: a licence or keyword entry never begins with ">".
OTHER_FILES = """
The following keyword changes are necessary to proceed:
 (see "package.accept_keywords" in the portage(5) man page for more details)
# required by @world
=app-misc/foo-1.2 ~amd64

The following license changes are necessary to proceed:
 (see "package.license" in the portage(5) man page for more details)
# required by =app-misc/foo-1.2 (argument)
=app-misc/foo-1.2 SOME-EULA

The following mask changes are necessary to proceed:
 (see "package.unmask" in the portage(5) man page for more details)
# required by @world
=app-misc/foo-1.2
"""


def test_a_change_line_is_kept_whatever_operator_it_starts_with() -> None:
    """The block ends at the blank line, not at an unfamiliar first character.

    Collecting by prefix kept ">=" lines and dropped every other one, so the
    licence and keyword entries — the two most often asked for — were parsed
    down to their comments and the user was shown a demand with no line in it.
    """
    changes = parse_pretend(OTHER_FILES).required_changes
    assert [c.file for c in changes] == [
        "package.accept_keywords",
        "package.license",
        "package.unmask",
    ]
    assert [c.entries[0].line for c in changes] == [
        "=app-misc/foo-1.2 ~amd64",
        "=app-misc/foo-1.2 SOME-EULA",
        "=app-misc/foo-1.2",
    ]


def test_a_required_use_conflict_is_not_offered_as_a_line() -> None:
    """There is no line in /etc/portage that settles REQUIRED_USE.

    It arrives in the same shape as the others and has to be turned away here,
    or the interface would offer a write that could not possibly help.
    """
    text = """
The following REQUIRED_USE flag constraints are unsatisfied:
  media-video/mpv-0.41.0: vulkan? ( egl )
"""
    change = parse_pretend(text).required_changes[0]
    assert change.file == ""
    assert change.entries == ()


# -- depclean ---------------------------------------------------------------

REAL_DEPCLEAN = """
 llvm-core/clang
    selected: 22.1.8
   protected: none
     omitted: none

All selected packages: =llvm-core/clang-22.1.8 =dev-lang/go-bootstrap-1.24.6

>>> 'Selected' packages are slated for removal.

Packages installed:   1022
Packages in world:    29
Required packages:    1006
Number to remove:     2
"""


def test_depclean_is_read_from_the_authoritative_line() -> None:
    result = parse_depclean(REAL_DEPCLEAN)
    assert result.atoms == ("=llvm-core/clang-22.1.8", "=dev-lang/go-bootstrap-1.24.6")
    assert result.to_remove == 2
    assert result.installed == 1022
    assert result.required == 1006


def test_a_depclean_with_nothing_to_do_is_empty() -> None:
    assert parse_depclean("Number to remove:     0\n").is_empty


# -- failures ---------------------------------------------------------------

FAILED_BUILD = """
>>> Compiling source in /var/tmp/portage/app-x/y-1.0/work/y-1.0 ...
make: *** [Makefile:12: all] Error 1
 * ERROR: app-x/y-1.0::gentoo failed (compile phase):
 *   emake failed
 *
 * Call stack:
 *   ebuild.sh, line 136:  Called src_compile
 *
 * The complete build log is located at '/var/tmp/portage/app-x/y-1.0/temp/build.log'.
"""


def test_a_build_failure_names_the_package_and_the_log() -> None:
    failure = find_failure(FAILED_BUILD)
    assert failure is not None
    assert failure.package == "app-x/y-1.0"
    assert failure.log_path == "/var/tmp/portage/app-x/y-1.0/temp/build.log"
    assert any("emake failed" in line for line in failure.excerpt)


@pytest.mark.parametrize(
    ("text", "hint"),
    [
        ("The following USE changes are necessary to proceed:", "use-change"),
        ("The following keyword changes are necessary to proceed:", "keyword-change"),
        ("The following license changes are necessary to proceed:", "licence-change"),
        ("Multiple package instances within a single package slot", "slot-conflict"),
        ("[blocks B      ] app-x/y", "blocked"),
        ("emerge: there are no ebuilds to satisfy \"app-x/y\".", "missing-dependency"),
        ("No space left on device", "out-of-space"),
    ],
)
def test_common_refusals_get_a_suggestion(text: str, hint: str) -> None:
    failure = find_failure(text)
    assert failure is not None
    assert failure.hint == hint


def test_ordinary_output_is_not_reported_as_a_failure() -> None:
    assert find_failure(REAL_PRETEND) is None


# -- news -------------------------------------------------------------------

NEWS_ITEM = """Title: Dracut changed default for hostonly_cmdline
Author: Sam James <sam@gentoo.org>
Posted: 2026-05-08
Revision: 1
News-Item-Format: 2.0
Display-If-Installed: >=sys-kernel/dracut-111

Dracut has changed the default value of the hostonly_cmdline setting.

You may need to regenerate your initramfs.
"""


@pytest.fixture
def item(tmp_path: Path):
    path = tmp_path / "item.en.txt"
    path.write_text(NEWS_ITEM, encoding="utf-8")
    return news.parse_item(path, "2026-05-08-dracut", "gentoo")


def test_a_news_item_is_read_headers_and_all(item) -> None:
    assert item.title == "Dracut changed default for hostonly_cmdline"
    assert item.author.startswith("Sam James")
    assert item.posted == date(2026, 5, 8)
    assert item.if_installed == (">=sys-kernel/dracut-111",)
    assert item.body.startswith("Dracut has changed")


def test_the_first_paragraph_is_the_summary(item) -> None:
    assert item.summary == "Dracut has changed the default value of the hostonly_cmdline setting."


def test_an_item_with_a_display_if_header_is_targeted(item) -> None:
    assert item.is_targeted


def test_an_item_with_no_display_if_headers_is_for_everyone(tmp_path: Path) -> None:
    path = tmp_path / "general.en.txt"
    path.write_text("Title: Something\nPosted: 2026-01-01\n\nBody.\n", encoding="utf-8")
    assert not news.parse_item(path, "x", "gentoo").is_targeted


def test_the_unread_list_is_read_from_portages_own_file(tmp_path: Path) -> None:
    (tmp_path / "news-gentoo.unread").write_text("a\n\nb\n", encoding="utf-8")
    assert news.unread_ids("gentoo", tmp_path) == frozenset({"a", "b"})


def test_no_unread_file_means_nothing_unread(tmp_path: Path) -> None:
    assert news.unread_ids("gentoo", tmp_path) == frozenset()


# -- security advisories ----------------------------------------------------

GLSA_OUTPUT = """
[A] means this GLSA was marked as applied (injected),
[U] means the system is not affected and
[N] indicates that the system might be affected.

200311-03 [U] HylaFAX: Remote code exploit in hylafax ( net-misc/hylafax )
202501-01 [N] Firefox: Multiple vulnerabilities ( www-client/firefox www-client/firefox-bin )
200312-01 [A] rsync.gentoo.org: rotation server compromised ()
"""


def test_advisories_are_read_with_their_packages() -> None:
    report = glsa.parse(GLSA_OUTPUT)
    assert len(report.advisories) == 3
    affected = report.affected
    assert len(affected) == 1
    assert affected[0].identifier == "202501-01"
    assert affected[0].packages == ("www-client/firefox", "www-client/firefox-bin")
    assert affected[0].url.endswith("/202501-01")


def test_a_system_with_an_advisory_against_it_is_not_clean() -> None:
    assert not glsa.parse(GLSA_OUTPUT).is_clean


def test_glsa_check_saying_so_outright_is_believed() -> None:
    report = glsa.parse("This system is not affected by any of the listed GLSAs\n")
    assert report.is_clean
    assert report.declared_clean


def test_colour_escapes_do_not_confuse_the_parser() -> None:
    coloured = "\x1b[31;01m202501-01\x1b[39;49;00m [N] Title ( app-x/y )"
    report = glsa.parse(coloured)
    assert report.advisories[0].identifier == "202501-01"


# -- against the real system ------------------------------------------------


def test_the_machines_own_news_reads(tmp_path: Path) -> None:
    from gentstore.core.portage_env import PortageUnavailableError, env

    try:
        environment = env()
    except PortageUnavailableError as exc:  # pragma: no cover - non-Gentoo host
        pytest.skip(f"no usable Portage installation: {exc}")

    items = news.load(environment)
    if not items:  # pragma: no cover - a repository without news
        pytest.skip("no news items on this machine")
    assert all(item.title for item in items)
    assert all(item.repo in environment.repo_names for item in items)
    # Relevance filtering has to actually filter, or it is not doing anything.
    assert len(items) < len(news.load(environment, only_relevant=False))
