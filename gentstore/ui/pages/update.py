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

"""The system update screen: six steps, each one runnable on its own.

A Gentoo update is a sequence, not a button. Sync, read the news, look at what
would change, do it, clean up, deal with the configuration files it left behind.
Wrapping that in a single "Update" button would hide the two steps where a
person actually has to decide something — the preview and the cleanup — so the
sequence is laid out as it is, and every step says exactly which command it runs
and can be run by itself, in any order, as often as you like.

Nothing here decides anything on its own. The preview is read-only, the cleanup
shows its list before removing anything, and a failed step keeps the error where
it can be read instead of collapsing into "something went wrong".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...core import glsa, news
from ...core.emerge_parse import (
    Action,
    Depclean,
    Failure,
    Preview,
    find_failure,
    parse_depclean,
    parse_pretend,
)
from ...models.update import COLUMNS, MergePreviewModel, format_size
from ...runner import emerge, eselect
from ...runner.command import CommandSpec
from ..context import AppContext
from ..i18n import untranslated
from ..tasks import run_async
from ..theme import icons
from ..theme import tokens as t
from ..widgets.news_list import NewsEntry
from .registry import PageSpec
from .split_page import SplitPage

log = logging.getLogger(__name__)


class StepState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    #: Ran and found there was nothing to do.
    CLEAR = "clear"


@dataclass(frozen=True, slots=True)
class StepSpec:
    key: str
    icon: str
    #: The command this step stands for, shown next to its name.
    command: str


STEPS = (
    StepSpec("sync", "arrows-clockwise", "emaint sync -a"),
    StepSpec("news", "envelope", "eselect news read"),
    StepSpec("preview", "magnifying-glass", "emerge -pvuDN --changed-use @world"),
    StepSpec("update", "arrow-circle-up", "emerge -vuDN @world"),
    StepSpec("clean", "package", "emerge --depclean"),
    StepSpec("config", "files", "dispatch-conf"),
    StepSpec("security", "shield-warning", "glsa-check -l affected"),
)

#: Steps four and five change the system; the rest only look.
_WRITING_STEPS = frozenset({"update", "clean"})


class _StepRow(QFrame):
    """One step in the left-hand column."""

    def __init__(self, page: UpdatePage, index: int, spec: StepSpec) -> None:
        super().__init__(page)
        self.setObjectName("stepRow")
        self.spec = spec
        self._page = page
        self._state = StepState.PENDING

        layout = QHBoxLayout(self)
        layout.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, t.SPACE_3)
        layout.setSpacing(t.SPACE_3)

        self._number = QLabel("" if spec.key == "security" else str(index + 1))
        self._number.setObjectName("stepNumber")
        self._number.setFixedWidth(18)
        layout.addWidget(self._number)

        text = QVBoxLayout()
        text.setSpacing(0)
        self._title = QLabel()
        self._title.setObjectName("stepTitle")
        text.addWidget(self._title)
        self._command = QLabel(spec.command)
        self._command.setProperty("role", "mono")
        text.addWidget(self._command)
        layout.addLayout(text, 1)

        self._badge = QLabel()
        layout.addWidget(self._badge)
        self.retranslate_ui()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802, ANN001 - Qt API
        self._page.select(self.spec.key)
        super().mouseReleaseEvent(event)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "yes" if selected else "no")
        self._repolish()

    def set_state(self, state: StepState) -> None:
        self._state = state
        self.setProperty("state", state.value)
        self._repolish()
        self.retranslate_ui()

    def _repolish(self) -> None:
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.update()

    def retranslate_ui(self) -> None:
        self._title.setText(self._page.step_title(self.spec.key))
        colour, name = {
            StepState.DONE: (t.OK, "check"),
            StepState.CLEAR: (t.OK, "check"),
            StepState.FAILED: (t.ERR, "warning"),
            StepState.RUNNING: (t.ACCENT, "arrows-clockwise"),
            StepState.PENDING: (t.NEUTRAL_800, "square"),
        }[self._state]
        size = max(12, round(self.fontMetrics().height() * 0.9))
        self._badge.setPixmap(
            icons.tinted_pixmap(name, colour, size, self.devicePixelRatioF())
        )


class UpdatePage(SplitPage):
    """The six-step update, plus the security panel."""

    def __init__(
        self, spec: PageSpec, context: AppContext, parent: QWidget | None = None
    ) -> None:
        super().__init__(spec, context, parent)

        self._rows: dict[str, _StepRow] = {}
        self._panels: dict[str, int] = {}
        self._states: dict[str, StepState] = {step.key: StepState.PENDING for step in STEPS}
        self._selected = STEPS[0].key
        #: Which step the command now running belongs to.
        self._running_step: str | None = None
        #: What to do with that command's output once it finishes.
        self._collect: str | None = None

        self._preview: Preview | None = None
        self._depclean: Depclean | None = None
        self._news: tuple[news.NewsItem, ...] = ()

        self._build_steps()
        self._build_panels()

        context.command.started.connect(self._on_command_started)
        context.command.finished.connect(self._on_command_finished)
        context.command.failed.connect(self._on_command_failed)
        context.command.running_changed.connect(self._on_running_changed)

        self.retranslate_ui()
        self.select(self._selected)

    # ------------------------------------------------------------ building --

    def _build_steps(self) -> None:
        header = QFrame()
        header.setObjectName("searchHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(t.SPACE_4, t.SPACE_4, t.SPACE_4, t.SPACE_4)
        header_layout.setSpacing(t.SPACE_1)
        self._heading = QLabel()
        self._heading.setProperty("role", "subheading")
        header_layout.addWidget(self._heading)
        self._subheading = QLabel()
        self._subheading.setProperty("role", "caption")
        self._subheading.setWordWrap(True)
        header_layout.addWidget(self._subheading)
        self.list_layout.addWidget(header)

        for index, step in enumerate(STEPS):
            row = _StepRow(self, index, step)
            self._rows[step.key] = row
            self.list_layout.addWidget(row)
        self.list_layout.addStretch(1)

    def _build_panels(self) -> None:
        self._stack = QStackedWidget()
        self.detail_layout.addWidget(self._stack, 1)
        for step in STEPS:
            builder = getattr(self, f"_panel_{step.key}")
            self._panels[step.key] = self._stack.addWidget(builder())

    def _panel_frame(self, key: str) -> tuple[QWidget, QVBoxLayout]:
        """The common shell: heading, explanation, then whatever the step needs."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(t.SPACE_4)

        title = QLabel()
        title.setProperty("role", "heading")
        layout.addWidget(title)
        explanation = QLabel()
        explanation.setProperty("role", "body")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        setattr(self, f"_{key}_title", title)
        setattr(self, f"_{key}_explanation", explanation)
        return panel, layout

    def _action_button(self, layout: QVBoxLayout, key: str, slot) -> QPushButton:  # noqa: ANN001
        row = QHBoxLayout()
        row.setSpacing(t.SPACE_2)
        button = QPushButton()
        button.setProperty("variant", "primary")
        button.clicked.connect(slot)
        row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)
        setattr(self, f"_{key}_button", button)
        return button

    def _result_label(self, layout: QVBoxLayout, key: str) -> QLabel:
        label = QLabel()
        label.setProperty("role", "mono")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(label)
        setattr(self, f"_{key}_result", label)
        return label

    # -- the individual steps ---------------------------------------------

    def _panel_sync(self) -> QWidget:
        panel, layout = self._panel_frame("sync")
        self._action_button(layout, "sync", lambda: self._start("sync", eselect.sync_all()))
        self._result_label(layout, "sync")
        layout.addStretch(1)
        return panel

    def _panel_news(self) -> QWidget:
        panel, layout = self._panel_frame("news")
        self._action_button(layout, "news", self._on_mark_news_read)
        self._news_holder = QWidget()
        self._news_layout = QVBoxLayout(self._news_holder)
        self._news_layout.setContentsMargins(0, 0, 0, 0)
        self._news_layout.setSpacing(0)
        layout.addWidget(self._news_holder)
        layout.addStretch(1)
        return panel

    def _panel_preview(self) -> QWidget:
        panel, layout = self._panel_frame("preview")
        self._action_button(
            layout,
            "preview",
            lambda: self._start(
                "preview",
                emerge.update_world_pretend(binaries=self.context.use_binaries),
                "preview",
            ),
        )
        self._result_label(layout, "preview")

        self._preview_model = MergePreviewModel(self)
        self._table = QTableView()
        self._table.setObjectName("previewTable")
        self._table.setModel(self._preview_model)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COLUMNS.index("use"), QHeaderView.ResizeMode.Stretch)
        self._table.hide()
        layout.addWidget(self._table, 1)

        self._required = QLabel()
        self._required.setObjectName("maskComment")
        self._required.setWordWrap(True)
        self._required.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._required.hide()
        layout.addWidget(self._required)
        return panel

    def _panel_update(self) -> QWidget:
        panel, layout = self._panel_frame("update")
        self._action_button(layout, "update", self._on_update)
        self._result_label(layout, "update")
        self._failure = QLabel()
        self._failure.setObjectName("maskComment")
        self._failure.setWordWrap(True)
        self._failure.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._failure.hide()
        layout.addWidget(self._failure)
        layout.addStretch(1)
        return panel

    def _panel_clean(self) -> QWidget:
        panel, layout = self._panel_frame("clean")
        self._action_button(
            layout,
            "clean",
            lambda: self._start("clean", emerge.depclean_pretend(), "depclean"),
        )
        self._result_label(layout, "clean")

        row = QHBoxLayout()
        row.setSpacing(t.SPACE_2)
        self._clean_remove = QPushButton()
        self._clean_remove.setProperty("variant", "danger")
        self._clean_remove.clicked.connect(self._on_depclean)
        self._clean_remove.hide()
        row.addWidget(self._clean_remove)
        self._clean_rebuild = QPushButton()
        self._clean_rebuild.clicked.connect(
            lambda: self._start("clean", emerge.preserved_rebuild())
        )
        row.addWidget(self._clean_rebuild)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)
        return panel

    def _panel_config(self) -> QWidget:
        panel, layout = self._panel_frame("config")
        self._action_button(layout, "config", lambda: self._go_to("cfg"))
        layout.addStretch(1)
        return panel

    def _panel_security(self) -> QWidget:
        panel, layout = self._panel_frame("security")
        self._action_button(
            layout, "security", lambda: self._start("security", eselect.check_glsa(), "glsa")
        )
        self._result_label(layout, "security")
        self._security_fix = QPushButton()
        self._security_fix.setProperty("variant", "danger")
        self._security_fix.clicked.connect(
            lambda: self._start("security", eselect.fix_glsa())
        )
        self._security_fix.hide()
        layout.addWidget(self._security_fix, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return panel

    # ---------------------------------------------------------- selection --

    def select(self, key: str) -> None:
        self._selected = key
        for row_key, row in self._rows.items():
            row.set_selected(row_key == key)
        self._stack.setCurrentIndex(self._panels[key])

    def activated(self) -> None:
        self._reload_news()
        self._refresh_sync_state()

    def _go_to(self, page_id: str) -> None:
        window = self.window()
        if hasattr(window, "set_page"):
            window.set_page(page_id)

    # ----------------------------------------------------------- running --

    def _start(self, step: str, spec: CommandSpec, collect: str | None = None) -> None:
        """Run *spec* on behalf of *step*, optionally parsing its output after."""
        self._running_step = step
        self._collect = collect
        if not self.context.run(spec):
            self._running_step = None
            self._collect = None
            return
        self._set_state(step, StepState.RUNNING)

    def _set_state(self, step: str, state: StepState) -> None:
        self._states[step] = state
        self._rows[step].set_state(state)

    def _on_command_started(self, _spec: object) -> None:
        if self._running_step is None:
            # Something else on another screen started a command; our steps
            # have nothing to do with it.
            self._collect = None

    def _on_running_changed(self, running: bool) -> None:
        for key in ("sync", "news", "preview", "update", "clean", "security"):
            button = getattr(self, f"_{key}_button", None)
            if button is not None:
                button.setEnabled(not running)
        self._clean_remove.setEnabled(not running)
        self._clean_rebuild.setEnabled(not running)
        self._security_fix.setEnabled(not running)

    def _on_command_finished(self, code: int) -> None:
        step, collect = self._running_step, self._collect
        self._running_step = self._collect = None
        if step is None:
            return

        output = self.window().log_view.text() if hasattr(self.window(), "log_view") else ""
        if code != 0:
            self._set_state(step, StepState.FAILED)
            self._show_failure(output)
            return

        self._set_state(step, StepState.DONE)
        if collect == "preview":
            self._absorb_preview(output)
        elif collect == "depclean":
            self._absorb_depclean(output)
        elif collect == "glsa":
            self._absorb_glsa(output)
        elif step == "sync":
            self.context.reload_portage()
            self.context.reload_index()
            self._reload_news()
            self._refresh_sync_state()
        elif step == "news":
            self._reload_news()
        elif step in _WRITING_STEPS:
            self.context.reload_portage()
            self.context.refresh_installed()

    def _on_command_failed(self, message: str) -> None:
        step = self._running_step
        self._running_step = self._collect = None
        if step is not None:
            self._set_state(step, StepState.FAILED)
            getattr(self, f"_{step}_result").setText(message)

    def _show_failure(self, output: str) -> None:
        """Put the useful six lines of a failed run where they can be read."""
        failure = find_failure(output)
        if failure is None:
            self._failure.hide()
            return
        self._failure.setText(self._failure_text(failure))
        self._failure.show()
        if self._selected != "update":
            self.select("update")

    # ------------------------------------------------------- the outcomes --

    def _absorb_preview(self, output: str) -> None:
        preview = parse_pretend(output)
        self._preview = preview
        self._preview_model.set_rows(preview.merges)
        self._table.setVisible(bool(preview.merges))

        # Each heading with its own lines under it. They used to be gathered
        # as every heading and then every body, which reads correctly only when
        # emerge asked for exactly one kind of change.
        lines: list[str] = []
        for change in preview.required_changes:
            lines.append(change.heading)
            lines.extend(change.lines)

        # Blockers and ``!!!`` lines were parsed and then never shown. emerge
        # usually exits non-zero when it prints them and the failure panel takes
        # over — but usually is not always, and a preview that came back naming
        # a conflict must not be summarised as "nothing to do" merely because no
        # package survived into the merge list.
        lines.extend(row.raw for row in preview.blockers if row.raw)
        lines.extend(preview.problems)

        if lines:
            self._required.setText("\n".join(lines))
            self._required.show()
            self._set_state("preview", StepState.FAILED)
        else:
            self._required.hide()
            if not preview.merges:
                self._set_state("preview", StepState.CLEAR)
        self.retranslate_ui()

    def _absorb_depclean(self, output: str) -> None:
        result = parse_depclean(output)
        self._depclean = result
        self._clean_remove.setVisible(not result.is_empty)
        if result.is_empty:
            self._set_state("clean", StepState.CLEAR)
        self.retranslate_ui()

    def _absorb_glsa(self, output: str) -> None:
        report = glsa.parse(output)
        self._glsa = report
        self._security_fix.setVisible(bool(report.affected))
        self._set_state("security", StepState.CLEAR if report.is_clean else StepState.FAILED)
        self.retranslate_ui()

    # ---------------------------------------------------------- the steps --

    def _on_update(self) -> None:
        preview = self._preview
        if preview is None:
            answer = QMessageBox.question(
                self,
                self.tr("Update the system"),
                self.tr(
                    "Nothing has been previewed yet. Run step 3 first to see what would "
                    "change.\n\nRun the update anyway?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._failure.hide()
        self._start("update", emerge.update_world(binaries=self.context.use_binaries))

    def _on_depclean(self) -> None:
        """Docs/04-privileges.md §6: the full list, then the question."""
        result = self._depclean
        if result is None or result.is_empty:
            return
        listing = "\n".join(result.atoms[:20])
        if len(result.atoms) > 20:
            listing += "\n…"
        answer = QMessageBox.question(
            self,
            self.tr("Remove unused packages"),
            self.tr(
                "%n package(s) are no longer needed by anything installed:", "",
                len(result.atoms)
            )
            + f"\n\n{listing}\n\n"
            + self.tr("Remove them?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._start("clean", emerge.depclean())

    def _on_mark_news_read(self) -> None:
        writable = news.state_is_writable()
        self._start("news", eselect.read_news(privileged=not writable))

    def _reload_news(self) -> None:
        run_async(news.load, self._on_news, self._on_news_failed)

    def _on_news(self, items: object) -> None:
        if not isinstance(items, tuple):
            return
        self._news = items
        while self._news_layout.count():
            entry = self._news_layout.takeAt(0)
            widget = entry.widget() if entry is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        for item in items:
            if item.unread:
                self._news_layout.addWidget(NewsEntry(item))
        unread = len(news.unread(items))
        self._set_state("news", StepState.CLEAR if not unread else StepState.PENDING)
        self.context.sidebar_badge.emit("update", str(unread) if unread else "")
        self.retranslate_ui()

    def _on_news_failed(self, error: Exception) -> None:
        log.error("Reading the news failed: %s", error)

    def _refresh_sync_state(self) -> None:
        from ...core.repos import repository  # noqa: PLC0415 — needs Portage

        try:
            main = repository(self.context.main_repo_name())
        except Exception:  # pragma: no cover - Portage unavailable
            return
        if main is not None and main.last_sync is not None:
            self._sync_result.setText(
                self.tr("last synchronised {when}").format(
                    when=main.last_sync.strftime("%Y-%m-%d %H:%M")
                )
            )

    # -------------------------------------------------------------- i18n --

    def step_title(self, key: str) -> str:
        return {
            "sync": self.tr("Synchronise repositories"),
            "news": self.tr("Read the news"),
            "preview": self.tr("See what would change"),
            "update": self.tr("Update @world"),
            "clean": self.tr("Remove what is no longer needed"),
            "config": self.tr("Configuration files"),
            "security": self.tr("Security advisories"),
        }[key]

    def _explanations(self) -> dict[str, str]:
        return {
            "sync": self.tr(
                "Fetches the current state of every configured repository. Nothing is "
                "installed or changed — after this, Portage simply knows what exists."
            ),
            "news": self.tr(
                "Repositories ship notes when an update needs a hand. Only the ones that "
                "concern this system are listed, and each says why it does."
            ),
            "preview": self.tr(
                "Asks Portage what it would do, without doing any of it. The table below "
                "is the same list emerge prints, sorted into columns."
            ),
            "update": self.tr(
                "Builds and installs everything from the preview. The log at the bottom "
                "of the window shows the output as it happens and can stop it at any "
                "point — the same interrupt Ctrl+C sends, so Portage can tidy up."
            ),
            "clean": self.tr(
                "Finds packages nothing depends on any more. The list is always shown "
                "before anything is removed. Afterwards, @preserved-rebuild rebuilds "
                "whatever was still using a library that has just gone."
            ),
            "config": self.tr(
                "Updates leave new versions of configuration files beside the old ones "
                "rather than overwriting them. Deciding between the two is the last step."
            ),
            "security": self.tr(
                "Compares what is installed against Gentoo's security advisories."
            ),
        }

    def _failure_text(self, failure: Failure) -> str:
        hints = {
            "blocked": self.tr(
                "Two packages block each other. Usually one of them has to be removed "
                "first, or a newer version accepted."
            ),
            "slot-conflict": self.tr(
                "Two versions of the same package are wanted in one slot. Something asked "
                "for a specific version — the lines above say which."
            ),
            "use-change": self.tr(
                "A USE flag has to change first. The Search screen can write it, with the "
                "line shown before it is saved."
            ),
            "keyword-change": self.tr(
                "A version has to be accepted first. Open it on the Search screen: the "
                "block frame there writes the keyword line."
            ),
            "mask-change": self.tr("A masked version is needed. Read why it was masked first."),
            "licence-change": self.tr(
                "A licence has to be accepted first. The Search screen shows its full text."
            ),
            "required-use": self.tr(
                "The USE flags asked for are not a combination the package allows."
            ),
            "missing-dependency": self.tr(
                "Something depends on a package no repository provides. An overlay may be "
                "missing."
            ),
            "out-of-space": self.tr("The disk filled up."),
        }
        parts = []
        if failure.package:
            parts.append(self.tr("Failed: {package}").format(package=failure.package))
        if failure.hint in hints:
            parts.append(hints[failure.hint])
        if failure.log_path:
            parts.append(self.tr("Full log: {path}").format(path=failure.log_path))
        if failure.excerpt:
            parts.append("")
            parts.extend(failure.excerpt[-20:])
        return "\n".join(parts)

    def _preview_summary(self) -> str:
        preview = self._preview
        if preview is None:
            return ""
        if not preview.merges:
            return self.tr("Everything is up to date.")
        pieces = [self.tr("%n package(s)", "", len(preview.merges))]

        # Spelled out one call at a time, and deliberately so. The string
        # extractor decides a message is a plural form by looking at the shape
        # of the call in the source; the same three-argument tr() inside a dict
        # literal came out marked "not a plural", which in Polish means one
        # wrong ending out of three. Repetition here is the price of the
        # catalogue being right.
        updates = preview.count(Action.UPDATE)
        if updates:
            pieces.append(self.tr("%n to update", "", updates))
        added = preview.count(Action.NEW)
        if added:
            pieces.append(self.tr("%n new", "", added))
        rebuilt = preview.count(Action.REBUILD)
        if rebuilt:
            pieces.append(self.tr("%n to rebuild", "", rebuilt))
        downgraded = preview.count(Action.DOWNGRADE)
        if downgraded:
            pieces.append(self.tr("%n to downgrade", "", downgraded))
        if preview.binary_count:
            pieces.append(self.tr("%n binary", "", preview.binary_count))
        pieces.append(
            self.tr("download {size}").format(
                size=format_size(preview.download_size or self._preview_model.total_size())
            )
        )
        return "   ·   ".join(pieces)

    def _clean_summary(self) -> str:
        result = self._depclean
        if result is None:
            return ""
        if result.is_empty:
            return self.tr("Nothing to remove.")
        return self.tr("%n package(s) could be removed.", "", len(result.atoms))

    def _security_summary(self) -> str:
        if not glsa.is_available():
            return self.tr(
                "glsa-check is not installed. Install {package} to enable this check."
            ).format(package=glsa.PACKAGE)
        report = getattr(self, "_glsa", None)
        if report is None:
            return ""
        if report.is_clean:
            return self.tr("This system is not affected by any known advisory.")
        return "\n".join(
            f"{item.identifier}  {item.title}  ({' '.join(item.packages)})"
            for item in report.affected
        )

    def retranslate_ui(self) -> None:
        self._heading.setText(self.tr("Update"))
        self._subheading.setText(
            self.tr("Six steps. Each one runs on its own, in any order, as often as you like.")
        )

        explanations = self._explanations()
        for step in STEPS:
            getattr(self, f"_{step.key}_title").setText(self.step_title(step.key))
            getattr(self, f"_{step.key}_explanation").setText(explanations[step.key])
            self._rows[step.key].retranslate_ui()

        self._sync_button.setText(self.tr("Synchronise"))
        self._news_button.setText(
            self.tr("Mark all as read")
            if news.unread(self._news)
            else self.tr("Nothing unread")
        )
        self._news_button.setEnabled(bool(news.unread(self._news)))
        self._preview_button.setText(self.tr("Calculate"))
        self._preview_result.setText(self._preview_summary())
        self._preview_model.set_headings(
            (
                self.tr("Package"),
                self.tr("Version"),
                self.tr("USE changes"),
                self.tr("Download"),
                self.tr("binary"),
            )
        )
        self._update_button.setText(self.tr("Update now"))
        self._clean_button.setText(self.tr("Check"))
        self._clean_result.setText(self._clean_summary())
        self._clean_remove.setText(self.tr("Remove them…"))
        self._clean_rebuild.setText(self.tr("Rebuild what needs it"))
        self._clean_rebuild.setToolTip(untranslated("emerge --verbose @preserved-rebuild"))
        self._config_button.setText(self.tr("Go to configuration files"))
        self._security_button.setText(self.tr("Check"))
        self._security_button.setEnabled(glsa.is_available())
        self._security_result.setText(self._security_summary())
        self._security_fix.setText(self.tr("Apply the fixes…"))

        for step in STEPS:
            getattr(self, f"_{step.key}_button").setToolTip(step.command)
