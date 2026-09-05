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

"""The "Search & install" screen — the first one with real data behind it.

Three things happen here, and they are deliberately kept apart:

* **searching** runs against the in-memory index and must feel instant, so it is
  synchronous and debounced;
* **the version line in each result row** needs a per-package question that the
  index does not answer, so the model asks it lazily while painting;
* **the details panel** asks Portage for everything about one package, which is
  slow enough to belong on a worker thread.

The action buttons run real commands from session S4 on. Each one shows the
exact command line it will run before it runs it, and removing a package always
goes through ``emerge -pv --unmerge`` first, so the list of what would disappear
is on screen before anything does (Docs/04-privileges.md §6).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from functools import partial

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.confedit import BatchPlan, WritePlan
from ...core.install_plan import InstallPlan
from ...core.install_plan import from_output as read_plan
from ...core.masking import Blockage
from ...core.masking import inspect as inspect_blocks
from ...core.packages import (
    Keywording,
    PackageDetails,
    PackageSummary,
    SearchIndex,
    UnknownPackageError,
    Version,
    package_state,
    split_repo_suffix,
)
from ...core.packages import (
    details as load_details,
)
from ...core.useflags import UsePicture
from ...core.useflags import clear_caches as clear_use_caches
from ...core.useflags import picture as load_use
from ...models.packages import PackageListModel
from ...runner import emerge, helper_client
from ...runner.command import CommandSpec
from ..context import AppContext
from ..tasks import run_async
from ..theme import icons
from ..theme import tokens as t
from ..widgets.block_notice import BlockNotice
from ..widgets.chips import Pill
from ..widgets.flow_layout import FlowWidget
from ..widgets.licence_dialog import LicenceDialog
from ..widgets.package_list import PackageListView
from ..widgets.repo_badge import RepoBadge
from ..widgets.required_changes import RequiredChanges
from ..widgets.use_flags_panel import UseFlagsPanel
from .registry import PageSpec
from .split_page import SplitPage

log = logging.getLogger(__name__)

#: How long to wait after the last keystroke before searching. Long enough to
#: skip the intermediate states of a word being typed, short enough to feel live.
_DEBOUNCE_MS = 150

#: Results kept per query. Nobody scrolls past a few hundred, and the cap keeps
#: the lazy per-row lookups bounded.
_RESULT_LIMIT = 500

#: The pseudo-repository the "all" filter pill stands for.
_ALL_REPOS = "*"


def _let_it_shrink(label: QLabel) -> None:
    """Let the layout make *label* narrower than its text would like.

    A ``QLabel`` reports the width of its longest line as a minimum, and inside a
    scroll area that turns into a horizontal scrollbar and clipped buttons. An
    ignored horizontal size policy hands the decision back to the layout; the
    label wraps or elides into whatever it is given.
    """
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)


def _prose_width(widget: QWidget) -> int:
    """Roughly seventy characters at the current interface scale."""
    return max(420, round(widget.fontMetrics().averageCharWidth() * 88))


def _size_text(size: int | None) -> str:
    """Bytes as a compact human-readable string, or an em dash."""
    if size is None:
        return "—"
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GiB"  # pragma: no cover - unreachable


class SearchPage(SplitPage):
    """Package search with a details panel."""

    #: Emitted when the user picks a package, so other screens can follow along.
    package_selected = pyqtSignal(str)

    def __init__(
        self, spec: PageSpec, context: AppContext, parent: QWidget | None = None
    ) -> None:
        super().__init__(spec, context, parent)

        self._repo_filter = _ALL_REPOS
        self._repo_pills: dict[str, Pill] = {}
        #: The repository the version lines are currently narrowed to, so that
        #: rebuilding the provider — and throwing away its cache — happens only
        #: when the answer actually changed.
        self._narrowed_to = ""
        self._hidden_count = 0
        self._result_count = 0
        self._selected_cp: str | None = None
        self._details: PackageDetails | None = None
        self._selected_cpv: str | None = None
        self._version_pills: list[tuple[Pill, str]] = []
        #: What to do once the command now running has finished successfully.
        #: Used for the two-step removal: show the list, then ask.
        self._after_command: Callable[[], None] | None = None
        #: The analysis command line whose result was clean, or ``None``.
        #:
        #: The install gate, and an argv rather than a flag on purpose: it is
        #: compared against the command the analysis *would* build for whatever
        #: is selected now, so choosing another version, another repository or
        #: turning binary packages on closes the gate by simply no longer
        #: matching. Nothing has to remember to clear it.
        self._gate: tuple[str, ...] | None = None
        #: Set while an analysis this screen started is running, so that the
        #: output arriving in the log can be told apart from any other command's.
        self._analysing: tuple[str, ...] | None = None
        #: The same question one step wider: the last command *this screen*
        #: started, whatever it was. Only such a run says anything about the
        #: package on screen, and only such a run may fill the frame below it.
        self._ran: tuple[str, ...] | None = None
        #: The version whose flags are on screen — not necessarily the one the
        #: details panel opened with, since the version picker changes it.
        self._use_cpv: str | None = None
        #: Which panel asked for the write now in flight.
        self._writer: object | None = None

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._run_search)

        self._build_list_pane()
        self._build_detail_pane()

        context.index_ready.connect(self._on_index_ready)
        context.index_progress.connect(self._on_index_progress)
        context.index_failed.connect(self._on_index_failed)
        context.official_only_changed.connect(self._on_official_changed)
        context.command.running_changed.connect(self._on_running_changed)
        context.command.finished.connect(self._on_command_finished)
        context.command.failed.connect(lambda _message: self._forget_pending())

        self.retranslate_ui()

    # ------------------------------------------------------------ building --

    def _build_list_pane(self) -> None:
        header = QFrame()
        header.setObjectName("searchHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(t.SPACE_4, t.SPACE_4, t.SPACE_4, t.SPACE_4)
        header_layout.setSpacing(t.SPACE_3)

        box = QFrame()
        box.setObjectName("searchBox")
        box_layout = QHBoxLayout(box)
        box_layout.setContentsMargins(t.SPACE_3, t.SPACE_2, t.SPACE_3, t.SPACE_2)
        box_layout.setSpacing(t.SPACE_2)

        self._search_icon = QLabel()
        box_layout.addWidget(self._search_icon)

        self._field = _SearchField(box)
        self._field.textChanged.connect(lambda _text: self._debounce.start())
        self._field.returnPressed.connect(self._run_search)
        box_layout.addWidget(self._field, 1)

        self._count = QLabel()
        self._count.setProperty("role", "mono")
        box_layout.addWidget(self._count)
        header_layout.addWidget(box)

        # A wrapping layout, not a row: at 130 % scale "::steam-overlay" alone
        # is a third of the pane, and a horizontal layout would clip it.
        self._filters = FlowWidget(t.SPACE_2)
        header_layout.addWidget(self._filters)

        self.list_layout.addWidget(header)

        self._model = PackageListModel(parent=self)
        self._list = PackageListView()
        self._list.setModel(self._model)
        selection = self._list.selectionModel()
        if selection is not None:
            selection.currentChanged.connect(self._on_row_changed)
        self.list_layout.addWidget(self._list, 1)

        self._notice = QLabel()
        self._notice.setObjectName("hiddenNote")
        self._notice.setWordWrap(True)
        self._notice.setContentsMargins(t.SPACE_3, t.SPACE_3, t.SPACE_3, t.SPACE_3)
        self._notice.hide()
        self.list_layout.addWidget(self._notice)

    def _build_detail_pane(self) -> None:
        self._detail_stack = QStackedWidget()
        self.detail_layout.addWidget(self._detail_stack, 1)

        self._placeholder = QLabel()
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setProperty("role", "caption")
        self._placeholder.setWordWrap(True)
        self._detail_stack.addWidget(self._placeholder)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(t.SPACE_6)

        top = QHBoxLayout()
        top.setSpacing(t.SPACE_6)
        top.setAlignment(Qt.AlignmentFlag.AlignTop)

        identity = QVBoxLayout()
        identity.setSpacing(t.SPACE_3)

        title_row = QHBoxLayout()
        title_row.setSpacing(t.SPACE_3)
        title_row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._atom = QLabel()
        self._atom.setObjectName("packageAtom")
        self._atom.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title_row.addWidget(self._atom)
        self._badge = RepoBadge()
        title_row.addWidget(self._badge)
        self._installed_note = QLabel()
        self._installed_note.setProperty("role", "caption")
        title_row.addWidget(self._installed_note)
        title_row.addStretch(1)
        identity.addLayout(title_row)

        self._description = QLabel()
        self._description.setProperty("role", "lead")
        self._description.setWordWrap(True)
        # The canvas caps the description at about 70 characters; past that a
        # line of prose is tiring to read however much room the window has.
        self._description.setMaximumWidth(_prose_width(self))
        _let_it_shrink(self._description)
        self._description.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        identity.addWidget(self._description)

        self._meta = QLabel()
        self._meta.setProperty("role", "mono")
        self._meta.setWordWrap(True)
        self._meta.setMaximumWidth(_prose_width(self))
        _let_it_shrink(self._meta)
        self._meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        identity.addWidget(self._meta)
        top.addLayout(identity, 1)

        actions = QVBoxLayout()
        actions.setSpacing(t.SPACE_2)
        actions.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        buttons = QHBoxLayout()
        buttons.setSpacing(t.SPACE_2)
        self._btn_pretend = QPushButton()
        self._btn_pretend.clicked.connect(self._on_pretend)
        self._btn_analyse = QPushButton()
        self._btn_analyse.clicked.connect(self._on_analyse)
        self._btn_secondary = QPushButton()
        self._btn_secondary.clicked.connect(self._on_secondary)
        self._btn_primary = QPushButton()
        self._btn_primary.setProperty("variant", "primary")
        self._btn_primary.clicked.connect(self._on_primary)
        for button in (
            self._btn_pretend,
            self._btn_analyse,
            self._btn_secondary,
            self._btn_primary,
        ):
            button.setEnabled(False)
            buttons.addWidget(button)
        actions.addLayout(buttons)

        self._command = QLabel()
        self._command.setProperty("role", "mono")
        self._command.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._command.setWordWrap(True)
        self._command.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        _let_it_shrink(self._command)
        actions.addWidget(self._command)
        top.addLayout(actions)
        layout.addLayout(top)

        versions = QWidget()
        versions_row = QHBoxLayout(versions)
        versions_row.setContentsMargins(0, 0, 0, 0)
        versions_row.setSpacing(t.SPACE_3)
        versions_row.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._versions_label = QLabel()
        self._versions_label.setProperty("role", "section")
        self._versions_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        # Aligned with the first row of pills rather than centred on the block:
        # a package with twenty versions wraps onto four lines, and a label
        # floating in the middle of them reads as a caption for nothing.
        versions_row.addWidget(self._versions_label)
        versions_row.setAlignment(self._versions_label, Qt.AlignmentFlag.AlignTop)
        self._versions = FlowWidget(t.SPACE_2)
        versions_row.addWidget(self._versions, 1)
        layout.addWidget(versions)

        self._block_notice = BlockNotice()
        self._block_notice.write_requested.connect(
            lambda plan: self._on_write_requested(plan, self._block_notice)
        )
        self._block_notice.licence_requested.connect(self._on_licence_requested)
        layout.addWidget(self._block_notice)

        self._required = RequiredChanges()
        self._required.apply_requested.connect(self._on_batch_requested)
        layout.addWidget(self._required)

        self._use_panel = UseFlagsPanel()
        self._use_panel.write_requested.connect(
            lambda plan: self._on_write_requested(plan, self._use_panel)
        )
        layout.addWidget(self._use_panel)

        layout.addStretch(1)
        self._detail_stack.addWidget(content)
        self._detail_stack.setCurrentWidget(self._placeholder)

    # ------------------------------------------------------------ the index --

    def activated(self) -> None:
        """Kick the index off the first time somebody opens the screen."""
        self.context.ensure_index()
        self._field.setFocus()

    def set_query(self, query: str) -> None:
        """Search for *query* right away, skipping the debounce.

        Used by the menu's "Search…" entry and by the screenshot tool; typing
        still goes through the timer.
        """
        self._field.setText(query)
        self._run_search()

    def _on_index_ready(self, index: object) -> None:
        if not isinstance(index, SearchIndex):
            return
        self._rebuild_repo_filters(index)
        self._list.delegate.set_official_repository(self._official_repo_name())
        self._run_search()

    def _on_index_progress(self, done: int, total: int) -> None:
        if total:
            self._count.setText(f"{round(done / total * 100)} %")

    def _on_index_failed(self, error: object) -> None:
        self._count.setText(self.tr("unavailable"))
        self._notice.setText(
            self.tr("Portage could not be read: {error}").format(error=error)
        )
        self._notice.show()

    def _official_repo_name(self) -> str:
        index = self.context.index
        return index.repos[0] if index and index.repos else "gentoo"

    def _rebuild_repo_filters(self, index: SearchIndex) -> None:
        """One pill per configured repository, plus "all"."""
        self._filters.clear()
        self._repo_pills.clear()

        for repo in (_ALL_REPOS, *index.repos):
            pill = Pill()
            pill.set_text(self.tr("all") if repo == _ALL_REPOS else f"::{repo}")
            pill.set_checked(repo == self._repo_filter)
            pill.clicked.connect(lambda r=repo: self._set_repo_filter(r))
            self._repo_pills[repo] = pill
            self._filters.add(pill)

        if self._repo_filter not in self._repo_pills:
            self._set_repo_filter(_ALL_REPOS)

    def _set_repo_filter(self, repo: str) -> None:
        self._repo_filter = repo
        for name, pill in self._repo_pills.items():
            pill.set_checked(name == repo)
        self._run_search()

    def _on_official_changed(self, _enabled: bool, _mode: str) -> None:
        self._run_search()

    def _active_repo(self) -> str:
        """The single repository this screen is currently confined to, or ``""``.

        A repository pill says so outright, and so does a ``::repo`` typed into
        the search box. The toolbar's "only ::gentoo" switch says the same thing
        in its hiding mode — if the overlays are not on the list, their versions
        have no business being in the details panel either.
        """
        if self._repo_filter != _ALL_REPOS:
            return self._repo_filter
        typed = split_repo_suffix(self._field.text().strip())[1]
        if typed:
            return typed
        if self._hides_overlays():
            return self._official_repo_name()
        return ""

    def _apply_repo_narrowing(self) -> None:
        """Point the version lines and the details panel at the chosen repository.

        Both have to move together with the pills. Otherwise a row filtered to
        ``::gentoo`` still advertises the overlay's newer version, and the panel
        still offers versions the chosen repository does not carry — which is
        how two repositories end up fighting over one package.
        """
        repo = self._active_repo()
        if repo == self._narrowed_to:
            return
        self._narrowed_to = repo
        self._model.set_state_provider(
            partial(package_state, repo=repo) if repo else None
        )
        self._reload_package()

    # ---------------------------------------------------------- the search --

    def _run_search(self) -> None:
        self._debounce.stop()
        index = self.context.index
        if index is None:
            return

        query = self._field.text().strip()
        explicit = None if self._repo_filter == _ALL_REPOS else (self._repo_filter,)
        results = index.search(query, repos=explicit, limit=_RESULT_LIMIT)

        # The "only ::gentoo" filter is applied here rather than passed into the
        # search so the screen can say exactly how many packages it swallowed.
        self._hidden_count = 0
        if self._hides_overlays():
            official = self._official_repo_name()
            kept = [item for item in results if official in item.repos]
            self._hidden_count = len(results) - len(kept)
            results = kept

        # The rows carry a repository badge of their own. Left alone it would
        # name the highest-priority repository that has the package, which under
        # a filter is routinely a different one from the panel on the right.
        repo = self._active_repo()
        if repo:
            results = [replace(item, repos=(repo,)) for item in results]

        self._result_count = len(results)
        self._apply_repo_narrowing()
        self._model.set_results(results)
        self._update_counts()
        self._restore_selection(results)

    def _hides_overlays(self) -> bool:
        """Whether the toolbar switch is currently filtering the list.

        Only mode ``hide`` touches the interface. Mode ``mask`` is a real change
        written into Portage, and the packages it hides disappear because
        Portage stops offering them, not because this screen dropped them.
        """
        return self.context.official_only and self.context.official_mode == "hide"

    def _restore_selection(self, results: list[PackageSummary]) -> None:
        """Keep the selected package selected if it survived the new query."""
        row = self._model.row_of(self._selected_cp) if self._selected_cp else -1
        if row >= 0:
            self._list.setCurrentIndex(self._model.index(row))
            return
        if results:
            self._list.setCurrentIndex(self._model.index(0))
        else:
            self._selected_cp = None
            self._details = None
            self._detail_stack.setCurrentWidget(self._placeholder)
        self._update_counts()

    def _on_row_changed(self, current, _previous) -> None:  # noqa: ANN001 - Qt API
        summary = self._model.summary_at(current.row()) if current.isValid() else None
        if summary is None or summary.cp == self._selected_cp:
            return
        self._selected_cp = summary.cp
        self._selected_cpv = None
        self._use_cpv = None
        self._use_panel.set_picture(None)
        self._block_notice.set_blockage(None)
        # What emerge last refused was about the package being left behind.
        self._required.clear()
        self.package_selected.emit(summary.cp)
        run_async(
            load_details, self._on_details, self._on_details_failed,
            summary.cp, repo=self._active_repo(),
        )

    # --------------------------------------------------------- the details --

    def _on_details(self, info: object) -> None:
        if not isinstance(info, PackageDetails):
            return
        # A slower request for a package the user has already navigated away
        # from — or for a repository filter they have since changed — must not
        # overwrite the panel.
        if info.cp != self._selected_cp or info.repo != self._active_repo():
            return
        self._details = info
        self._selected_cpv = info.best_visible or (
            info.versions[-1].cpv if info.versions else None
        )
        self._detail_stack.setCurrentIndex(1)
        self._refresh_details()
        self._load_use_flags()
        self._refresh_blockage()

    def _on_details_failed(self, error: Exception) -> None:
        if isinstance(error, UnknownPackageError):
            log.info("Package vanished before its details could be read: %s", error)
        else:
            log.error("Reading package details failed: %s", error)
        self._details = None
        self._detail_stack.setCurrentWidget(self._placeholder)

    def _refresh_details(self) -> None:
        info = self._details
        if info is None:
            return

        self._atom.setText(info.cp)
        repo = info.repos[0] if info.repos else ""
        self._badge.set_repository(repo, repo == self._official_repo_name())

        if info.installed:
            versions = ", ".join(entry.version for entry in info.installed)
            self._installed_note.setText(
                self.tr("installed: {versions}").format(versions=versions)
            )
        else:
            self._installed_note.setText(self.tr("not installed"))

        self._description.setText(info.description or self.tr("no description"))
        self._meta.setText(self._meta_text(info))
        self._rebuild_version_pills(info)
        self._refresh_actions(info)

    def _meta_text(self, info: PackageDetails) -> str:
        """Homepage, licence, slot and download size on one monospace line.

        The variable names stay in English — they are Portage's own names, and a
        translated ``LICENCJA=`` would not match anything in ``make.conf`` or in
        the handbook (Docs/03-i18n.md).
        """
        parts = []
        if info.homepage:
            parts.append(info.homepage[0])
        if info.license:
            parts.append(f"LICENSE={info.license}")
        version = self._current_version(info)
        if version is not None:
            parts.append(f"SLOT={version.slot_display}")
        parts.append(self.tr("download: {size}").format(size=_size_text(info.download_size)))
        return "   ·   ".join(parts)

    def _current_version(self, info: PackageDetails) -> Version | None:
        if self._selected_cpv:
            return info.version(self._selected_cpv)
        return None

    def _rebuild_version_pills(self, info: PackageDetails) -> None:
        self._versions.clear()
        self._version_pills.clear()

        for version in self._ordered_versions(info):
            pill = Pill()
            pill.set_text(version.version)
            pill.set_suffix(self._version_tag(version))
            pill.set_checked(version.cpv == self._selected_cpv)
            pill.clicked.connect(lambda cpv=version.cpv: self._select_version(cpv))
            self._version_pills.append((pill, version.cpv))
            self._versions.add(pill)

    @staticmethod
    def _ordered_versions(info: PackageDetails) -> list[Version]:
        """Newest release first, live ebuilds last.

        Strict version order would put ``9999`` at the front of nearly every
        package, and a live ebuild is almost never what somebody is looking for.
        """
        released = [v for v in info.versions if v.keywording is not Keywording.LIVE]
        live = [v for v in info.versions if v.keywording is Keywording.LIVE]
        return list(reversed(released)) + list(reversed(live))

    def _version_tag(self, version: Version) -> str:
        """The short word next to a version number in the picker."""
        if version.installed:
            return self.tr("installed")
        if version.keywording is Keywording.LIVE:
            return self.tr("live")
        if version.masking:
            return self.tr("blocked")
        if not version.masking_known:
            return self.tr("unchecked")
        if version.keywording is Keywording.TESTING:
            return self.tr("testing")
        if version.keywording is Keywording.STABLE:
            return self.tr("stable")
        return ""

    def _select_version(self, cpv: str) -> None:
        if cpv == self._selected_cpv:
            return
        self._selected_cpv = cpv
        for pill, pill_cpv in self._version_pills:
            pill.set_checked(pill_cpv == cpv)
        info = self._details
        if info is not None:
            self._meta.setText(self._meta_text(info))
            self._refresh_actions(info)
        # Flags and blocks both belong to a version, not to a package: a new
        # major release routinely gains and loses flags, and one version being
        # masked says nothing about the next.
        self._load_use_flags()
        self._refresh_blockage()

    def _refresh_actions(self, info: PackageDetails) -> None:
        installed = info.is_installed
        self._btn_pretend.setText(self.tr("Pretend"))
        self._btn_analyse.setText(self.tr("Analyse requirements"))
        self._btn_secondary.setText(
            self.tr("Uninstall") if installed else self.tr("Add to @world")
        )
        self._btn_primary.setText(self.tr("Update") if installed else self.tr("Install"))

        for button, spec in (
            (self._btn_pretend, self._pretend_spec(info)),
            (self._btn_analyse, self._analysis_spec(info)),
            (self._btn_secondary, self._secondary_spec(info)),
            (self._btn_primary, self._primary_spec(info)),
        ):
            # Docs/02-ui-design.md §8: a button that runs something says exactly
            # what, before it is pressed.
            button.setToolTip(spec.display if spec is not None else "")
        if not self._gate_is_open():
            self._btn_primary.setToolTip(self._gate_hint())
        self._command.setText(self._primary_spec(info).display)
        self._on_running_changed(self.context.is_running)

    # ------------------------------------------------------------ actions --

    def _pretend_spec(self, info: PackageDetails) -> CommandSpec:
        return emerge.pretend([self._atom_for(info)])

    def _analysis_spec(self, info: PackageDetails) -> CommandSpec:
        """The analysis, built with the options the install button would use.

        Same atom, same ``--getbinpkg``. A plan worked out for one command and
        an install that runs another would be a description of something the
        user never agreed to, and the difference would show up as a refusal
        after the password rather than before it.
        """
        return emerge.analyse(
            [self._atom_for(info)], binaries=self.context.use_binaries
        )

    def _primary_spec(self, info: PackageDetails) -> CommandSpec:
        return emerge.install(
            [self._atom_for(info)], binaries=self.context.use_binaries
        )

    def _secondary_spec(self, info: PackageDetails) -> CommandSpec:
        if info.is_installed:
            return emerge.unmerge_pretend([info.cp])
        return emerge.select([info.cp])

    def _run(self, spec: CommandSpec) -> bool:
        """Start *spec* and remember that this screen is the one that did.

        Every command in the window shares one runner and one log panel, so the
        output arriving when a command ends is not necessarily an answer to
        anything asked here. Clicking "Update @world" in the toolbar while a
        package is on screen used to leave that update's report in this
        package's frame — a conflict from a run about the whole system, shown
        under the name of one package that had nothing to do with it.
        """
        started = self.context.run(spec)
        self._ran = spec.argv if started else None
        return started

    def _on_running_changed(self, running: bool) -> None:
        ready = self._details is not None and not running
        for button in (self._btn_pretend, self._btn_analyse, self._btn_secondary):
            button.setEnabled(ready)
        self._btn_primary.setEnabled(ready and self._gate_is_open())

    def _gate_is_open(self) -> bool:
        """Whether Portage has said, about *this* command, that it can proceed.

        The gate is shut until an analysis of exactly the command the install
        button would run comes back with nothing to write and nothing
        conflicting. It costs a click and several seconds before every install,
        and it buys the one thing this screen could not say before: that the
        build is going to start rather than stop on a keyword four dependencies
        down.
        """
        info = self._details
        return (
            info is not None
            and self._gate is not None
            and self._gate == self._analysis_spec(info).argv
        )

    def _gate_hint(self) -> str:
        return self.tr(
            "Run “Analyse requirements” first — Portage has not confirmed that "
            "this can be built as your system stands."
        )

    def _on_pretend(self) -> None:
        if self._details is not None:
            self._run(self._pretend_spec(self._details))

    def _on_analyse(self) -> None:
        """Ask Portage what it wants changed, all of it, before installing."""
        info = self._details
        if info is None:
            return
        spec = self._analysis_spec(info)
        # Cleared before rather than after: whatever the previous answer was, it
        # describes a moment that has passed, and a gate left open across a run
        # is a gate that is not a gate.
        self._gate = None
        self._btn_primary.setEnabled(False)
        self._analysing = spec.argv if self._run(spec) else None

    def _on_primary(self) -> None:
        """Install or update, after showing the command and asking."""
        info = self._details
        if info is None:
            return
        spec = self._primary_spec(info)
        title = self.tr("Update package") if info.is_installed else self.tr("Install package")
        if self._confirm(title, spec):
            self._run(spec)

    def _on_secondary(self) -> None:
        info = self._details
        if info is None:
            return
        if not info.is_installed:
            spec = emerge.select([info.cp])
            if self._confirm(self.tr("Add to @world"), spec):
                self._run(spec)
            return

        # Removal is two steps on purpose: first the list of what would go,
        # then the question. Nothing disappears before it has been shown.
        cp = info.cp
        self._after_command = lambda: self._confirm_unmerge(cp)
        if not self._run(emerge.unmerge_pretend([cp])):
            self._forget_pending()

    def _confirm_unmerge(self, cp: str) -> None:
        spec = emerge.unmerge([cp])
        answer = QMessageBox.question(
            self,
            self.tr("Uninstall package"),
            self.tr(
                "The log above lists what would be removed.\n\n"
                "Remove {package} now?\n\n{command}"
            ).format(package=cp, command=spec.display),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._run(spec)

    def _confirm(self, title: str, spec: CommandSpec) -> bool:
        answer = QMessageBox.question(
            self,
            title,
            self.tr("This will run:\n\n{command}").format(command=spec.display),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _on_command_finished(self, code: int) -> None:
        pending, self._after_command = self._after_command, None
        if code == 0 and pending is not None:
            pending()
        analysed, self._analysing = self._analysing, None
        ours, self._ran = self._ran, None
        self._absorb_required_changes(analysed, ours)
        # Whatever ran may have installed or removed something.
        self._model.invalidate_states()
        self._reload_package()

    def _absorb_required_changes(
        self, analysed: tuple[str, ...] | None, ours: tuple[str, ...] | None
    ) -> None:
        """Read back what emerge refused to proceed without.

        Deliberately not conditional on the exit code. A run that stops for
        autounmask *always* exits non-zero — that refusal is the whole message,
        and treating a non-zero exit as nothing to read is what left these
        blocks sitting in the terminal pane with no way to act on them.

        It *is* conditional on who asked. *ours* is the command line if this
        screen started the run, and nothing else may fill the frame: one runner
        and one log panel serve the whole window, so "Update @world" from the
        toolbar ends here too, carrying a report about the entire system that
        would otherwise be shown under the name of whichever package happened to
        be selected.

        *analysed* is narrower again — the command line if this was an analysis
        — and it is the only thing that can open the install gate. A plain
        ``--pretend`` run can come back looking every bit as clean and mean
        less: without ``--autounmask`` Portage never mentions a licence (see
        ``runner/emerge.py``), so "it said nothing" would be answering a
        question that was not asked.
        """
        plan: InstallPlan | None = None
        if ours is not None:
            window = self.window()
            output = window.log_view.text() if hasattr(window, "log_view") else ""
            if output:
                try:
                    plan = read_plan(output)
                except Exception:  # pragma: no cover - output we cannot make sense of
                    log.warning("Could not read the emerge output back", exc_info=True)
        self._required.set_plan(plan)

        self._gate = (
            analysed if analysed is not None and plan is not None and plan.is_ready
            else None
        )
        if self._details is not None:
            self._refresh_actions(self._details)

    def _forget_pending(self) -> None:
        self._after_command = None

    def _atom_for(self, info: PackageDetails) -> str:
        """The atom to put in front of the user.

        The ``::repo`` qualifier earns its place twice: when the package exists
        in more than one repository, and when the screen has been narrowed to
        one on purpose. In the second case it is the whole point — the same
        version number can sit in two repositories, and without the qualifier
        Portage picks by repository priority rather than by what is on screen.
        Everywhere else it is noise that nobody would type into a terminal.
        """
        version = self._current_version(info)
        if version is None:
            return f"{info.cp}::{info.repo}" if info.repo else info.cp
        if info.repo or len(info.repos) > 1:
            return version.atom
        return f"={version.cpv}"

    # ----------------------------------------------------------- USE flags --

    def _load_use_flags(self) -> None:
        """Read the flags of the selected version, off the GUI thread.

        Gathering them means reading ``use.local.desc``, which is most of a
        megabyte, so this is never done while somebody is typing — only once a
        package and a version have been chosen.
        """
        info = self._details
        cpv = self._selected_cpv
        if info is None or cpv is None:
            self._use_panel.set_picture(None)
            return

        version = info.version(cpv)
        repo = version.repo if version is not None else ""
        self._use_cpv = cpv
        run_async(load_use, self._on_use_flags, self._on_use_flags_failed, cpv, repo)

    def _on_use_flags(self, result: object) -> None:
        if not isinstance(result, UsePicture):
            return
        # A slower answer for a version the user has moved on from must not
        # replace the flags they are looking at now.
        if result.state.cpv != self._use_cpv:
            return
        self._use_panel.set_picture(result)

    def _on_use_flags_failed(self, error: Exception) -> None:
        log.error("Reading USE flags failed: %s", error)
        self._use_panel.set_picture(None)

    def _on_write_requested(self, plan: object, requester: object) -> None:
        """Send the previewed line to the privileged helper.

        *requester* is the panel that asked, so the report lands under the thing
        the user was looking at rather than somewhere else on the screen.
        """
        if not isinstance(plan, WritePlan) or plan.is_noop:
            return
        self._writer = requester
        tracker = self.context.backups
        requester.set_busy(True)
        run_async(
            helper_client.request,
            self._on_written,
            self._on_write_failed,
            plan.op,
            ensure_backup=tracker.needs_backup(),
            **self.context.backup_options(),
            **plan.as_request(),
        )

    def _on_batch_requested(self, batch: object) -> None:
        """Send one set of lines to the helper as a single operation.

        One request, one backup, one password, for a set the user has just seen
        written out in full. The helper still checks every entry on its own
        side: it reads its request from standard input and is in no position to
        assume what wrote it, and "the user agreed to all of this at once" is a
        fact about this window, not about the bytes arriving there.
        """
        if not isinstance(batch, BatchPlan) or batch.is_empty:
            return
        self._writer = self._required
        self._required.set_busy(True)
        run_async(
            helper_client.request,
            self._on_batch_written,
            self._on_write_failed,
            "append_lines",
            ensure_backup=self.context.backups.needs_backup(),
            **self.context.backup_options(),
            **batch.as_request(),
        )

    def _on_batch_written(self, result: object) -> None:
        """Report what the helper did, then ask Portage the question again.

        The plan that was just applied described the system as it was before it
        was applied, so it is now out of date by construction — and the run that
        replaces it is the only thing that can open the install gate. Portage
        also routinely stops resolving as soon as autounmask finds something,
        which means the second run is where a conflict either disappears or
        turns out to have been real.
        """
        if not getattr(result, "ok", False):
            self._report_write_failure(result)
            return

        data = getattr(result, "data", {}) or {}
        self.context.backups.note(getattr(result, "backup", None))
        self.context.backups_changed.emit()
        self._required.report_success(self._batch_report(data))

        clear_use_caches()
        self.context.reload_portage()
        self._gate = None
        self._reload_package()
        self._on_analyse()

    def _batch_report(self, data: dict) -> str:
        """What actually happened, file by file, in the helper's own words."""
        entries = [item for item in data.get("entries", []) if isinstance(item, dict)]
        written = [item for item in entries if item.get("changed")]
        if not written:
            return self.tr("No change was needed: every line was already there.")

        by_file: dict[str, list[str]] = {}
        for item in written:
            by_file.setdefault(str(item.get("path", "")), []).append(
                str(item.get("line", ""))
            )
        blocks = [
            "{path}\n{lines}".format(
                path=path, lines="\n".join(f"+ {line}" for line in lines)
            )
            for path, lines in by_file.items()
        ]
        skipped = len(entries) - len(written)
        report = self.tr("Added %n line(s):", "", len(written)) + "\n" + "\n\n".join(blocks)
        if skipped:
            report += "\n" + self.tr(
                "%n line(s) were already there and were left alone.", "", skipped
            )
        return report

    def _report_write_failure(self, result: object) -> None:
        requester = self._writer
        if requester is None:
            return
        if getattr(result, "cancelled", False):
            requester.report_failure(self.tr("Cancelled — nothing was written."))
        else:
            requester.report_failure(
                self.tr("Nothing was written: {error}").format(
                    error=getattr(result, "error", "")
                )
            )

    def _on_written(self, result: object) -> None:
        requester = self._writer
        if requester is None:
            return
        plan = requester.plan
        if getattr(result, "ok", False):
            self.context.backups.note(getattr(result, "backup", None))
            self.context.backups_changed.emit()
            requester.report_success(self._write_report(result, plan))
            # Portage has to be asked again: the file it reads just changed.
            clear_use_caches()
            self.context.reload_portage()
            self._reload_package()
        elif getattr(result, "cancelled", False):
            requester.report_failure(self.tr("Cancelled — nothing was written."))
        else:
            requester.report_failure(
                self.tr("Nothing was written: {error}").format(
                    error=getattr(result, "error", "")
                )
            )

    def _write_report(self, result: object, plan: WritePlan | None) -> str:
        """Say exactly what happened, in the helper's own words."""
        data = getattr(result, "data", {}) or {}
        path = data.get("path") or (str(plan.path) if plan else "")
        if not data.get("changed"):
            return self.tr("No change was needed: {detail}").format(
                detail=data.get("detail", "")
            )
        if plan is not None and plan.op == "remove_line":
            return self.tr("Removed the line from {path}.").format(path=path)
        if plan is not None and plan.op == "replace_line":
            return self.tr("Replaced one line in {path} with:\n{line}").format(
                path=path, line=plan.line
            )
        return self.tr("Added to {path}:\n{line}").format(
            path=path, line=data.get("line", plan.line if plan else "")
        )

    def _on_write_failed(self, error: Exception) -> None:
        log.error("Writing to /etc/portage failed: %s", error)
        if self._writer is not None:
            self._writer.report_failure(str(error))

    def _reload_package(self) -> None:
        """Ask Portage about this package again after the configuration changed.

        Unmasking is the case that makes this necessary: the whole point is that
        the version becomes installable, and the screen has to show that rather
        than the state it refused in.
        """
        self._load_use_flags()
        if self._selected_cp:
            run_async(
                load_details, self._on_details, self._on_details_failed,
                self._selected_cp, repo=self._active_repo(),
            )

    # -------------------------------------------------------- the blockage --

    def _refresh_blockage(self) -> None:
        info = self._details
        cpv = self._selected_cpv
        if info is None or cpv is None:
            self._block_notice.set_blockage(None)
            return
        version = info.version(cpv)
        repo = version.repo if version is not None else ""
        run_async(inspect_blocks, self._on_blockage, self._on_blockage_failed, cpv, repo)

    def _on_blockage(self, blockage: object) -> None:
        if not isinstance(blockage, Blockage) or blockage.cpv != self._selected_cpv:
            return
        self._block_notice.set_blockage(blockage)

    def _on_blockage_failed(self, error: Exception) -> None:
        log.error("Reading the masking status failed: %s", error)
        self._block_notice.set_blockage(None)

    def _on_licence_requested(self, name: str) -> None:
        """Put the licence text in front of the user before they accept it."""
        from ...core.licenses import describe, text  # noqa: PLC0415 — needs Portage

        info = self._details
        if info is None:
            return
        dialog = LicenceDialog(describe(name), text(name), info.cp, self)
        if dialog.exec() == LicenceDialog.DialogCode.Accepted:
            self._block_notice.accept_licence(name)

    # ------------------------------------------------------------ counters --

    def _update_counts(self) -> None:
        index = self.context.index
        if index is None:
            self._count.setText(self.tr("loading…"))
        elif not self._field.text().strip():
            self._count.setText(self.tr("%n package(s)", "", len(index)))
        else:
            self._count.setText(self.tr("%n result(s)", "", self._result_count))

        if self._hidden_count:
            self._notice.setText(
                self.tr("%n package(s) outside ::gentoo hidden. Overlays keep syncing.", "",
                        self._hidden_count)
            )
            self._notice.show()
        else:
            self._notice.hide()

        if index is not None and self._result_count == 0:
            self._placeholder.setText(
                self.tr("Nothing matches the query.")
                if self._field.text().strip()
                else self.tr("Type a name, a category or a word from the description.")
            )

    # ---------------------------------------------------------------- i18n --

    def retranslate_ui(self) -> None:
        self._field.setPlaceholderText(self.tr("name, category or description"))
        self._search_icon.setPixmap(
            icons.tinted_pixmap(
                "magnifying-glass", t.NEUTRAL_500,
                max(12, round(self.fontMetrics().height() * 0.85)),
                self.devicePixelRatioF(),
            )
        )
        self._versions_label.setText(self.tr("VERSION"))
        for label in (self._description, self._meta):
            label.setMaximumWidth(_prose_width(self))
        if _ALL_REPOS in self._repo_pills:
            self._repo_pills[_ALL_REPOS].set_text(self.tr("all"))
        self._update_counts()
        if self._details is not None:
            self._refresh_details()
        else:
            self._placeholder.setText(
                self.tr("Type a name, a category or a word from the description.")
            )


