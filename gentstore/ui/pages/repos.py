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

"""The "Repositories" screen: what is configured, and what else exists.

Two halves that answer two different questions. On the left, the repositories
this system actually uses — with the ``repos.conf`` section that defines each
one, shown as it is written rather than summarised, because that file is what
somebody would go and read. On the right, Gentoo's published catalogue of four
hundred-odd others, searchable, one click to enable.

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
    QVBoxLayout,
    QWidget,
)

from ...core import overlays, repos
from ...core.confedit import WritePlan
from ...core.overlays import Catalogue, CatalogueEntry
from ...core.repos import RepositoryInfo
from ...runner import eselect, helper_client
from ..context import AppContext
from ..i18n import untranslated
from ..tasks import run_async
from ..theme import tokens as t
from ..widgets.add_overlay_dialog import AddOverlayDialog
from ..widgets.clickable_label import ClickableLabel
from ..widgets.write_preview import WritePreview
from .registry import PageSpec
from .split_page import SplitPage

log = logging.getLogger(__name__)

#: The list side is wider here than on the package screen: repository names and
#: their sync dates do not shorten (Docs/02-ui-design.md §4).
LIST_WIDTH = 512

#: Catalogue rows shown at once, browsing or searching. Enough that a short
#: catalogue is simply the list and nothing has to be typed at all; four
#: hundred-odd of them is what the search box is for.
_RESULT_LIMIT = 50


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

    def __init__(self, page: ReposPage, entry: CatalogueEntry, configured: bool) -> None:
        super().__init__(page)
        self.setObjectName("catalogueRow")
        self._page = page
        self.entry = entry
        self._configured = configured

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

        self._action = QPushButton()
        self._action.clicked.connect(lambda: page.enable(entry))
        self._action.setEnabled(not configured)
        top.addWidget(self._action)
        layout.addLayout(top)

        description = QLabel(entry.description)
        description.setProperty("role", "caption")
        description.setWordWrap(True)
        layout.addWidget(description)

        source = entry.preferred_source
        uri = QLabel(source[1] if source else "")
        uri.setProperty("role", "mono")
        uri.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(uri)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        entry = self.entry
        official = self.tr("official") if entry.is_official else self.tr("unofficial")
        self._quality.setText(f"{official} · {entry.quality}" if entry.quality else official)
        self._action.setText(
            self.tr("already configured") if self._configured else self.tr("Enable")
        )


class ReposPage(SplitPage):
    """Configured repositories on the left, the whole catalogue on the right."""

    def __init__(
        self, spec: PageSpec, context: AppContext, parent: QWidget | None = None
    ) -> None:
        super().__init__(spec, context, parent)
        self.set_list_width(LIST_WIDTH)

        self._configured: tuple[RepositoryInfo, ...] = ()
        self._catalogue = Catalogue()
        self._rows: dict[str, _ConfiguredRow] = {}
        self._selected: str | None = None
        self._plan: WritePlan | None = None
        self._after_command = None

        self._build_list_pane()
        self._build_detail_pane()

        context.command.finished.connect(self._on_command_finished)
        context.command.running_changed.connect(self._on_running_changed)
        self.retranslate_ui()

    # ------------------------------------------------------------ building --

    def _build_list_pane(self) -> None:
        header = QFrame()
        header.setObjectName("searchHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(t.SPACE_4, t.SPACE_4, t.SPACE_4, t.SPACE_4)
        header_layout.setSpacing(t.SPACE_3)
        self._list_title = QLabel()
        self._list_title.setProperty("role", "subheading")
        header_layout.addWidget(self._list_title)
        header_layout.addStretch(1)
        self._sync_all = QPushButton()
        self._sync_all.clicked.connect(lambda: self._run(eselect.sync_all()))
        header_layout.addWidget(self._sync_all)
        self.list_layout.addWidget(header)

        self._rows_holder = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_holder)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)
        self._rows_layout.addStretch(1)
        self.list_layout.addWidget(self._rows_holder, 1)

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

        browser = QFrame()
        browser.setObjectName("useFlagsPanel")
        browser_layout = QVBoxLayout(browser)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.setSpacing(0)

        top = QFrame()
        top.setObjectName("useFlagsHeader")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, t.SPACE_3)
        top_layout.setSpacing(t.SPACE_3)
        self._browser_title = QLabel()
        self._browser_title.setProperty("role", "subheading")
        top_layout.addWidget(self._browser_title)

        self._search = QLineEdit()
        self._search.setObjectName("searchInput")
        self._search.textChanged.connect(self._on_search)
        top_layout.addWidget(self._search, 1)

        self._catalogue_state = QLabel()
        self._catalogue_state.setProperty("role", "mono")
        top_layout.addWidget(self._catalogue_state)

        self._refresh = ClickableLabel()
        self._refresh.setProperty("role", "mono-accent")
        self._refresh.clicked.connect(lambda: self._run(eselect.list_repositories()))
        top_layout.addWidget(self._refresh)

        self._add = QPushButton()
        self._add.setProperty("variant", "danger")
        self._add.clicked.connect(self._on_add)
        top_layout.addWidget(self._add)
        browser_layout.addWidget(top)

        self._results = QWidget()
        self._results_layout = QVBoxLayout(self._results)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(0)
        browser_layout.addWidget(self._results)
        self.detail_layout.addWidget(browser)
        # Without this the two panels stretch to fill the pane and the browser
        # header floats in the middle of its own empty half.
        self.detail_layout.addStretch(1)

    # -------------------------------------------------------------- data --

    def activated(self) -> None:
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
        self._rebuild_rows(masked)
        if self._selected is None and self._configured:
            self.select(self._configured[0].name)
        else:
            self._refresh_details()
        self._on_search(self._search.text())
        self.retranslate_ui()

    def _on_read_failed(self, error: Exception) -> None:
        log.error("Reading the repository list failed: %s", error)

    def _rebuild_rows(self, masked: frozenset[str]) -> None:
        while self._rows_layout.count() > 1:
            item = self._rows_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._rows.clear()

        for index, info in enumerate(self._configured):
            row = _ConfiguredRow(self, info, info.name in masked)
            self._rows[info.name] = row
            self._rows_layout.insertWidget(index, row)

    def select(self, name: str) -> None:
        self._selected = name
        for row_name, row in self._rows.items():
            row.set_selected(row_name == name)
        self._disarm()
        self._refresh_details()

    @property
    def _current(self) -> RepositoryInfo | None:
        return next((r for r in self._configured if r.name == self._selected), None)

    # ---------------------------------------------------------- searching --

    def _on_search(self, text: str) -> None:
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        query = text.strip()
        if self._catalogue.is_empty:
            self._results_layout.addWidget(
                self._hint(
                    self.tr(
                        "No catalogue yet. Press Refresh to fetch Gentoo's list of "
                        "repositories."
                    )
                )
            )
            return

        # Nothing typed is not nothing to show. Four hundred repositories the
        # user has never heard of cannot be searched by name, so the panel opens
        # on the list itself and the search box narrows it.
        found = (
            self._catalogue.search(query, None) if query else self._catalogue.browse(None)
        )
        if not found:
            self._results_layout.addWidget(
                self._hint(self.tr("Nothing matches “{query}”.").format(query=query))
            )
            return

        configured = {info.name for info in self._configured}
        if not query:
            # A repository already on the left is not an offer. It stays in the
            # list — its absence would read as the catalogue being wrong — but
            # it goes to the end rather than heading the page as ::gentoo,
            # official and core, otherwise would.
            found.sort(key=lambda entry: entry.name in configured)
        for entry in found[:_RESULT_LIMIT]:
            self._results_layout.addWidget(
                _CatalogueRow(self, entry, entry.name in configured)
            )
        if len(found) > _RESULT_LIMIT:
            self._results_layout.addWidget(
                self._hint(
                    self.tr("Showing {shown} of {total}. Type to narrow the list.").format(
                        shown=_RESULT_LIMIT, total=len(found)
                    )
                )
            )

    def _hint(self, text: str) -> QLabel:
        """A line of explanation where the result rows would be."""
        hint = QLabel(text)
        hint.setProperty("role", "caption")
        hint.setWordWrap(True)
        hint.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, t.SPACE_3)
        return hint

    # ----------------------------------------------------------- actions --

    def _run(self, spec, then=None) -> None:  # noqa: ANN001 - CommandSpec
        self._after_command = then
        if not self.context.run(spec):
            self._after_command = None

    def _on_running_changed(self, running: bool) -> None:
        for button in (self._btn_sync, self._btn_remove, self._add, self._sync_all):
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
        self._run(eselect.enable(entry.name), lambda: self._run(eselect.sync(entry.name)))

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
            self._run(eselect.remove(info.name))

    def _on_add(self) -> None:
        dialog = AddOverlayDialog(self)
        if dialog.exec() != AddOverlayDialog.DialogCode.Accepted:
            return
        name, sync_type, uri = dialog.repository
        self._run(eselect.add(name, sync_type, uri), lambda: self._run(eselect.sync(name)))

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

    # -------------------------------------------------------------- i18n --

    def _refresh_details(self) -> None:
        info = self._current
        self._details.setVisible(info is not None)
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

    def retranslate_ui(self) -> None:
        self._list_title.setText(self.tr("Configured"))
        self._sync_all.setText(self.tr("Synchronise all"))
        self._sync_all.setToolTip(untranslated("emaint sync -a"))
        self._browser_title.setText(self.tr("All repositories"))
        self._search.setPlaceholderText(self.tr("name or keyword, e.g. steam"))
        self._refresh.setText(self.tr("Refresh"))
        self._refresh.setToolTip(untranslated("eselect repository list"))
        self._add.setText(self.tr("Add by hand…"))
        self._btn_sync.setText(self.tr("Synchronise"))
        self._btn_remove.setText(self.tr("Remove…"))
        self._catalogue_state.setText(
            self.tr("%n known", "", len(self._catalogue)) if self._catalogue else ""
        )
        for row in self._rows.values():
            row.retranslate_ui()
        self._refresh_details()
        self._preview.retranslate_ui()
