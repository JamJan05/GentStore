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

"""The USE flag card: every flag, the rules that constrain them, and the write.

It owns the whole interaction rather than leaving it spread across the screen,
because the three parts are one thought: ticking a box changes which
``REQUIRED_USE`` rules hold, and that decides whether the line at the bottom may
be written at all.

Everything is recomputed on every toggle. That sounds wasteful and is not —
evaluating the rules is a walk over a handful of nodes, and working out the line
is a few stat calls — and it means there is no cached state to fall out of step
with the checkboxes.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ...core import required_use as ru
from ...core.confedit import WritePlan, plan_package_use
from ...core.useflags import UsePicture, UseState
from ..theme import icons
from ..theme import tokens as t
from .use_flag_row import UseFlagRow
from .write_preview import WritePreview

log = logging.getLogger(__name__)


class _RequirementRow(QWidget):
    """One ``REQUIRED_USE`` rule with a tick or a cross beside it."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(t.SPACE_3)

        self._icon = QLabel()
        layout.addWidget(self._icon)

        self._expression = QLabel()
        self._expression.setObjectName("requirementExpression")
        self._expression.setWordWrap(True)
        self._expression.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._expression, 1)

        self._note = QLabel()
        self._note.setProperty("role", "caption")
        layout.addWidget(self._note)

    def set_requirement(self, requirement: ru.Requirement, note: str) -> None:
        if not requirement.applies:
            name, colour = "square", t.NEUTRAL_700
        elif requirement.satisfied:
            name, colour = "check", t.OK
        else:
            name, colour = "warning", t.ERR
        size = max(12, round(self.fontMetrics().height() * 0.85))
        self._icon.setPixmap(icons.tinted_pixmap(name, colour, size, self.devicePixelRatioF()))
        self._expression.setText(requirement.expression)
        self._expression.setProperty("state", "err" if requirement.is_broken else "")
        style = self._expression.style()
        if style is not None:
            style.unpolish(self._expression)
            style.polish(self._expression)
        self._note.setText(note)


