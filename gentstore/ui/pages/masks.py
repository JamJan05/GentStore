"""The "Masks & licences" screen: what this system has already been told to allow.

``/etc/portage/package.accept_keywords`` and its neighbours accumulate. A line
added two years ago to install one testing version is still there, still
accepting that version, and nobody has read the file since. This screen is that
file, read back: every entry, the file it lives in, and a way to take it out
again.

One column, because there is nothing to put beside it — and because the list is
the point rather than a way of navigating to something else.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core import confedit
from ...core.confedit import WritePlan
from ...core.licenses import ConditionalLicence, LicenceCondition
from ...core.licenses import conditional_licences as load_conditional
from ...runner import helper_client
from ..context import AppContext
from ..tasks import run_async
from ..theme import tokens as t
from ..widgets.clickable_label import ClickableLabel
from ..widgets.write_preview import WritePreview
from .base import Page
from .registry import PageSpec

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Section:
    """One ``/etc/portage`` file and what it is for."""

    file_name: str
    #: Key the page turns into a heading; kept apart so core stays translation-free.
    key: str


SECTIONS = (
    Section("package.accept_keywords", "keywords"),
    Section("package.unmask", "unmask"),
    Section("package.license", "licence"),
    Section("package.mask", "mask"),
)


class _EntryRow(QFrame):
    """One line of one file, with a way to take it back out."""

    def __init__(self, page: MasksPage, file_name: str, path, line: str) -> None:  # noqa: ANN001
        super().__init__(page)
        self.setObjectName("maskEntry")
        self._page = page
        self._file_name = file_name
        self._line = line

        atom, _, rest = line.partition(" ")
        self._atom = atom

        layout = QHBoxLayout(self)
        layout.setContentsMargins(t.SPACE_4, t.SPACE_2, t.SPACE_4, t.SPACE_2)
        layout.setSpacing(t.SPACE_3)

        name = QLabel(atom)
        name.setObjectName("maskEntryAtom")
        name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(name)

        tokens = QLabel(rest.strip())
        tokens.setProperty("role", "mono")
        layout.addWidget(tokens)
        layout.addStretch(1)

        # The file name, not the whole path: every row in a section shares the
        # same directory, and repeating it crowds out the part that differs.
        location = QLabel(path.name)
        location.setProperty("role", "mono")
        location.setToolTip(str(path))
        layout.addWidget(location)

        self._remove = ClickableLabel()
        self._remove.setProperty("role", "mono-accent")
        self._remove.clicked.connect(self._on_remove)
        layout.addWidget(self._remove)

        self.retranslate_ui()

    def _on_remove(self) -> None:
        self._page.arm_removal(self._file_name, self._atom)

    def retranslate_ui(self) -> None:
        self._remove.setText(self.tr("Remove…"))


class _ConditionalRow(QFrame):
    """One package whose licence bill grows if a flag is turned on."""

    def __init__(self, page: MasksPage, item: ConditionalLicence) -> None:
        super().__init__(page)
        self.setObjectName("maskEntry")
        self._page = page
        self._item = item

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_4, t.SPACE_2, t.SPACE_4, t.SPACE_2)
        layout.setSpacing(t.SPACE_1)

        top = QHBoxLayout()
        top.setSpacing(t.SPACE_3)
        name = ClickableLabel(item.cpv)
        name.setProperty("role", "mono")
        name.setToolTip(self.tr("Open this package"))
        name.clicked.connect(lambda: page.open_package(item.cp))
        top.addWidget(name)
        repo = QLabel(f"::{item.repo}" if item.repo else "")
        repo.setProperty("role", "caption")
        top.addWidget(repo)
        top.addStretch(1)
        layout.addLayout(top)

        expression = QLabel(item.expression)
        expression.setProperty("role", "caption")
        expression.setWordWrap(True)
        expression.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(expression)

        for condition in item.conditions:
            line = QLabel()
            line.setProperty("role", "caption")
            line.setWordWrap(True)
            line.setText(page.condition_text(condition))
            layout.addWidget(line)


class MasksPage(Page):
    """Everything this system has been told to accept, and how to undo it."""

    def __init__(
        self, spec: PageSpec, context: AppContext, parent: QWidget | None = None
    ) -> None:
        super().__init__(spec, context, parent)
        self._section_widgets: dict[str, tuple[QLabel, QLabel, QWidget]] = {}
        self._plan: WritePlan | None = None
        #: Filled in by a worker: reading LICENSE for every package in every
        #: repository is seconds, not milliseconds.
        self._conditional: tuple[ConditionalLicence, ...] | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("detailPane")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("detailContent")
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(t.SPACE_8, t.SPACE_6, t.SPACE_8, t.SPACE_8)
        self._layout.setSpacing(t.SPACE_6)

        self._heading = QLabel()
        self._heading.setProperty("role", "heading")
        self._layout.addWidget(self._heading)

        self._settings = QLabel()
        self._settings.setProperty("role", "mono")
        self._settings.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._layout.addWidget(self._settings)

        for section in SECTIONS:
            self._layout.addWidget(self._build_section(section))

        self._layout.addWidget(self._build_conditional_section())

        self._layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        self._preview = WritePreview()
        self._preview.save_requested.connect(self._on_save)
        self._preview.reset_requested.connect(self._disarm)
        outer.addWidget(self._preview)

        self.retranslate_ui()

    def _build_section(self, section: Section) -> QWidget:
        box = QFrame()
        box.setObjectName("maskSection")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, t.SPACE_3)
        header_layout.setSpacing(t.SPACE_3)
        title = QLabel()
        title.setObjectName("maskSectionTitle")
        header_layout.addWidget(title)
        purpose = QLabel()
        purpose.setProperty("role", "caption")
        purpose.setWordWrap(True)
        header_layout.addWidget(purpose, 1)
        layout.addWidget(header)

        entries = QWidget()
        entries_layout = QVBoxLayout(entries)
        entries_layout.setContentsMargins(0, 0, 0, t.SPACE_2)
        entries_layout.setSpacing(0)
        layout.addWidget(entries)

        self._section_widgets[section.file_name] = (title, purpose, entries)
        return box

    def _build_conditional_section(self) -> QWidget:
        """The one section that is worked out rather than read off disk.

        Everything above is a file this system has already been told to accept.
        This is the opposite question — what would it refuse *next*, if a flag
        were turned on — so it is computed, arrives late, and offers no line to
        remove.
        """
        box = QFrame()
        box.setObjectName("maskSection")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, t.SPACE_3)
        header_layout.setSpacing(t.SPACE_3)
        self._conditional_title = QLabel()
        self._conditional_title.setObjectName("maskSectionTitle")
        header_layout.addWidget(self._conditional_title)
        self._conditional_purpose = QLabel()
        self._conditional_purpose.setProperty("role", "caption")
        self._conditional_purpose.setWordWrap(True)
        header_layout.addWidget(self._conditional_purpose, 1)
        layout.addWidget(header)

        self._conditional_entries = QWidget()
        entries_layout = QVBoxLayout(self._conditional_entries)
        entries_layout.setContentsMargins(0, 0, 0, t.SPACE_2)
        entries_layout.setSpacing(0)
        layout.addWidget(self._conditional_entries)
        return box

    # -- contents ----------------------------------------------------------

    def activated(self) -> None:
        self.reload()

    def reload(self) -> None:
        """Re-read every file. Cheap enough to do on every visit."""
        for section in SECTIONS:
            _title, _purpose, container = self._section_widgets[section.file_name]
            layout = container.layout()
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget() if item is not None else None
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()

            try:
                entries = confedit.read_entries(section.file_name)
            except Exception:  # pragma: no cover - unreadable /etc/portage
                log.warning("Could not read %s", section.file_name, exc_info=True)
                entries = ()

            if not entries:
                empty = QLabel()
                empty.setProperty("role", "caption")
                empty.setContentsMargins(t.SPACE_4, 0, t.SPACE_4, t.SPACE_2)
                empty.setText(self.tr("No entries."))
                layout.addWidget(empty)
                continue

            for path, line in entries:
                layout.addWidget(_EntryRow(self, section.file_name, path, line))

        self._reload_conditional()
        self.retranslate_ui()

    # -- licences that depend on a flag ------------------------------------

    def _reload_conditional(self) -> None:
        """Ask a worker for the scan; the section says so until it answers."""
        self._conditional = None
        self._rebuild_conditional()
        run_async(load_conditional, self._on_conditional, self._on_conditional_failed)

    def _on_conditional(self, result: object) -> None:
        self._conditional = tuple(result) if isinstance(result, tuple) else ()
        self._rebuild_conditional()
        self.retranslate_ui()

    def _on_conditional_failed(self, error: Exception) -> None:
        log.warning("Could not work out which licences depend on a flag: %s", error)
        self._conditional = ()
        self._rebuild_conditional()
        self.retranslate_ui()

    def _rebuild_conditional(self) -> None:
        layout = self._conditional_entries.layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        if self._conditional is None:
            waiting = QLabel(self.tr("Reading every ebuild's LICENSE…"))
            waiting.setProperty("role", "caption")
            waiting.setContentsMargins(t.SPACE_4, 0, t.SPACE_4, t.SPACE_2)
            layout.addWidget(waiting)
            return

        if not self._conditional:
            empty = QLabel(self.tr("Nothing here changes its licence with a flag."))
            empty.setProperty("role", "caption")
            empty.setContentsMargins(t.SPACE_4, 0, t.SPACE_4, t.SPACE_2)
            layout.addWidget(empty)
            return

        for entry in self._conditional:
            layout.addWidget(_ConditionalRow(self, entry))

    def open_package(self, cp: str) -> None:
        """Show *cp* on the package screen, the way the menu's search does."""
        window = self.window()
        if not hasattr(window, "set_page"):  # pragma: no cover - defensive
            return
        window.set_page("search")
        page = window.stack.currentWidget()
        if hasattr(page, "set_query"):
            page.set_query(cp)

    def condition_text(self, condition: LicenceCondition) -> str:
        """``rar`` → ``turning rar on also means accepting unRAR``."""
        licences = ", ".join(condition.licences)
        if condition.when_enabled:
            return self.tr("Turning {flag} on also means accepting {licences}").format(
                flag=condition.flag, licences=licences
            )
        return self.tr("Turning {flag} off also means accepting {licences}").format(
            flag=condition.flag, licences=licences
        )

    # -- removing ----------------------------------------------------------

    def arm_removal(self, file_name: str, atom: str) -> None:
        """Show the line that would go. Clicking "Remove…" never writes."""
        self._plan = confedit.plan_removal(
            file_name, confedit.cp_from_atom(atom), atom
        )
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
            self._preview.report_success(
                self.tr("Removed the line from {path}.").format(
                    path=(getattr(result, "data", {}) or {}).get("path", "")
                )
            )
            self.context.reload_portage()
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
        log.error("Removing the entry failed: %s", error)
        self._preview.report_failure(str(error))

    # -- i18n --------------------------------------------------------------

    def _purpose_text(self, key: str) -> str:
        return {
            "keywords": self.tr(
                "Versions accepted despite not being marked stable for this architecture."
            ),
            "unmask": self.tr("Versions installed despite a developer having masked them."),
            "licence": self.tr("Licences accepted for one package rather than system-wide."),
            "mask": self.tr("Versions you have blocked yourself."),
        }[key]

    def retranslate_ui(self) -> None:
        self._heading.setText(self.spec.title)
        self._settings.setText(self._settings_text())
        for section in SECTIONS:
            title, purpose, _entries = self._section_widgets[section.file_name]
            title.setText(section.file_name)
            purpose.setText(self._purpose_text(section.key))

        self._conditional_title.setText(self.tr("Licences that depend on a USE flag"))
        self._conditional_purpose.setText(
            self.tr(
                "Not a file — worked out. These packages carry a licence you have not "
                "accepted, hidden behind a flag that is currently off. Nothing is wrong "
                "with them today; turn the flag on and the install stops."
            )
        )
        self._preview.retranslate_ui()

    def _settings_text(self) -> str:
        try:
            from ...core.licenses import accept_license  # noqa: PLC0415 — needs Portage

            keywords = self.context.settings_summary_keywords()
            licences = accept_license() or self.tr("empty")
        except Exception:  # pragma: no cover - Portage unavailable
            return ""
        return f"ACCEPT_KEYWORDS={keywords}   ·   ACCEPT_LICENSE={licences}"