class _SearchField(QWidget):
    """A borderless line edit that lives inside the framed search box.

    A plain ``QLineEdit`` would draw its own background and border inside the
    box's, so the styling is disabled here rather than fought with per-widget
    stylesheet overrides at the call site.
    """

    textChanged = pyqtSignal(str)  # noqa: N815 - mirrors QLineEdit
    returnPressed = pyqtSignal()  # noqa: N815 - mirrors QLineEdit

    def __init__(self, parent: QWidget | None = None) -> None:
        from PyQt6.QtWidgets import QLineEdit  # noqa: PLC0415 - local to this shim

        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QLineEdit()
        self._edit.setObjectName("searchInput")
        self._edit.setFrame(False)
        self._edit.setClearButtonEnabled(True)
        self._edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._edit.textChanged.connect(self.textChanged)
        self._edit.returnPressed.connect(self.returnPressed)
        layout.addWidget(self._edit)

    def text(self) -> str:
        return self._edit.text()

    def setText(self, text: str) -> None:  # noqa: N802 - mirrors QLineEdit
        self._edit.setText(text)

    def setPlaceholderText(self, text: str) -> None:  # noqa: N802 - mirrors QLineEdit
        self._edit.setPlaceholderText(text)

    def setFocus(self) -> None:  # noqa: N802 - Qt API
        self._edit.setFocus()
        self._edit.selectAll()