class UseFlagsPanel(QFrame):
    """Flags, rules and the pending write, for one package."""

    #: The user pressed Save; the payload is the :class:`WritePlan`.
    write_requested = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("useFlagsPanel")
        self._picture: UsePicture | None = None
        self._desired: dict[str, bool] = {}
        self._rows: dict[str, UseFlagRow] = {}
        self._requirement_rows: list[_RequirementRow] = []
        self._plan: WritePlan | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("useFlagsHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, t.SPACE_3)
        header_layout.setSpacing(t.SPACE_3)
        self._title = QLabel()
        self._title.setProperty("role", "subheading")
        header_layout.addWidget(self._title)
        self._summary = QLabel()
        self._summary.setProperty("role", "mono")
        header_layout.addWidget(self._summary)
        header_layout.addStretch(1)
        layout.addWidget(header)

        self._requirements = QWidget()
        self._requirements.setObjectName("requirementsBlock")
        self._requirements_layout = QVBoxLayout(self._requirements)
        self._requirements_layout.setContentsMargins(
            t.SPACE_4, t.SPACE_3, t.SPACE_4, t.SPACE_3
        )
        self._requirements_layout.setSpacing(t.SPACE_2)
        self._requirements_title = QLabel()
        self._requirements_title.setProperty("role", "section")
        self._requirements_layout.addWidget(self._requirements_title)
        self._requirements.hide()
        layout.addWidget(self._requirements)

        self._flags = QWidget()
        self._flags_layout = QVBoxLayout(self._flags)
        self._flags_layout.setContentsMargins(0, 0, 0, 0)
        self._flags_layout.setSpacing(0)
        layout.addWidget(self._flags)

        self._preview = WritePreview()
        self._preview.save_requested.connect(self._on_save)
        self._preview.reset_requested.connect(self.reset)
        layout.addWidget(self._preview)

        self.retranslate_ui()
        self.hide()

    # -- contents ----------------------------------------------------------

    def set_picture(self, picture: UsePicture | None) -> None:
        """Show the flags of one package, or nothing."""
        self._picture = picture
        self._clear_rows()
        if picture is None or not picture.state.flags:
            self.hide()
            return

        self._desired = {flag.name: flag.enabled for flag in picture.state.flags}
        self._build_rows(picture)
        self.show()
        self._refresh()

    def reset(self) -> None:
        """Put every checkbox back to what Portage currently says."""
        if self._picture is None:
            return
        self._desired = {flag.name: flag.enabled for flag in self._picture.state.flags}
        for name, row in self._rows.items():
            row.set_checked(self._desired[name])
        self._refresh()

    def set_busy(self, busy: bool) -> None:
        self._preview.set_busy(busy)

    def report_success(self, message: str) -> None:
        self._preview.report_success(message)

    def report_failure(self, message: str) -> None:
        self._preview.report_failure(message)

    @property
    def plan(self) -> WritePlan | None:
        return self._plan

    # -- building ----------------------------------------------------------

    def _clear_rows(self) -> None:
        self._rows.clear()
        self._requirement_rows.clear()
        for layout in (self._flags_layout, self._requirements_layout):
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget() if item is not None else None
                if widget is not None and widget is not self._requirements_title:
                    widget.setParent(None)
                    widget.deleteLater()
        self._requirements_layout.addWidget(self._requirements_title)

    def _build_rows(self, picture: UsePicture) -> None:
        required = self._required_flags(picture.state)
        for group, flags in picture.state.grouped():
            if not flags:
                continue
            if group:
                heading = QLabel(group)
                heading.setProperty("role", "section")
                heading.setContentsMargins(t.SPACE_4, t.SPACE_3, t.SPACE_4, 0)
                self._flags_layout.addWidget(heading)
            for flag in flags:
                row = UseFlagRow()
                row.set_flag(flag, picture.effects.get(flag.name), flag.name in required)
                row.toggled.connect(self._on_flag_toggled)
                self._rows[flag.name] = row
                self._flags_layout.addWidget(row)

    @staticmethod
    def _required_flags(state: UseState) -> frozenset[str]:
        try:
            nodes = ru.parse(state.required_use)
        except ru.RequiredUseError:
            return frozenset()
        return frozenset().union(*(node.flags() for node in nodes)) if nodes else frozenset()

    # -- reacting ----------------------------------------------------------

    def _on_flag_toggled(self, name: str, enabled: bool) -> None:
        self._desired[name] = enabled
        self._refresh()

    def _refresh(self) -> None:
        picture = self._picture
        if picture is None:
            return
        state = picture.state
        enabled = {name for name, value in self._desired.items() if value}

        broken = self._refresh_requirements(state, enabled)
        self._plan = plan_package_use(state, dict(self._desired))
        self._preview.set_plan(
            self._plan,
            blocked_reason=self.tr(
                "REQUIRED_USE is not satisfied. Portage would refuse this combination, "
                "so there is nothing worth writing yet."
            )
            if broken
            else "",
        )
        self._refresh_summary(state)

    def _refresh_requirements(self, state: UseState, enabled: set[str]) -> bool:
        try:
            requirements = ru.check(state.required_use, enabled)
        except ru.RequiredUseError as exc:
            log.warning("Could not parse REQUIRED_USE of %s: %s", state.cpv, exc)
            self._requirements.hide()
            return False

        if not requirements:
            self._requirements.hide()
            return False

        while len(self._requirement_rows) < len(requirements):
            row = _RequirementRow()
            self._requirement_rows.append(row)
            self._requirements_layout.addWidget(row)

        for row, requirement in zip(self._requirement_rows, requirements, strict=False):
            row.set_requirement(requirement, self._requirement_note(requirement))
            row.show()
        for row in self._requirement_rows[len(requirements):]:
            row.hide()

        self._requirements.show()
        return any(requirement.is_broken for requirement in requirements)

    def _requirement_note(self, requirement: ru.Requirement) -> str:
        if not requirement.applies:
            return self.tr("does not apply")
        return "" if requirement.satisfied else self.tr("not satisfied")

    def _refresh_summary(self, state: UseState) -> None:
        changed = sum(
            1
            for flag in state.flags
            if not flag.is_locked and self._desired.get(flag.name, flag.enabled) != flag.enabled
        )
        on = sum(1 for value in self._desired.values() if value)
        self._summary.setText(
            self.tr("%n flag(s) on", "", on)
            + " · "
            + self.tr("%n changed", "", changed)
        )

    def _on_save(self) -> None:
        if self._plan is not None and not self._plan.is_noop:
            self.write_requested.emit(self._plan)

    # -- i18n --------------------------------------------------------------

    def retranslate_ui(self) -> None:
        self._title.setText(self.tr("USE flags"))
        self._requirements_title.setText(self.tr("REQUIRED_USE"))
        if self._picture is not None:
            self._refresh()

    def changeEvent(self, event: QEvent | None) -> None:  # noqa: N802 - Qt API
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
