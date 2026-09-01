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

"""The "Repositories" screen: what is configured, and what could be.

One list on the left with two tabs, because the two questions are asked at
different times and want the same shape of answer. **Configured** is what this
system uses; picking one shows the ``repos.conf`` section that defines it — as
written, rather than summarised, since that file is what somebody would go and
read — and what it brings with it, the packages that come from that repository
and nowhere else. **Available** is the rest of Gentoo's published catalogue,
four hundred-odd of them; picking one shows who runs it and what enabling it
would run. One search box serves whichever tab is open.

Everything that changes the system goes out as a visible command in the log
(``eselect repository …``, ``emaint sync -r …``) except masking a repository,
which is a line in ``/etc/portage/package.mask`` and so goes through the same
preview → write → report as everything else in that directory.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...core import overlays, repos
from ...core.confedit import WritePlan
from ...core.overlays import Catalogue, CatalogueEntry
from ...core.packages import SearchIndex
from ...core.repos import RepositoryInfo
from ...runner import eselect, helper_client
from ..context import AppContext
from ..i18n import untranslated
from ..tasks import run_async
from ..theme import icons
from ..theme import tokens as t
from ..widgets.add_overlay_dialog import AddOverlayDialog
from ..widgets.chips import Pill
from ..widgets.clickable_label import ClickableLabel
from ..widgets.write_preview import WritePreview
from .registry import PageSpec
from .split_page import SplitPage

log = logging.getLogger(__name__)

#: The list side is wider here than on the package screen: repository names and
#: their sync dates do not shorten (Docs/02-ui-design.md §4).
LIST_WIDTH = 512

#: Catalogue rows built at once. Enough that a short catalogue is simply the
#: list and nothing has to be typed at all; four hundred-odd of them is what the
#: search box is for.
_RESULT_LIMIT = 50

#: Packages listed under a repository before the screen stops and points at the
#: package screen, which is built for exactly this and has the filters for it.
_PACKAGE_LIMIT = 40


class _ConfiguredRow(QFrame):
    """One repository this system uses."""

    def __init__(self, page: ReposPage, info: RepositoryInfo, masked: bool) -> None:
        super().__init__(page)
        self.setObjectName("repoRow")
        self._page = page
        self.info = info

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, t.SPACE_3)
        layout.setSpacing(t.SPACE_1)

        top = QHBoxLayout()
        top.setSpacing(t.SPACE_3)
        self._name = QLabel(f"::{info.name}")
        self._name.setObjectName("repoRowName")
        top.addWidget(self._name)

        # No repository badge here: the row already begins with "::guru", and a
        # chip saying the same word twice is noise. What the badge is for on the
        # package screen — official or not — is spelled out instead.
        self._kind = QLabel()
        self._kind.setObjectName("repoQuality")
        self._kind.setProperty("official", "yes" if info.is_official else "no")
        top.addWidget(self._kind)

        self._state = QLabel()
        self._state.setProperty("role", "caption")
        self._state.setProperty("state", "warn" if masked else "")
        top.addWidget(self._state)
        top.addStretch(1)
        layout.addLayout(top)

        self._meta = QLabel()
        self._meta.setProperty("role", "mono")
        layout.addWidget(self._meta)

        self._masked = masked
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retranslate_ui()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802, ANN001 - Qt API
        # The whole row, not just the name: the row is what hover highlights,
        # so the row is what a click has to mean.
        self._page.select(self.info.name)
        super().mouseReleaseEvent(event)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "yes" if selected else "no")
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)

    def retranslate_ui(self) -> None:
        info = self.info
        self._kind.setText(
            self.tr("main repository") if info.is_official else self.tr("overlay")
        )
        self._state.setText(self.tr("hidden from Portage") if self._masked else "")
        count = (
            self.tr("%n package(s)", "", info.package_count)
            if info.package_count is not None
            else ""
        )
        when = (
            info.last_sync.strftime("%Y-%m-%d %H:%M")
            if info.last_sync
            else self.tr("never synchronised")
        )
        priority = "" if info.priority is None else f"prio {info.priority}"
        self._meta.setText("   ·   ".join(part for part in (count, when, priority) if part))


class _CatalogueRow(QFrame):
    """One repository from the published list that is not configured here."""

    def __init__(self, page: ReposPage, entry: CatalogueEntry) -> None:
        super().__init__(page)
        self.setObjectName("catalogueRow")
        self._page = page
        self.entry = entry

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, t.SPACE_3)
        layout.setSpacing(t.SPACE_1)

        top = QHBoxLayout()
        top.setSpacing(t.SPACE_3)
        name = QLabel(f"::{entry.name}")
        name.setObjectName("repoRowName")
        top.addWidget(name)

        self._quality = QLabel()
        self._quality.setObjectName("repoQuality")
        self._quality.setProperty("official", "yes" if entry.is_official else "no")
        top.addWidget(self._quality)
        top.addStretch(1)
        layout.addLayout(top)

        description = QLabel(entry.description)
        description.setProperty("role", "caption")
        description.setWordWrap(True)
        layout.addWidget(description)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retranslate_ui()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802, ANN001 - Qt API
        self._page.select_offer(self.entry)
        super().mouseReleaseEvent(event)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "yes" if selected else "no")
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)

    def retranslate_ui(self) -> None:
        entry = self.entry
        official = self.tr("official") if entry.is_official else self.tr("unofficial")
        self._quality.setText(f"{official} · {entry.quality}" if entry.quality else official)


class ReposPage(SplitPage):
    """Configured repositories and the catalogue, as two tabs of one list."""

    #: The two tabs, as they are stored in :attr:`_tab`.
    CONFIGURED = "configured"
    AVAILABLE = "available"

    def __init__(
        self, spec: PageSpec, context: AppContext, parent: QWidget | None = None
    ) -> None:
        super().__init__(spec, context, parent)
        self.set_list_width(LIST_WIDTH)

        self._configured: tuple[RepositoryInfo, ...] = ()
        self._catalogue = Catalogue()
        self._rows: dict[str, _ConfiguredRow] = {}
        self._masked: frozenset[str] = frozenset()
        self._offer_rows: dict[str, _CatalogueRow] = {}
        self._selected: str | None = None
        self._offered: CatalogueEntry | None = None
        self._tab = self.CONFIGURED
        self._plan: WritePlan | None = None
        self._after_command = None

        self._build_list_pane()
        self._build_detail_pane()

        context.command.finished.connect(self._on_command_finished)
        context.command.running_changed.connect(self._on_running_changed)
        context.index_ready.connect(self._on_index_ready)
        self.retranslate_ui()

    # ------------------------------------------------------------ building --

    def _build_list_pane(self) -> None:
        header = QFrame()
        header.setObjectName("searchHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(t.SPACE_4, t.SPACE_4, t.SPACE_4, t.SPACE_4)
        header_layout.setSpacing(t.SPACE_3)

        tabs = QHBoxLayout()
        tabs.setSpacing(t.SPACE_2)
        self._tab_configured = Pill()
        self._tab_configured.set_checked(True)
        self._tab_configured.clicked.connect(lambda: self.set_tab(self.CONFIGURED))
        tabs.addWidget(self._tab_configured)
        self._tab_available = Pill()
        self._tab_available.clicked.connect(lambda: self.set_tab(self.AVAILABLE))
        tabs.addWidget(self._tab_available)
        tabs.addStretch(1)
        header_layout.addLayout(tabs)

        # The same search box as the package screen, down to the icon: it is
        # the one control on both screens that means "type here".
        box = QFrame()
        box.setObjectName("searchBox")
        box_layout = QHBoxLayout(box)
        box_layout.setContentsMargins(t.SPACE_3, t.SPACE_2, t.SPACE_3, t.SPACE_2)
        box_layout.setSpacing(t.SPACE_2)
        self._search_icon = QLabel()
        box_layout.addWidget(self._search_icon)
        self._search = QLineEdit()
        self._search.setObjectName("searchInput")
        self._search.textChanged.connect(lambda _text: self._rebuild_visible_tab())
        box_layout.addWidget(self._search, 1)
        header_layout.addWidget(box)

        actions = QHBoxLayout()
        actions.setSpacing(t.SPACE_2)
        self._sync_all = QPushButton()
        self._sync_all.clicked.connect(lambda: self._run(eselect.sync_all()))
        actions.addWidget(self._sync_all)
        self._refresh = QPushButton()
        self._refresh.clicked.connect(lambda: self._run(eselect.list_repositories()))
        actions.addWidget(self._refresh)
        self._add = QPushButton()
        self._add.setProperty("variant", "danger")
        self._add.clicked.connect(self._on_add)
        actions.addWidget(self._add)
        actions.addStretch(1)
        header_layout.addLayout(actions)
        self.list_layout.addWidget(header)

        # Four configured repositories fit; four hundred and fifty-nine do not,
        # and the list pane of a SplitPage does not scroll on its own.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("repoList")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._lists = QStackedWidget()
        self._rows_holder, self._rows_layout = self._list_holder()
        self._lists.addWidget(self._rows_holder)
        self._offers_holder, self._offers_layout = self._list_holder()
        self._lists.addWidget(self._offers_holder)
        scroll.setWidget(self._lists)
        self.list_layout.addWidget(scroll, 1)

    @staticmethod
    def _list_holder() -> tuple[QWidget, QVBoxLayout]:
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(1)
        return holder, layout

    def _build_detail_pane(self) -> None:
        self._details = QFrame()
        self._details.setObjectName("useFlagsPanel")
        details = QVBoxLayout(self._details)
        details.setContentsMargins(t.SPACE_4, t.SPACE_4, t.SPACE_4, t.SPACE_4)
        details.setSpacing(t.SPACE_3)

        self._detail_name = QLabel()
        self._detail_name.setObjectName("packageAtom")
        details.addWidget(self._detail_name)

        self._detail_meta = QLabel()
        self._detail_meta.setProperty("role", "mono")
        self._detail_meta.setWordWrap(True)
        self._detail_meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details.addWidget(self._detail_meta)

        self._config_path = QLabel()
        self._config_path.setProperty("role", "mono")
        details.addWidget(self._config_path)

        self._config_text = QLabel()
        self._config_text.setObjectName("maskComment")
        self._config_text.setWordWrap(True)
        self._config_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details.addWidget(self._config_text)

        actions = QHBoxLayout()
        actions.setSpacing(t.SPACE_2)
        self._btn_sync = QPushButton()
        self._btn_sync.clicked.connect(self._on_sync)
        actions.addWidget(self._btn_sync)
        self._btn_mask = QPushButton()
        self._btn_mask.clicked.connect(self._on_mask)
        actions.addWidget(self._btn_mask)
        self._btn_remove = QPushButton()
        self._btn_remove.setProperty("variant", "danger")
        self._btn_remove.clicked.connect(self._on_remove)
        actions.addWidget(self._btn_remove)
        actions.addStretch(1)
        details.addLayout(actions)

        self._preview = WritePreview()
        self._preview.save_requested.connect(self._on_save)
        self._preview.reset_requested.connect(self._disarm)
        details.addWidget(self._preview)
        self.detail_layout.addWidget(self._details)

        self._build_packages_panel()
        self._build_offer_panel()
        # Without this the panels stretch to fill the pane and a short one
        # floats in the middle of its own empty half.
        self.detail_layout.addStretch(1)

    def _build_packages_panel(self) -> None:
        """What the selected repository brings with it."""
        self._packages_panel = QFrame()
        self._packages_panel.setObjectName("useFlagsPanel")
        layout = QVBoxLayout(self._packages_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        top = QFrame()
        top.setObjectName("useFlagsHeader")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, t.SPACE_3)
        top_layout.setSpacing(t.SPACE_3)
        self._packages_title = QLabel()
        self._packages_title.setProperty("role", "subheading")
        top_layout.addWidget(self._packages_title)
        top_layout.addStretch(1)
        self._packages_state = QLabel()
        self._packages_state.setProperty("role", "mono")
        top_layout.addWidget(self._packages_state)
        self._packages_all = ClickableLabel()
        self._packages_all.setProperty("role", "mono-accent")
        self._packages_all.clicked.connect(self._open_package_screen)
        top_layout.addWidget(self._packages_all)
        layout.addWidget(top)

        self._packages_holder = QWidget()
        self._packages_layout = QVBoxLayout(self._packages_holder)
        self._packages_layout.setContentsMargins(0, 0, 0, 0)
        self._packages_layout.setSpacing(0)
        layout.addWidget(self._packages_holder)
        self.detail_layout.addWidget(self._packages_panel)

    def _build_offer_panel(self) -> None:
        """A repository from the catalogue that is not configured here."""
        self._offer_panel = QFrame()
        self._offer_panel.setObjectName("useFlagsPanel")
        layout = QVBoxLayout(self._offer_panel)
        layout.setContentsMargins(t.SPACE_4, t.SPACE_4, t.SPACE_4, t.SPACE_4)
        layout.setSpacing(t.SPACE_3)

        self._offer_name = QLabel()
        self._offer_name.setObjectName("packageAtom")
        layout.addWidget(self._offer_name)

        self._offer_quality = QLabel()
        self._offer_quality.setObjectName("repoQuality")
        row = QHBoxLayout()
        row.addWidget(self._offer_quality)
        row.addStretch(1)
        layout.addLayout(row)

        self._offer_description = QLabel()
        self._offer_description.setWordWrap(True)
        layout.addWidget(self._offer_description)

        self._offer_meta = QLabel()
        self._offer_meta.setProperty("role", "mono")
        self._offer_meta.setWordWrap(True)
        self._offer_meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._offer_meta)

        self._offer_warning = QLabel()
        self._offer_warning.setObjectName("addOverlayWarning")
        self._offer_warning.setWordWrap(True)
        layout.addWidget(self._offer_warning)

        self._offer_command = QLabel()
        self._offer_command.setProperty("role", "mono")
        self._offer_command.setWordWrap(True)
        self._offer_command.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._offer_command)

        buttons = QHBoxLayout()
        buttons.setSpacing(t.SPACE_2)
        self._btn_enable = QPushButton()
        self._btn_enable.setProperty("variant", "primary")
        self._btn_enable.clicked.connect(self._on_enable)
        buttons.addWidget(self._btn_enable)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.detail_layout.addWidget(self._offer_panel)

    # -------------------------------------------------------------- data --

    def activated(self) -> None:
        # The package list under a repository comes out of the search index,
        # which is shared and built once.
        self.context.ensure_index()
        self.reload()

    def reload(self) -> None:
        """Re-read both sides. Counting packages is the slow part, so it waits."""
        run_async(self._read, self._on_read, self._on_read_failed)

    @staticmethod
    def _read() -> tuple[tuple[RepositoryInfo, ...], Catalogue, frozenset[str]]:
        return repos.list_repositories(), overlays.load(), repos.masked_repos()

    def _on_read(self, result: object) -> None:
        if not isinstance(result, tuple):
            return
        self._configured, self._catalogue, masked = result
        self._masked = masked
        self._rebuild_rows(masked)
        if self._selected is None and self._configured:
            self.select(self._configured[0].name)
        self._rebuild_offers()
        self._refresh_details()
        self.retranslate_ui()

    def _on_read_failed(self, error: Exception) -> None:
        log.error("Reading the repository list failed: %s", error)

    def _on_index_ready(self, _index: object) -> None:
        self._refresh_packages()

    # --------------------------------------------------------- the two tabs --

    def set_tab(self, tab: str) -> None:
        """Switch between what is configured and what could be."""
        self._tab = tab
        self._tab_configured.set_checked(tab == self.CONFIGURED)
        self._tab_available.set_checked(tab == self.AVAILABLE)
        self._lists.setCurrentWidget(
            self._rows_holder if tab == self.CONFIGURED else self._offers_holder
        )
        # A search typed in one tab means nothing in the other, and leaving it
        # behind would show a list filtered by something invisible.
        self._search.clear()
        self._rebuild_visible_tab()
        self._refresh_details()
        self.retranslate_ui()

    def _rebuild_visible_tab(self) -> None:
        if self._tab == self.CONFIGURED:
            self._rebuild_rows(self._masked)
        else:
            self._rebuild_offers()

    @staticmethod
    def _clear(layout: QVBoxLayout) -> None:
        """Empty a list, keeping the trailing stretch."""
        while layout.count() > 1:
            item = layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _rebuild_rows(self, masked: frozenset[str]) -> None:
        self._clear(self._rows_layout)
        self._rows.clear()

        needle = self._search.text().strip().lower() if self._tab == self.CONFIGURED else ""
        shown = [
            info
            for info in self._configured
            if not needle or needle in info.name.lower()
        ]
        for index, info in enumerate(shown):
            row = _ConfiguredRow(self, info, info.name in masked)
            row.set_selected(info.name == self._selected)
            self._rows[info.name] = row
            self._rows_layout.insertWidget(index, row)
        if not shown:
            self._rows_layout.insertWidget(0, self._hint(self._no_rows_text()))

    def _rebuild_offers(self) -> None:
        self._clear(self._offers_layout)
        self._offer_rows.clear()
        if self._tab != self.AVAILABLE:
            return

        if self._catalogue.is_empty:
            self._offers_layout.insertWidget(
                0,
                self._hint(
                    self.tr(
                        "No catalogue yet. Press Refresh to fetch Gentoo's list of "
                        "repositories."
                    )
                ),
            )
            return

        query = self._search.text().strip()
        # Nothing typed is not nothing to show: a repository nobody has heard of
        # is exactly the one that cannot be searched for by name.
        found = (
            self._catalogue.search(query, None) if query else self._catalogue.browse(None)
        )
        configured = {info.name for info in self._configured}
        found = [entry for entry in found if entry.name not in configured]
        if not found:
            self._offers_layout.insertWidget(
                0,
                self._hint(
                    self.tr("Nothing matches “{query}”.").format(query=query)
                    if query
                    else self.tr("Every repository in the catalogue is already configured.")
                ),
            )
            return

        for index, entry in enumerate(found[:_RESULT_LIMIT]):
            row = _CatalogueRow(self, entry)
            row.set_selected(self._offered is not None and entry.name == self._offered.name)
            self._offer_rows[entry.name] = row
            self._offers_layout.insertWidget(index, row)
        if len(found) > _RESULT_LIMIT:
            self._offers_layout.insertWidget(
                _RESULT_LIMIT,
                self._hint(
                    self.tr("Showing {shown} of {total}. Type to narrow the list.").format(
                        shown=_RESULT_LIMIT, total=len(found)
                    )
                ),
            )

    def _no_rows_text(self) -> str:
        return (
            self.tr("Nothing matches “{query}”.").format(query=self._search.text().strip())
            if self._search.text().strip()
            else self.tr("No repository is configured.")
        )

    def _hint(self, text: str) -> QLabel:
        """A line of explanation where the rows would be."""
        hint = QLabel(text)
        hint.setProperty("role", "caption")
        hint.setWordWrap(True)
        hint.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, t.SPACE_3)
        return hint

    # --------------------------------------------------------- selecting --

    def select(self, name: str) -> None:
        """Show a configured repository."""
        self._selected = name
        self._offered = None
        for row_name, row in self._rows.items():
            row.set_selected(row_name == name)
        for row in self._offer_rows.values():
            row.set_selected(False)
        self._disarm()
        self._refresh_details()

    def select_offer(self, entry: CatalogueEntry) -> None:
        """Show a repository from the catalogue that is not configured."""
        self._offered = entry
        for row_name, row in self._offer_rows.items():
            row.set_selected(row_name == entry.name)
        self._refresh_details()

    @property
    def _current(self) -> RepositoryInfo | None:
        return next((r for r in self._configured if r.name == self._selected), None)

    @property
    def _showing_offer(self) -> bool:
        return self._tab == self.AVAILABLE and self._offered is not None

    # ----------------------------------------------------------- actions --

    def _run(self, spec, then=None) -> None:  # noqa: ANN001 - CommandSpec
        self._after_command = then
        if not self.context.run(spec):
            self._after_command = None

    def _on_running_changed(self, running: bool) -> None:
        for button in (
            self._btn_sync,
            self._btn_remove,
            self._btn_enable,
            self._add,
            self._sync_all,
            self._refresh,
        ):
            button.setEnabled(not running)

    def _on_command_finished(self, code: int) -> None:
        follow_up, self._after_command = self._after_command, None
        if code == 0 and follow_up is not None:
            follow_up()
            return
        if code == 0:
            # eselect and emaint both change what Portage sees.
            self.context.reload_portage()
            self.context.reload_index()
            self.reload()

    def _on_enable(self) -> None:
        entry = self._offered
        if entry is not None:
            self.enable(entry)

    def enable(self, entry: CatalogueEntry) -> None:
        """Enable a catalogued repository and sync it in one go."""
        source = entry.preferred_source
        detail = self.tr(
            "This will run:\n\neselect repository enable {name}\nemaint sync -r {name}\n\n"
            "Source: {uri}"
        ).format(name=entry.name, uri=source[1] if source else "?")
        if not entry.is_official:
            detail += "\n\n" + self.tr(
                "This repository is not run by Gentoo. Its ebuilds will run as root "
                "while building packages."
            )
        if not self._confirm(self.tr("Enable repository"), detail):
            return
        name = entry.name

        def then() -> None:
            self._run(eselect.sync(name))
            # It is configured from here on, so it belongs to the other tab.
            self._selected = name
            self._offered = None
            self._tab = self.CONFIGURED

        self._run(eselect.enable(name), then)

    def _on_sync(self) -> None:
        info = self._current
        if info is not None:
            self._run(eselect.sync(info.name))

    def _on_remove(self) -> None:
        """Docs/04-privileges.md §6: say what will be orphaned, then ask."""
        info = self._current
        if info is None:
            return
        if info.is_official:
            QMessageBox.information(
                self,
                self.tr("Remove repository"),
                self.tr("The main repository cannot be removed."),
            )
            return

        installed = repos.installed_from(info.name)
        detail = self.tr("This will run:\n\neselect repository remove -f {name}").format(
            name=info.name
        )
        if installed:
            detail += "\n\n" + self.tr(
                "%n installed package(s) came from this repository. They stay on the "
                "system but lose their ebuild, so nothing will update or rebuild them "
                "again:",
                "",
                len(installed),
            )
            detail += "\n" + "\n".join(installed[:10])
            if len(installed) > 10:
                detail += "\n…"
        if self._confirm(self.tr("Remove repository"), detail):
            self._selected = None
            self._run(eselect.remove(info.name))

    def _on_add(self) -> None:
        dialog = AddOverlayDialog(self)
        if dialog.exec() != AddOverlayDialog.DialogCode.Accepted:
            return
        name, sync_type, uri = dialog.repository
        self._run(eselect.add(name, sync_type, uri), lambda: self._run(eselect.sync(name)))

    def _open_package_screen(self) -> None:
        """Hand the repository to the screen that is built for packages."""
        info = self._current
        window = self.window()
        if info is None or not hasattr(window, "set_page"):  # pragma: no cover - defensive
            return
        window.set_page("search")
        page = window.stack.currentWidget()
        if hasattr(page, "set_query"):
            page.set_query(f"::{info.name}")

    # -------------------------------------------- hiding a whole repository --

    def _on_mask(self) -> None:
        """Mode (b) of "Only ::gentoo", one repository at a time."""
        info = self._current
        if info is None:
            return
        masked = repos.is_masked(info.name)
        self._plan = (
            repos.plan_unmask(info.name) if masked else repos.plan_mask(info.name)
        )
        if not masked:
            installed = repos.installed_from(info.name)
            if installed and not self._confirm(
                self.tr("Hide repository from Portage"),
                self.tr(
                    "%n installed package(s) came from ::{name}. Masking it means Portage "
                    "stops offering updates for them — they are not removed, and nothing "
                    "else changes.",
                    "",
                    len(installed),
                ).format(name=info.name),
            ):
                self._plan = None
                return
        self._preview.set_plan(self._plan)

    def _disarm(self) -> None:
        self._plan = None
        self._preview.set_plan(None)

    def _on_save(self) -> None:
        plan = self._plan
        if plan is None or plan.is_noop:
            return
        self._preview.set_busy(True)
        run_async(
            helper_client.request,
            self._on_written,
            self._on_write_failed,
            plan.op,
            ensure_backup=self.context.backups.needs_backup(),
            **self.context.backup_options(),
            **plan.as_request(),
        )

    def _on_written(self, result: object) -> None:
        if getattr(result, "ok", False):
            self.context.backups.note(getattr(result, "backup", None))
            self.context.backups_changed.emit()
            data = getattr(result, "data", {}) or {}
            self._preview.report_success(
                self.tr("Written to {path}.").format(path=data.get("path", ""))
            )
            self.context.reload_portage()
            self.context.reload_index()
            self.reload()
        elif getattr(result, "cancelled", False):
            self._preview.report_failure(self.tr("Cancelled — nothing was written."))
        else:
            self._preview.report_failure(
                self.tr("Nothing was written: {error}").format(
                    error=getattr(result, "error", "")
                )
            )

    def _on_write_failed(self, error: Exception) -> None:
        log.error("Masking the repository failed: %s", error)
        self._preview.report_failure(str(error))

    def _confirm(self, title: str, detail: str) -> bool:
        answer = QMessageBox.question(
            self,
            title,
            detail,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Yes

    # ------------------------------------------------------ the right side --

    def _refresh_details(self) -> None:
        offer = self._showing_offer
        info = self._current

        self._offer_panel.setVisible(offer)
        self._details.setVisible(not offer and info is not None)
        self._packages_panel.setVisible(not offer and info is not None)

        if offer:
            self._refresh_offer()
            return
        if info is None:
            return

        self._detail_name.setText(f"::{info.name}")
        parts = [
            info.location,
            f"sync-type={info.sync_type or '-'}",
            f"sync-uri={info.sync_uri or '-'}",
        ]
        if info.masters:
            parts.append("masters=" + ", ".join(info.masters))
        self._detail_meta.setText("\n".join(parts))

        section = repos.config_section(info.name)
        if section is None:
            self._config_path.setText("")
            self._config_text.setText(self.tr("Defined by the profile, not by repos.conf."))
        else:
            path, text = section
            self._config_path.setText(str(path))
            self._config_text.setText(text)

        masked = repos.is_masked(info.name)
        self._btn_mask.setText(
            self.tr("Show in Portage again") if masked else self.tr("Hide from Portage")
        )
        self._btn_mask.setToolTip(repos.mask_atom(info.name))
        self._btn_remove.setVisible(not info.is_official)
        self._btn_sync.setToolTip(f"emaint sync -r {info.name}")
        self._refresh_packages()

    def _refresh_offer(self) -> None:
        entry = self._offered
        if entry is None:
            return
        self._offer_name.setText(f"::{entry.name}")
        self._offer_quality.setProperty("official", "yes" if entry.is_official else "no")
        official = self.tr("official") if entry.is_official else self.tr("unofficial")
        self._offer_quality.setText(
            f"{official} · {entry.quality}" if entry.quality else official
        )
        style = self._offer_quality.style()
        if style is not None:
            style.unpolish(self._offer_quality)
            style.polish(self._offer_quality)

        self._offer_description.setText(entry.description)
        source = entry.preferred_source
        parts = []
        if entry.homepage:
            parts.append(entry.homepage)
        if entry.owners:
            parts.append(self.tr("maintained by {owners}").format(owners=", ".join(entry.owners)))
        if source:
            parts.append(f"{source[0]}  {source[1]}")
        self._offer_meta.setText("\n".join(parts))

        self._offer_warning.setVisible(not entry.is_official)
        self._offer_command.setText(
            untranslated(
                f"eselect repository enable {entry.name}\nemaint sync -r {entry.name}"
            )
        )
        self._btn_enable.setEnabled(not self.context.is_running)

    def _refresh_packages(self) -> None:
        """The packages this repository is the source of."""
        info = self._current
        while self._packages_layout.count():
            item = self._packages_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        if info is None or self._showing_offer:
            return

        index = self.context.index
        if not isinstance(index, SearchIndex):
            self._packages_state.setText("")
            self._packages_all.setText("")
            self._packages_layout.addWidget(
                self._hint(self.tr("Reading the package index…"))
            )
            return

        found = [entry for entry in index.entries if info.name in entry.repos]
        self._packages_state.setText(
            self.tr("%n package(s)", "", len(found)) if found else ""
        )
        self._packages_all.setText(self.tr("Open in Search & install") if found else "")
        if not found:
            self._packages_layout.addWidget(
                self._hint(
                    self.tr(
                        "Nothing comes from ::{name} — every package it carries is also "
                        "in a repository Portage prefers."
                    ).format(name=info.name)
                )
            )
            return

        for entry in found[:_PACKAGE_LIMIT]:
            self._packages_layout.addWidget(_PackageRow(self, entry.cp, entry.description))
        if len(found) > _PACKAGE_LIMIT:
            self._packages_layout.addWidget(
                self._hint(
                    self.tr(
                        "Showing {shown} of {total}. The package screen has the search "
                        "and the filters for the rest."
                    ).format(shown=_PACKAGE_LIMIT, total=len(found))
                )
            )

    # -------------------------------------------------------------- i18n --

    def retranslate_ui(self) -> None:
        configured = len(self._configured)
        available = max(0, len(self._catalogue) - configured)
        self._tab_configured.set_text(self.tr("Configured"))
        self._tab_configured.set_suffix(str(configured))
        self._tab_available.set_text(self.tr("Available"))
        self._tab_available.set_suffix(str(available) if available else "")

        self._search_icon.setPixmap(
            icons.tinted_pixmap(
                "magnifying-glass",
                t.NEUTRAL_500,
                max(12, round(self.fontMetrics().height() * 0.85)),
                self.devicePixelRatioF(),
            )
        )
        self._search.setPlaceholderText(
            self.tr("filter by name")
            if self._tab == self.CONFIGURED
            else self.tr("name or keyword, e.g. steam")
        )
        self._sync_all.setText(self.tr("Synchronise all"))
        self._sync_all.setToolTip(untranslated("emaint sync -a"))
        self._sync_all.setVisible(self._tab == self.CONFIGURED)
        self._refresh.setText(self.tr("Refresh the catalogue"))
        self._refresh.setToolTip(untranslated("eselect repository list"))
        self._refresh.setVisible(self._tab == self.AVAILABLE)
        self._add.setText(self.tr("Add by hand…"))
        self._add.setVisible(self._tab == self.AVAILABLE)

        self._btn_sync.setText(self.tr("Synchronise"))
        self._btn_remove.setText(self.tr("Remove…"))
        self._btn_enable.setText(self.tr("Enable this repository"))
        self._packages_title.setText(self.tr("Packages from here"))
        self._offer_warning.setText(
            self.tr(
                "Nobody at Gentoo runs this repository. Building one of its packages "
                "runs its ebuild as root, now and at every sync after."
            )
        )
        for row in self._rows.values():
            row.retranslate_ui()
        for row in self._offer_rows.values():
            row.retranslate_ui()
        self._refresh_details()
        self._preview.retranslate_ui()


class _PackageRow(QFrame):
    """One package the selected repository is the source of."""

    def __init__(self, page: ReposPage, cp: str, description: str) -> None:
        super().__init__(page)
        self.setObjectName("catalogueRow")
        self._page = page
        self.cp = cp

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_4, t.SPACE_2, t.SPACE_4, t.SPACE_2)
        layout.setSpacing(0)

        name = QLabel(cp)
        name.setObjectName("repoRowName")
        layout.addWidget(name)

        if description:
            text = QLabel(description)
            text.setProperty("role", "caption")
            text.setWordWrap(True)
            layout.addWidget(text)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802, ANN001 - Qt API
        window = self._page.window()
        if hasattr(window, "set_page"):
            window.set_page("search")
            page = window.stack.currentWidget()
            if hasattr(page, "set_query"):
                page.set_query(self.cp)
        super().mouseReleaseEvent(event)
