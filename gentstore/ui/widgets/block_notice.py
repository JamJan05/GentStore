"""The frame that explains why a package will not install.

It sits in the package details panel and only appears when there is something to
say. Four things, in this order: what Portage refused and in its own words, the
maintainer's note if there is one, what that means in practice, and the single
line that would change it — through the same preview → save → report the USE
flags use, because it is the same kind of decision.

The wording is graded. Accepting a ``~amd64`` keyword is ordinary Gentoo and the
frame says so plainly; unmasking something a developer masked on purpose gets a
warning and a button that does not pretend to be routine.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.confedit import WritePlan, plan_entry
from ...core.masking import Block, Blockage, BlockKind, Fix, fix_for
from ..theme import icons
from ..theme import tokens as t
from .chips import Pill
from .flow_layout import FlowWidget
from .write_preview import WritePreview

log = logging.getLogger(__name__)


class BlockNotice(QFrame):
    """Reason, explanation and the one-line fix for a blocked version."""

    #: Save was pressed; the payload is the :class:`WritePlan`.
    write_requested = pyqtSignal(object)
    #: A licence chip was clicked; the payload is the licence name.
    licence_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("blockNotice")
        self._blockage: Blockage | None = None
        self._block: Block | None = None
        self._fix: Fix | None = None
        self._plan: WritePlan | None = None
        self._armed = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(t.SPACE_6, t.SPACE_4, t.SPACE_6, t.SPACE_4)
        body_layout.setSpacing(t.SPACE_3)

        heading = QHBoxLayout()
        heading.setSpacing(t.SPACE_3)
        self._icon = QLabel()
        heading.addWidget(self._icon)
        self._title = QLabel()
        self._title.setProperty("role", "lead")
        heading.addWidget(self._title)
        self._raw = QLabel()
        self._raw.setProperty("role", "mono")
        self._raw.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        heading.addWidget(self._raw)
        heading.addStretch(1)
        body_layout.addLayout(heading)

        self._comment = QLabel()
        self._comment.setObjectName("maskComment")
        self._comment.setWordWrap(True)
        self._comment.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body_layout.addWidget(self._comment)

        self._location = QLabel()
        self._location.setProperty("role", "mono")
        self._location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body_layout.addWidget(self._location)

        self._explanation = QLabel()
        self._explanation.setProperty("role", "body")
        self._explanation.setWordWrap(True)
        body_layout.addWidget(self._explanation)

        self._licences = FlowWidget(t.SPACE_2)
        body_layout.addWidget(self._licences)

        actions = QHBoxLayout()
        actions.setSpacing(t.SPACE_3)
        self._action = QPushButton()
        self._action.clicked.connect(self._arm)
        actions.addWidget(self._action)
        self._caution = QLabel()
        self._caution.setProperty("role", "caption")
        self._caution.setWordWrap(True)
        actions.addWidget(self._caution, 1)
        body_layout.addLayout(actions)
        layout.addWidget(body)

        self._preview = WritePreview()
        self._preview.save_requested.connect(self._on_save)
        self._preview.reset_requested.connect(self._disarm)
        layout.addWidget(self._preview)

        self.hide()

    # -- contents ----------------------------------------------------------

    def set_blockage(self, blockage: Blockage | None) -> None:
        """Show the reason *blockage* gives, or hide the frame entirely."""
        self._blockage = blockage
        self._armed = False
        self._plan = None
        self._preview.set_plan(None)

        if blockage is None or not blockage.is_blocked:
            self._block = None
            self._fix = None
            self.hide()
            return

        self._block = blockage.primary
        self._fix = fix_for(self._block, blockage.cpv) if self._block else None
        self.setProperty("severity", "high" if self._block.is_serious else "normal")
        self._repolish()
        self.show()
        self.retranslate_ui()

    def set_busy(self, busy: bool) -> None:
        self._preview.set_busy(busy)

    def report_success(self, message: str) -> None:
        self._preview.report_success(message)

    def report_failure(self, message: str) -> None:
        self._preview.report_failure(message)

    @property
    def plan(self) -> WritePlan | None:
        return self._plan

    # -- the fix -----------------------------------------------------------

    def _arm(self) -> None:
        """Show the exact line. Pressing the action button never writes."""
        if self._fix is None or self._blockage is None:
            return
        self._plan = plan_entry(
            self._fix.file, self._blockage.cp, self._fix.atom, self._fix.tokens
        )
        self._armed = True
        self._preview.set_plan(self._plan)
        self.retranslate_ui()

    def _disarm(self) -> None:
        self._armed = False
        self._plan = None
        self._preview.set_plan(None)
        self.retranslate_ui()

    def _on_save(self) -> None:
        if self._plan is not None and not self._plan.is_noop:
            self.write_requested.emit(self._plan)

    def accept_licence(self, name: str) -> None:
        """Called back once the user has read a licence and agreed to it."""
        if self._blockage is None or self._block is None:
            return
        self._plan = plan_entry(
            "package.license", self._blockage.cp, f"={self._blockage.cpv}", (name,)
        )
        self._armed = True
        self._preview.set_plan(self._plan)
        self.retranslate_ui()

    # -- wording -----------------------------------------------------------

    def _icon_name(self, block: Block) -> str:
        """A failed check is a question about Gentstore, not about the package."""
        return "info" if block.kind is BlockKind.UNKNOWN else "shield-warning"

    def _title_text(self, block: Block) -> str:
        return {
            BlockKind.TESTING_KEYWORD: self.tr("Not marked stable yet"),
            BlockKind.MISSING_KEYWORD: self.tr("Never tested on this architecture"),
            BlockKind.UNSUPPORTED_ARCH: self.tr("Marked as not working here"),
            BlockKind.PACKAGE_MASK: self.tr("Masked by a developer"),
            BlockKind.LICENCE: self.tr("Licence not accepted"),
            BlockKind.OTHER: self.tr("Portage will not install this version"),
            BlockKind.UNKNOWN: self.tr("Could not be checked"),
        }[block.kind]

    def _explanation_text(self, block: Block) -> str:
        if block.kind is BlockKind.TESTING_KEYWORD:
            return self.tr(
                "The version works, but nobody has declared it stable for {keyword} yet. "
                "Running testing versions of individual packages is ordinary practice on "
                "Gentoo; the line below tells Portage that this one is fine by you."
            ).format(keyword=block.keyword.lstrip("~"))
        if block.kind is BlockKind.MISSING_KEYWORD:
            return self.tr(
                "This version carries no keyword for any architecture — which is also "
                "how every live ebuild looks, because it is built straight from the "
                "project's source repository and changes without warning. Expect to have "
                "to fix things yourself."
            )
        if block.kind is BlockKind.UNSUPPORTED_ARCH:
            return self.tr(
                "The ebuild states that this version does not work on this architecture. "
                "A line in package.accept_keywords would stop Portage refusing, but it "
                "would not make the package build."
            )
        if block.kind is BlockKind.PACKAGE_MASK:
            return self.tr(
                "Somebody decided this version should not be installed and wrote down "
                "why. Read that first: masks are usually about security holes, data loss "
                "or a package on its way out of the repository."
            )
        if block.kind is BlockKind.LICENCE:
            return self.tr(
                "ACCEPT_LICENSE in make.conf is currently {accepted}, which does not "
                "cover every licence this package carries. Read the ones below and "
                "decide for this package alone."
            ).format(accepted=self._accept_license())
        if block.kind is BlockKind.UNKNOWN:
            return self.tr(
                "Portage could not say whether this version installs, so Gentstore is "
                "not going to guess. Nothing here is necessarily wrong with the package "
                "— the check itself failed. Run emerge --pretend for this version to "
                "see Portage's own answer; the log has the details."
            )
        return self.tr("Portage gave this reason and Gentstore has nothing to add to it.")

    def _accept_license(self) -> str:
        from ...core.licenses import accept_license  # noqa: PLC0415 — needs Portage

        try:
            return accept_license() or self.tr("empty")
        except Exception:  # pragma: no cover - Portage unavailable
            return "?"

    def _action_text(self, fix: Fix) -> str:
        if fix.file == "package.unmask":
            return self.tr("Unmask anyway…")
        if fix.file == "package.license":
            return self.tr("Read the licence…")
        if fix.tokens == ("**",):
            return self.tr("Accept any keyword…")
        return self.tr("Accept {keyword}…").format(keyword=" ".join(fix.tokens))

    def _caution_text(self, fix: Fix) -> str:
        return {
            "untested-on-this-arch": self.tr(
                "** accepts this version whatever its keywords say, now and after every "
                "sync."
            ),
            "marked-broken-here": self.tr(
                "Not recommended: the ebuild says it does not work on this architecture."
            ),
            "masked-on-purpose": self.tr(
                "Not recommended: read the note above before going ahead."
            ),
            "": "",
        }[fix.caution]

    def _rebuild_licence_chips(self, block: Block) -> None:
        self._licences.clear()
        if block.kind is not BlockKind.LICENCE:
            self._licences.hide()
            return
        for name in block.licences:
            chip = Pill()
            chip.set_text(name)
            chip.clicked.connect(lambda n=name: self.licence_requested.emit(n))
            self._licences.add(chip)
        self._licences.setVisible(bool(block.licences))

    def _repolish(self) -> None:
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.update()

    def retranslate_ui(self) -> None:
        block = self._block
        if block is None:
            return

        colour = t.ERR if block.is_serious else t.WARN
        size = max(14, round(self.fontMetrics().height() * 1.05))
        self._icon.setPixmap(
            icons.tinted_pixmap(self._icon_name(block), colour, size, self.devicePixelRatioF())
        )
        self._title.setText(self._title_text(block))
        self._raw.setText(block.raw)
        self._raw.setVisible(bool(block.raw))

        self._comment.setText(block.comment)
        self._comment.setVisible(bool(block.comment))
        self._location.setText(block.location)
        self._location.setVisible(bool(block.location))

        self._explanation.setText(self._explanation_text(block))
        self._rebuild_licence_chips(block)

        fix = self._fix
        self._action.setVisible(fix is not None and not self._armed)
        self._caution.setVisible(fix is not None and not self._armed)
        if fix is not None:
            self._action.setText(self._action_text(fix))
            self._action.setProperty("variant", "danger" if not fix.advisable else "")
            self._action.setToolTip(fix.line)
            self._caution.setText(self._caution_text(fix))
            style = self._action.style()
            if style is not None:
                style.unpolish(self._action)
                style.polish(self._action)

    def changeEvent(self, event: QEvent | None) -> None:  # noqa: N802 - Qt API
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
