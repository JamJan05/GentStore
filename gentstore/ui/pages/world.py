"""``@world``: the short list of packages you asked for.

Everything installed on a Gentoo system is either in ``@world`` — you asked for
it — or a dependency of something that is. That distinction is what
``--depclean`` runs on, and it is the one people find hardest to see, because
both kinds of package look identical once installed.

So the screen puts them side by side. On the left, the twenty-odd entries in
``/var/lib/portage/world``. On the right, the thousand things actually on disk.
Taking an entry out of ``@world`` **does not uninstall it** — it stops
protecting it, and the next ``--depclean`` decides whether anything still needs
it. The screen says so before doing it, because "remove" reads like "delete".
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
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core import worldset
from ...core.worldset import InstalledPackage, WorldEntry
from ...runner import emerge
from ..context import AppContext
from ..tasks import run_async
from ..theme import tokens as t
from ..widgets.clickable_label import ClickableLabel
from .registry import PageSpec
from .split_page import SplitPage

log = logging.getLogger(__name__)

#: Wider than the package list: world entries are atoms, which do not shorten.
LIST_WIDTH = 560

#: Installed rows shown at once; the filter narrows the rest.
INSTALLED_LIMIT = 400

_SIZE_UNITS = ("B", "KiB", "MiB", "GiB")


def format_size(size: int | None) -> str:
    if size is None:
        return ""
    value = float(size)
    for unit in _SIZE_UNITS:
        if value < 1024 or unit == _SIZE_UNITS[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return ""  # pragma: no cover - unreachable


class _WorldRow(QFrame):
    """One line of ``/var/lib/portage/world``."""

    def __init__(self, page: WorldPage, entry: WorldEntry) -> None:
        super().__init__(page)
        self.setObjectName("worldRow")
        self.setProperty("satisfied", "yes" if entry.is_satisfied else "no")
        self._page = page
        self.entry = entry

        layout = QHBoxLayout(self)
        layout.setContentsMargins(t.SPACE_4, t.SPACE_2, t.SPACE_4, t.SPACE_2)
        layout.setSpacing(t.SPACE_3)

        atom = QLabel(entry.atom)
        atom.setObjectName("worldAtom")
        atom.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(atom)

        self._versions = QLabel()
        self._versions.setProperty("role", "mono")
        layout.addWidget(self._versions)
        layout.addStretch(1)

        self._remove = ClickableLabel()
        self._remove.setProperty("role", "mono-accent")
        self._remove.clicked.connect(lambda: page.deselect(entry))
        layout.addWidget(self._remove)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        entry = self.entry
        self._versions.setText(
            ", ".join(item.version for item in entry.installed)
            if entry.is_satisfied
            else self.tr("not installed")
        )
        self._remove.setText(self.tr("Take out of @world…"))


class _InstalledRow(QFrame):
    """One entry of ``/var/db/pkg``."""

    def __init__(self, package: InstalledPackage, official: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("installedRow")
        self.package = package

        layout = QHBoxLayout(self)
        layout.setContentsMargins(t.SPACE_4, t.SPACE_1, t.SPACE_4, t.SPACE_1)
        layout.setSpacing(t.SPACE_3)

        name = QLabel(package.cp)
        name.setObjectName("installedName")
        layout.addWidget(name)

        version = QLabel(package.version)
        version.setProperty("role", "mono")
        layout.addWidget(version)
        layout.addStretch(1)

        repo = QLabel(f"::{package.repo}" if package.repo else "")
        repo.setObjectName("repoQuality")
        repo.setProperty("official", "yes" if package.repo == official else "no")
        layout.addWidget(repo)

        size = QLabel(format_size(package.size))
        size.setProperty("role", "mono")
        size.setMinimumWidth(72)
        size.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(size)


class WorldPage(SplitPage):
    """``@world`` beside everything that is actually installed."""

    def __init__(
        self, spec: PageSpec, context: AppContext, parent: QWidget | None = None
    ) -> None:
        super().__init__(spec, context, parent)
        self.set_list_width(LIST_WIDTH)

        self._entries: tuple[WorldEntry, ...] = ()
        self._installed: tuple[InstalledPackage, ...] = ()
        self._rows: list[_WorldRow] = []

        self._build_list_pane()
        self._build_detail_pane()
        context.command.finished.connect(lambda _code: self.reload())
        self.retranslate_ui()

    # ------------------------------------------------------------ building --

    def _build_list_pane(self) -> None:
        header = QFrame()
        header.setObjectName("searchHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(t.SPACE_4, t.SPACE_4, t.SPACE_4, t.SPACE_4)
        header_layout.setSpacing(t.SPACE_1)
        self._world_title = QLabel()
        self._world_title.setProperty("role", "subheading")
        header_layout.addWidget(self._world_title)
        self._world_note = QLabel()
        self._world_note.setProperty("role", "caption")
        self._world_note.setWordWrap(True)
        header_layout.addWidget(self._world_note)
        self.list_layout.addWidget(header)

        holder = QScrollArea()
        holder.setWidgetResizable(True)
        holder.setObjectName("detailPane")
        holder.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        self._world_layout = QVBoxLayout(content)
        self._world_layout.setContentsMargins(0, 0, 0, 0)
        self._world_layout.setSpacing(0)
        self._world_layout.addStretch(1)
        holder.setWidget(content)
        self.list_layout.addWidget(holder, 1)

    def _build_detail_pane(self) -> None:
        top = QHBoxLayout()
        top.setSpacing(t.SPACE_3)
        self._installed_title = QLabel()
        self._installed_title.setProperty("role", "subheading")
        top.addWidget(self._installed_title)
        self._filter = QLineEdit()
        self._filter.setObjectName("searchInput")
        self._filter.textChanged.connect(lambda _text: self._rebuild_installed())
        top.addWidget(self._filter, 1)
        self._summary = QLabel()
        self._summary.setProperty("role", "mono")
        top.addWidget(self._summary)
        self.detail_layout.addLayout(top)

        holder = QScrollArea()
        holder.setWidgetResizable(True)
        holder.setObjectName("detailPane")
        holder.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        self._installed_layout = QVBoxLayout(content)
        self._installed_layout.setContentsMargins(0, 0, 0, 0)
        self._installed_layout.setSpacing(0)
        self._installed_layout.addStretch(1)
        holder.setWidget(content)
        self.detail_layout.addWidget(holder, 1)

    # -------------------------------------------------------------- data --

    def activated(self) -> None:
        self.reload()

    def reload(self) -> None:
        run_async(self._read, self._on_read, self._on_read_failed)

    @staticmethod
    def _read() -> tuple[tuple[WorldEntry, ...], tuple[InstalledPackage, ...]]:
        return worldset.world_entries(), worldset.installed_packages()

    def _on_read(self, result: object) -> None:
        if not isinstance(result, tuple):
            return
        self._entries, self._installed = result
        self._rebuild_world()
        self._rebuild_installed()
        self.context.sidebar_badge.emit("world", str(len(self._entries)))
        self.retranslate_ui()

    def _on_read_failed(self, error: Exception) -> None:
        log.error("Reading @world failed: %s", error)

    @staticmethod
    def _clear(layout: QVBoxLayout) -> None:
        while layout.count() > 1:
            item = layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _rebuild_world(self) -> None:
        self._clear(self._world_layout)
        self._rows = []
        for entry in self._entries:
            row = _WorldRow(self, entry)
            self._rows.append(row)
            self._world_layout.insertWidget(len(self._rows) - 1, row)

    def _rebuild_installed(self) -> None:
        self._clear(self._installed_layout)
        needle = self._filter.text().strip().lower()
        official = self.context.main_repo_name()

        matching = [
            package
            for package in self._installed
            if not needle or needle in package.cp.lower()
        ]
        for index, package in enumerate(matching[:INSTALLED_LIMIT]):
            self._installed_layout.insertWidget(
                index, _InstalledRow(package, official, self)
            )
        self._matching_count = len(matching)
        self._shown_count = min(len(matching), INSTALLED_LIMIT)
        self.retranslate_ui()

    # ----------------------------------------------------------- removing --

    def deselect(self, entry: WorldEntry) -> None:
        """``emerge --deselect`` — and say plainly what that does and does not do."""
        answer = QMessageBox.question(
            self,
            self.tr("Take out of @world"),
            self.tr(
                "Remove {atom} from @world?\n\n"
                "This does not uninstall anything. It only stops the package being one "
                "you asked for, so the next --depclean will remove it if nothing else "
                "needs it.\n\nThis will run:\n\n  emerge --deselect {atom}"
            ).format(atom=entry.atom),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.context.run(emerge.deselect([entry.atom]))

    # -------------------------------------------------------------- i18n --

    def retranslate_ui(self) -> None:
        self._world_title.setText(self.tr("@world"))
        self._world_note.setText(
            self.tr(
                "The packages you asked for. Everything else installed is here because "
                "one of these needs it."
            )
        )
        self._installed_title.setText(self.tr("Installed"))
        self._filter.setPlaceholderText(self.tr("filter by name"))

        total = worldset.total_installed_size(self._installed)
        shown = getattr(self, "_shown_count", 0)
        matching = getattr(self, "_matching_count", 0)
        parts = [self.tr("%n package(s)", "", matching), format_size(total)]
        if matching > shown:
            parts.append(self.tr("showing the first %n", "", shown))
        self._summary.setText("   ·   ".join(part for part in parts if part))

        for row in self._rows:
            row.retranslate_ui()
