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

"""``make.conf``: what Portage uses, what this file says, and one line at a time.

Every row shows two values, and the difference between them is the point. The
*effective* value is what Portage actually uses, assembled from the profile,
``/etc/env.d`` and this file together. The *file* value is the line in
``make.conf``, if there is one. For ``MAKEOPTS`` they are the same; for
``FEATURES`` and ``USE`` they are not, and somebody who does not know that will
eventually paste the profile's entire list into their own file and wonder why
their system stops following profile updates.

Editing follows the pattern the rest of the application uses: the change is
shown as a difference against the real file before it is written, and the write
replaces one line and leaves every comment where it was.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core import makeconf
from ...core.confedit import WritePlan
from ...core.makeconf import EDITABLE, MakeConf, Suggestion
from ...runner import helper_client
from ..context import AppContext
from ..tasks import run_async
from ..theme import tokens as t
from ..widgets.clickable_label import ClickableLabel
from ..widgets.diff_view import DiffView
from ..widgets.write_preview import WritePreview
from .base import Page
from .registry import PageSpec

log = logging.getLogger(__name__)


#: A profile's USE list runs to several thousand characters. The row shows how
#: many entries there are and the first few; the whole thing is in the tooltip,
#: and the USE flag panel on the package screen is where it is actually useful.
_EFFECTIVE_PREVIEW = 140


def _shorten(value: str) -> str:
    if len(value) <= _EFFECTIVE_PREVIEW:
        return value
    words = value.split()
    kept: list[str] = []
    length = 0
    for word in words:
        if length + len(word) + 1 > _EFFECTIVE_PREVIEW:
            break
        kept.append(word)
        length += len(word) + 1
    return " ".join(kept) + f" … ({len(words)})"


class _VariableRow(QFrame):
    """One variable: what it is, what it is set to, and a field to change it."""

    edited = pyqtSignal(str, str)

    def __init__(self, page: MakeConfPage, name: str) -> None:
        super().__init__(page)
        self.setObjectName("variableRow")
        self._page = page
        self.name = name
        self._file_value = ""
        self._suggestion: Suggestion | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, t.SPACE_3)
        layout.setSpacing(t.SPACE_2)

        top = QHBoxLayout()
        top.setSpacing(t.SPACE_3)
        self._name = QLabel(name)
        self._name.setObjectName("variableName")
        top.addWidget(self._name)
        self._purpose = QLabel()
        self._purpose.setProperty("role", "caption")
        self._purpose.setWordWrap(True)
        top.addWidget(self._purpose, 1)
        layout.addLayout(top)

        self._field = QLineEdit()
        self._field.setObjectName("variableField")
        self._field.textEdited.connect(lambda text: self.edited.emit(self.name, text))
        layout.addWidget(self._field)

        self._effective = QLabel()
        self._effective.setProperty("role", "mono")
        self._effective.setWordWrap(True)
        self._effective.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._effective)

        hint = QHBoxLayout()
        hint.setSpacing(t.SPACE_3)
        self._suggest = ClickableLabel()
        self._suggest.setProperty("role", "mono-accent")
        self._suggest.clicked.connect(self._take_suggestion)
        hint.addWidget(self._suggest)
        self._suggest_why = QLabel()
        self._suggest_why.setProperty("role", "caption")
        self._suggest_why.setWordWrap(True)
        hint.addWidget(self._suggest_why, 1)
        layout.addLayout(hint)

    # -- contents ----------------------------------------------------------

    def set_state(
        self, file_value: str, effective: str, defined: bool, editable: bool
    ) -> None:
        self._file_value = file_value
        self._field.setText(file_value)
        self._field.setEnabled(editable)
        self._field.setPlaceholderText("" if defined else self.tr("not set in make.conf"))
        self._effective_value = effective
        self._defined = defined
        self._editable = editable
        self.retranslate_ui()

    def set_suggestion(self, suggestion: Suggestion | None) -> None:
        self._suggestion = suggestion
        self.retranslate_ui()

    @property
    def value(self) -> str:
        return self._field.text()

    @property
    def is_changed(self) -> bool:
        return self._field.text() != self._file_value

    def revert(self) -> None:
        self._field.setText(self._file_value)

    def _take_suggestion(self) -> None:
        if self._suggestion is not None and self._suggestion.is_available:
            self._field.setText(self._suggestion.value)
            self.edited.emit(self.name, self._suggestion.value)

    # -- wording -----------------------------------------------------------

    def retranslate_ui(self) -> None:
        self._purpose.setText(self._page.purpose(self.name))

        effective = getattr(self, "_effective_value", "")
        if effective and effective != self._file_value:
            self._effective.setText(
                self.tr("Portage uses: {value}").format(value=_shorten(effective))
            )
            self._effective.setToolTip(effective)
            self._effective.show()
        else:
            self._effective.hide()

        if not getattr(self, "_editable", True):
            self._suggest.setText("")
            self._suggest_why.setText(
                self.tr("This assignment spans several lines; Gentstore will not rewrite it.")
            )
            return

        suggestion = self._suggestion
        if suggestion is None:
            self._suggest.setText("")
            self._suggest_why.setText("")
            return
        if not suggestion.is_available:
            self._suggest.setText("")
            self._suggest_why.setText(
                self.tr("A suggestion needs {package}; it is not installed.").format(
                    package=suggestion.missing
                )
            )
            return
        self._suggest.setText(suggestion.value)
        self._suggest_why.setText(self._page.suggestion_reason(suggestion.reason))


class MakeConfPage(Page):
    """The Portage settings screen."""

    def __init__(
        self, spec: PageSpec, context: AppContext, parent: QWidget | None = None
    ) -> None:
        super().__init__(spec, context, parent)
        self._conf: MakeConf | None = None
        self._rows: dict[str, _VariableRow] = {}
        self._pending: str | None = None
        self._plan: WritePlan | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("detailPane")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("detailContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(t.SPACE_8, t.SPACE_6, t.SPACE_8, t.SPACE_8)
        layout.setSpacing(t.SPACE_4)

        self._heading = QLabel()
        self._heading.setProperty("role", "heading")
        layout.addWidget(self._heading)
        self._path = QLabel()
        self._path.setProperty("role", "mono")
        self._path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._path)
        self._note = QLabel()
        self._note.setProperty("role", "body")
        self._note.setWordWrap(True)
        layout.addWidget(self._note)

        for name in EDITABLE:
            row = _VariableRow(self, name)
            row.edited.connect(self._on_edited)
            self._rows[name] = row
            layout.addWidget(row)

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        self._diff = DiffView()
        self._diff.hide()
        outer.addWidget(self._diff)

        self._preview = WritePreview()
        self._preview.save_requested.connect(self._on_save)
        self._preview.reset_requested.connect(self._revert)
        outer.addWidget(self._preview)

        self.retranslate_ui()

    # -------------------------------------------------------------- data --

    def activated(self) -> None:
        self.reload()

    def reload(self) -> None:
        run_async(self._read, self._on_read, self._on_read_failed)

    @staticmethod
    def _read() -> tuple[MakeConf, dict[str, str], dict[str, Suggestion]]:
        conf = makeconf.load()
        effective = {name: makeconf.effective(name) for name in EDITABLE}
        suggestions = {
            "MAKEOPTS": makeconf.suggest_makeopts(),
            "CPU_FLAGS_X86": makeconf.suggest_cpu_flags(),
        }
        return conf, effective, suggestions

    def _on_read(self, result: object) -> None:
        if not isinstance(result, tuple):
            return
        conf, effective, suggestions = result
        self._conf = conf
        self._pending = None
        self._plan = None
        self._diff.hide()
        self._preview.set_plan(None)

        for name, row in self._rows.items():
            assignment = conf.get(name)
            row.set_state(
                file_value=assignment.value if assignment else "",
                effective=effective.get(name, ""),
                defined=assignment is not None,
                editable=assignment is None or assignment.is_editable,
            )
            row.set_suggestion(suggestions.get(name))
        self.retranslate_ui()

    def _on_read_failed(self, error: Exception) -> None:
        log.error("Reading make.conf failed: %s", error)

    # ------------------------------------------------------------ editing --

    def _on_edited(self, name: str, value: str) -> None:
        conf = self._conf
        if conf is None:
            return

        # One line per write, so one variable is pending at a time. Editing a
        # second one replaces the first rather than queueing it, and the field
        # of the first goes back to what the file says.
        if self._pending and self._pending != name:
            self._rows[self._pending].revert()
        self._pending = name

        try:
            plan = makeconf.plan_set(conf, name, value)
        except makeconf.UnsafeValue as refused:
            # Nothing is written and nothing is previewed: there is no line to
            # preview, which is the whole reason it was refused.
            self._plan = None
            self._diff.hide()
            self._preview.set_plan(None)
            self._preview.report_failure(str(refused))
            self._preview.show()
            return

        self._plan = plan
        if plan.is_noop:
            self._pending = None
            self._diff.hide()
            self._preview.set_plan(None)
            return

        self._diff.set_lines(makeconf.preview(conf, plan))
        self._diff.show()
        self._preview.set_plan(plan)

    def _revert(self) -> None:
        if self._pending:
            self._rows[self._pending].revert()
        self._pending = None
        self._plan = None
        self._diff.hide()
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
                self.tr("Changed one line in {path}:\n{line}").format(
                    path=data.get("path", ""), line=self._plan.line if self._plan else ""
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
        log.error("Writing make.conf failed: %s", error)
        self._preview.report_failure(str(error))

    # -------------------------------------------------------------- i18n --

    def purpose(self, name: str) -> str:
        return {
            "MAKEOPTS": self.tr("How many compiler jobs run at once."),
            "EMERGE_DEFAULT_OPTS": self.tr("Options added to every emerge command."),
            "USE": self.tr(
                "USE flags for the whole system, on top of what the profile sets."
            ),
            "ACCEPT_KEYWORDS": self.tr(
                "Which keywords count as installable. ~amd64 here puts the whole system "
                "on testing versions; a line per package is nearly always the better idea."
            ),
            "ACCEPT_LICENSE": self.tr("Which licences may be installed without asking."),
            "VIDEO_CARDS": self.tr("Which graphics drivers get built."),
            "CPU_FLAGS_X86": self.tr("Instruction sets this processor has."),
            "FEATURES": self.tr("How Portage itself behaves while building."),
            "L10N": self.tr("Which translations get installed."),
        }.get(name, "")

    def suggestion_reason(self, reason: str) -> str:
        return {
            "cores": self.tr("one job per core"),
            "memory": self.tr(
                "one job per core would need more memory than this machine has; "
                "roughly 2 GiB per job is the usual rule"
            ),
            "cpuid": self.tr("as cpuid2cpuflags reports it"),
        }.get(reason, "")

    def retranslate_ui(self) -> None:
        self._heading.setText(self.spec.title)
        self._path.setText(str(self._conf.path) if self._conf else "")
        self._note.setText(
            self.tr(
                "Changing a value here replaces one line and leaves the rest of the file "
                "exactly as it is — comments, ordering and all. The difference is shown "
                "before anything is written."
            )
        )
        for row in self._rows.values():
            row.retranslate_ui()
        self._diff.set_labels(self.tr("now"), self.tr("after this change"))
        self._preview.retranslate_ui()
