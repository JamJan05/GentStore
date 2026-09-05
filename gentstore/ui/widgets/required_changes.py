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

"""Everything emerge wants changed, as one set of decisions.

A masked package is a question about the package itself, and
:mod:`gentstore.ui.widgets.block_notice` answers it. This frame is for the other
case: the package is perfectly installable and a dozen things it *depends on*
are not configured the way they need to be. ``emerge --autounmask`` finds that
out while resolving the graph, refuses, and prints the lines.

It used to show them one at a time, each with its own save button, and each save
was a separate authentication. Fourteen lines for one window manager meant
fourteen password prompts to do a thing the user had already agreed to once, so
the lines are now grouped by the file they go in, ticked or unticked
individually, and written in a single privileged operation.

Grouping is presentation and nothing more. The lines are Portage's, byte for
byte; the counts come from counting; and none of it is a reason to write with
less care — the helper checks every entry again on its own side, and the exact
file and the exact line are on screen before anything is sent.

Three things are deliberately not flattened into the total.

**A mask is not a keyword.** ``~amd64`` means nobody has declared the version
stable yet, which is ordinary Gentoo. ``package.unmask`` undoes a decision a
developer wrote down on purpose, so that group is graded like
:class:`~gentstore.ui.widgets.block_notice.BlockNotice` grades it and starts
unticked.

**``**`` and ``9999`` are not routine either.** One means nobody has tested the
package on this architecture at all, the other means building whatever upstream
pushed this morning. Both are marked and both start unticked.

**A conflict alongside changes is provisional.** Portage stops backtracking the
moment autounmask has something to say, so what it reports as unresolvable was
computed before these lines existed. Saying so is more honest than either hiding
the conflict or refusing to help because of it.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.confedit import BatchPlan, cp_from_atom, plan_batch, plan_entry
from ...core.install_plan import InstallPlan, PlanGroup, PlannedEntry
from ..theme import icons
from ..theme import tokens as t

log = logging.getLogger(__name__)

def _key(entry: PlannedEntry) -> str:
    """Identifies one entry across a rebuild of the rows."""
    return f"{entry.file}\0{entry.line}"


class RequiredChanges(QFrame):
    """The ``/etc/portage`` lines emerge is waiting for, as one decision."""

    #: Apply was confirmed; the payload is the
    #: :class:`~gentstore.core.confedit.BatchPlan` to send to the helper.
    apply_requested = pyqtSignal(object)

    def __init__(
        self, parent: QWidget | None = None, config_dir: Path | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("requiredChanges")
        #: Where ``/etc/portage`` is, for working out which file a line goes in.
        #: ``None`` means the real one. It exists for the tests, which otherwise
        #: assert against whatever this machine happens to have accepted
        #: already — and it is no kind of boundary: nothing here writes, and the
        #: helper re-checks every path it is handed whatever built it
        #: (gentstore/core/confedit.py, ``_config_dir``).
        self._config_dir = config_dir
        self._plan: InstallPlan | None = None
        #: Entries the user has ticked, by :func:`_key`.
        self._selected: set[str] = set()
        #: Entries this panel has already offered. The pair is what lets a
        #: re-analysis keep the user's answers: a key that is here and not in
        #: :attr:`_selected` was unticked deliberately, and re-ticking it
        #: because it looks routine would quietly undo a decision.
        self._seen: set[str] = set()
        self._batch: BatchPlan | None = None
        self._busy = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_6, t.SPACE_4, t.SPACE_6, t.SPACE_4)
        layout.setSpacing(t.SPACE_3)

        heading = QHBoxLayout()
        heading.setSpacing(t.SPACE_3)
        self._icon = QLabel()
        heading.addWidget(self._icon)
        self._title = QLabel()
        self._title.setProperty("role", "lead")
        heading.addWidget(self._title)
        heading.addStretch(1)
        layout.addLayout(heading)

        self._explanation = QLabel()
        self._explanation.setProperty("role", "body")
        self._explanation.setWordWrap(True)
        layout.addWidget(self._explanation)

        #: Portage's own text for a graph it could not resolve, unparsed.
        self._conflict = QLabel()
        self._conflict.setObjectName("maskComment")
        self._conflict.setWordWrap(True)
        self._conflict.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._conflict.hide()
        layout.addWidget(self._conflict)

        #: One block per file, rebuilt whenever the answer changes.
        self._groups = QWidget()
        self._groups_layout = QVBoxLayout(self._groups)
        self._groups_layout.setContentsMargins(0, 0, 0, 0)
        self._groups_layout.setSpacing(t.SPACE_4)
        layout.addWidget(self._groups)

        self._held_back = QLabel()
        self._held_back.setProperty("role", "caption")
        self._held_back.setWordWrap(True)
        self._held_back.hide()
        layout.addWidget(self._held_back)

        buttons = QHBoxLayout()
        buttons.setSpacing(t.SPACE_2)
        buttons.addStretch(1)
        self._btn_lines = QPushButton()
        self._btn_lines.clicked.connect(self._on_show_lines)
        buttons.addWidget(self._btn_lines)
        self._btn_apply = QPushButton()
        self._btn_apply.setProperty("variant", "primary")
        self._btn_apply.clicked.connect(self._on_show_lines)
        buttons.addWidget(self._btn_apply)
        layout.addLayout(buttons)

        #: The second beat of preview → write → report. Nothing is sent until
        #: the exact files and the exact lines have been on screen.
        self._preview = QFrame()
        self._preview.setObjectName("writePreview")
        preview_layout = QVBoxLayout(self._preview)
        preview_layout.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, t.SPACE_3)
        preview_layout.setSpacing(t.SPACE_2)
        self._preview_title = QLabel()
        self._preview_title.setProperty("role", "subheading")
        preview_layout.addWidget(self._preview_title)
        self._preview_body = QLabel()
        self._preview_body.setObjectName("writeLine")
        self._preview_body.setWordWrap(True)
        self._preview_body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        preview_layout.addWidget(self._preview_body)
        self._preview_note = QLabel()
        self._preview_note.setProperty("role", "caption")
        self._preview_note.setWordWrap(True)
        preview_layout.addWidget(self._preview_note)
        preview_buttons = QHBoxLayout()
        preview_buttons.setSpacing(t.SPACE_2)
        preview_buttons.addStretch(1)
        self._btn_cancel = QPushButton()
        self._btn_cancel.clicked.connect(self._disarm)
        preview_buttons.addWidget(self._btn_cancel)
        self._btn_save = QPushButton()
        self._btn_save.setProperty("variant", "primary")
        self._btn_save.clicked.connect(self._on_save)
        preview_buttons.addWidget(self._btn_save)
        preview_layout.addLayout(preview_buttons)
        self._preview.hide()
        layout.addWidget(self._preview)

        self._report = QLabel()
        self._report.setObjectName("writeReport")
        self._report.setWordWrap(True)
        self._report.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._report.hide()
        layout.addWidget(self._report)

        self.hide()

    # -- contents ----------------------------------------------------------

    def set_plan(self, plan: InstallPlan | None) -> None:
        """Show *plan*, or hide the frame when there is nothing to say.

        Nothing to say means exactly that: no lines wanted and no conflict. A
        plan that could not be read is not nothing — it hides here and keeps the
        install gate shut in :mod:`gentstore.ui.pages.search`, which is where
        the two halves of "we do not know" belong together.
        """
        self._plan = plan
        self._disarm()
        self._report.hide()

        if plan is None or (not plan.groups and not plan.conflicts):
            self._selected.clear()
            self._seen.clear()
            self.hide()
            return

        known = {_key(entry) for entry in plan.entries}
        # Answers survive a re-analysis; answers about lines nobody is asking
        # for any more do not.
        self._selected &= known
        self._seen &= known
        for group in plan.groups:
            for entry in group.entries:
                key = _key(entry)
                if key in self._seen:
                    continue
                self._seen.add(key)
                if self._starts_ticked(entry, group):
                    self._selected.add(key)
        self.show()
        self.retranslate_ui()

    def clear(self) -> None:
        self._seen.clear()
        self.set_plan(None)

    @staticmethod
    def _starts_ticked(entry: PlannedEntry, group: PlanGroup) -> bool:
        """Whether this line is ordinary enough to be ticked for the user.

        Unticked means "say yes to this one yourself". Three cases earn it: a
        mask somebody wrote on purpose, a ``**`` keyword for an architecture the
        package has never been tested on, and a live ebuild. Everything else is
        the ordinary business of running newer software on Gentoo, and making a
        person tick fourteen boxes to say so is the tedium this frame exists to
        remove.
        """
        return not group.is_unmask and entry.is_ordinary

    # -- reading the state -------------------------------------------------

    @property
    def selected(self) -> tuple[PlannedEntry, ...]:
        if self._plan is None:
            return ()
        return tuple(
            entry for entry in self._plan.entries if _key(entry) in self._selected
        )

    @property
    def batch(self) -> BatchPlan | None:
        """The batch shown in the preview, once it has been built."""
        return self._batch

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.retranslate_ui()

    def report_success(self, message: str) -> None:
        self._show_report(message, "ok")

    def report_failure(self, message: str) -> None:
        self._show_report(message, "err")

    def _show_report(self, message: str, state: str) -> None:
        self._busy = False
        self._report.setProperty("state", state)
        self._report.setText(message)
        self._report.show()
        style = self._report.style()
        if style is not None:
            style.unpolish(self._report)
            style.polish(self._report)
        self._report.update()
        self.retranslate_ui()

    # -- arming ------------------------------------------------------------

    def _build_batch(self) -> BatchPlan:
        """Turn the ticked entries into plans, and the plans into one batch.

        The plans are made here rather than when the rows are drawn because
        making one reads ``/etc/portage``: which file the entry belongs in
        depends on what is already there, and what is already there changes
        under this window every time something is written.
        """
        return plan_batch(
            plan_entry(
                entry.file,
                cp_from_atom(entry.atom),
                entry.atom,
                entry.tokens,
                config_dir=self._config_dir,
            )
            for entry in self.selected
        )

    def _on_show_lines(self) -> None:
        """Show the exact files and lines. Pressing this never writes."""
        self._batch = self._build_batch()
        self._report.hide()
        self.retranslate_ui()

    def _disarm(self) -> None:
        self._batch = None
        self._busy = False
        self._preview.hide()

    def _on_save(self) -> None:
        if self._batch is not None and not self._batch.is_empty:
            self.apply_requested.emit(self._batch)

    def _on_entry_toggled(self, entry: PlannedEntry, checked: bool) -> None:
        if checked:
            self._selected.add(_key(entry))
        else:
            self._selected.discard(_key(entry))
        # The preview described a different set of lines a moment ago.
        self._disarm()
        self.retranslate_ui()

    def _on_group_toggled(self, group: PlanGroup, checked: bool) -> None:
        for entry in group.entries:
            if checked:
                self._selected.add(_key(entry))
            else:
                self._selected.discard(_key(entry))
        self._disarm()
        self.retranslate_ui()

    # -- wording -----------------------------------------------------------

    def _group_title(self, group: PlanGroup) -> str:
        """What the file is called in a sentence, rather than on disk.

        Written out as four literal calls rather than looked up in a mapping:
        ``pylupdate6`` reads the sources for ``tr()`` with a literal inside it
        and finds nothing to translate in ``self.tr(name)`` (Docs/03-i18n.md).
        """
        names = {
            "package.accept_keywords": self.tr("Keywords"),
            "package.license": self.tr("Licences"),
            "package.use": self.tr("USE flags"),
            "package.unmask": self.tr("Unmasking"),
        }
        return f"{names.get(group.file, group.file)} ({len(group)})"

    def _entry_reason(self, entry: PlannedEntry) -> str:
        """Who asked for this line, nearest first.

        The chain matters more here than anywhere else on the screen: nothing is
        wrong with the package the user chose, and the demand comes from a
        dependency they have very likely never heard of. Two links are enough to
        make that clear; the rest is emerge talking to itself.
        """
        if not entry.reasons:
            return ""
        chain = " → ".join(entry.reasons[:2])
        return self.tr("Asked for by {chain}").format(chain=chain)

    def _entry_marker(self, entry: PlannedEntry) -> str:
        if entry.is_unkeyworded:
            return self.tr("** — not tested on this architecture at all")
        if entry.is_live:
            return self.tr("live ebuild — builds whatever upstream has today")
        return ""

    def _explanation_text(self, plan: InstallPlan) -> str:
        if not plan.groups:
            return self.tr(
                "Portage could not find a set of packages that fits together, and "
                "has no change to suggest for this one. Its own account is below. "
                "A block usually involves something already installed, and Portage "
                "only proposes changes for the package it was asked about — so "
                "there may well be an entry that settles this, further up the "
                "chain, and this screen is not the thing that will find it."
            )
        if plan.is_provisional:
            return self.tr(
                "Portage stopped before building anything: it needs these lines in "
                "your configuration first. It also reported a conflict, but it "
                "stopped working on the graph as soon as it found these changes, so "
                "that conflict was worked out without them. Applying the lines and "
                "looking again is the way to find out whether it is real."
            )
        if plan.conflicts:
            return self.tr(
                "Portage needs these lines in your configuration, and it also "
                "reported a conflict it worked out in full. Writing the lines will "
                "not settle that on its own; the analysis after them will say where "
                "it stands."
            )
        return self.tr(
            "Portage stopped before building anything because it needs these lines "
            "in your configuration first. Each one is shown with the package that "
            "asked for it. Nothing is written until you have seen the exact lines."
        )

    def _held_back_text(self, batch: BatchPlan) -> str:
        """The lines that are not in the batch, and why they are not.

        Both of these are quiet by nature — nothing failed and nothing is wrong
        — which is exactly why they are said out loud. A ticked line that simply
        does not appear in the preview would be the one thing this frame must
        never do.
        """
        parts = []
        if batch.needs_replacement:
            parts.append(
                self.tr(
                    "%n line(s) would replace an entry you already have for the same "
                    "atom, which is a change to make on purpose rather than in a "
                    "batch.",
                    "",
                    len(batch.needs_replacement),
                )
            )
        if batch.already_present:
            parts.append(
                self.tr(
                    "%n line(s) are already in your configuration.",
                    "",
                    len(batch.already_present),
                )
            )
        return "\n".join(parts)

    # -- drawing -----------------------------------------------------------

    def _clear_groups(self) -> None:
        while self._groups_layout.count():
            item = self._groups_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

    def _build_group(self, group: PlanGroup) -> QWidget:
        block = QWidget()
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(t.SPACE_2)

        header = QHBoxLayout()
        header.setSpacing(t.SPACE_3)
        ticked = [entry for entry in group.entries if _key(entry) in self._selected]
        box = QCheckBox(self._group_title(group))
        box.setTristate(False)
        box.setChecked(len(ticked) == len(group.entries))
        box.toggled.connect(
            lambda checked, g=group: self._on_group_toggled(g, checked)
        )
        header.addWidget(box)
        header.addStretch(1)
        target = QLabel(group.file)
        target.setProperty("role", "caption")
        header.addWidget(target)
        block_layout.addLayout(header)

        if group.is_unmask:
            warning = QLabel(
                self.tr(
                    "A developer masked these on purpose and wrote down why. "
                    "Unmasking is not routine; tick them one at a time."
                )
            )
            warning.setProperty("role", "caption")
            warning.setWordWrap(True)
            block_layout.addWidget(warning)

        for entry in group.entries:
            block_layout.addWidget(self._build_entry(entry))
        return block

    def _build_entry(self, entry: PlannedEntry) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(t.SPACE_4, 0, 0, 0)
        row_layout.setSpacing(t.SPACE_3)

        box = QCheckBox()
        box.setChecked(_key(entry) in self._selected)
        box.toggled.connect(
            lambda checked, e=entry: self._on_entry_toggled(e, checked)
        )
        row_layout.addWidget(box, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(t.SPACE_1)
        line = QLabel(entry.line)
        line.setProperty("role", "mono")
        line.setWordWrap(True)
        line.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text.addWidget(line)
        for caption in (self._entry_marker(entry), self._entry_reason(entry)):
            if not caption:
                continue
            label = QLabel(caption)
            label.setProperty("role", "caption")
            label.setWordWrap(True)
            text.addWidget(label)
        row_layout.addLayout(text, 1)
        return row

    def _preview_text(self, batch: BatchPlan) -> str:
        """Every file and every line, grouped the way they will be written."""
        blocks = []
        for path in batch.paths:
            lines = [plan.line for plan in batch.appends if plan.path == path]
            body = "\n".join(f"+ {line}" for line in lines)
            blocks.append(f"{path}\n{body}")
        return "\n\n".join(blocks)

    def retranslate_ui(self) -> None:
        plan = self._plan
        if plan is None:
            return

        size = max(14, round(self.fontMetrics().height() * 1.05))
        self._icon.setPixmap(
            icons.tinted_pixmap("shield-warning", t.WARN, size, self.devicePixelRatioF())
        )
        self._title.setText(
            self.tr("Portage cannot resolve this")
            if not plan.groups
            else self.tr("Emerge needs %n change(s) first", "", len(plan))
        )
        self._explanation.setText(self._explanation_text(plan))

        if plan.conflicts:
            self._conflict.setText("\n".join(plan.conflicts))
            self._conflict.show()
        else:
            self._conflict.hide()

        self._clear_groups()
        for group in plan.groups:
            self._groups_layout.addWidget(self._build_group(group))

        self._btn_lines.setText(self.tr("Show exact lines"))
        self._btn_apply.setText(self.tr("Apply selected changes"))
        has_selection = bool(self._selected)
        for button in (self._btn_lines, self._btn_apply):
            button.setVisible(bool(plan.groups))
            button.setEnabled(has_selection and not self._busy)

        batch = self._batch
        if batch is None:
            self._preview.hide()
            self._held_back.hide()
            return

        note = self._held_back_text(batch)
        self._held_back.setText(note)
        self._held_back.setVisible(bool(note))

        self._preview.show()
        self._preview_title.setText(self.tr("Will be written"))
        self._preview_body.setText(
            self._preview_text(batch)
            if not batch.is_empty
            else self.tr("Nothing left to write — see the note above.")
        )
        self._preview_note.setText(
            self.tr(
                "%n line(s) will be added, in one privileged operation, after one "
                "password. Everything else in those files is left alone.",
                "",
                len(batch),
            )
        )
        self._btn_cancel.setText(self.tr("Cancel"))
        self._btn_cancel.setEnabled(not self._busy)
        self._btn_save.setText(self.tr("Saving…") if self._busy else self.tr("Save"))
        self._btn_save.setEnabled(not self._busy and not batch.is_empty)

    def changeEvent(self, event: QEvent | None) -> None:  # noqa: N802 - Qt API
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
