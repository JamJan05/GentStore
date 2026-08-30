"""One USE flag, with room to explain itself.

Collapsed it is a checkbox, a name, where the value came from and a one-line
description — dense enough that forty of them fit on a screen. Expanded it
answers the question the handbook does not: *what changes if I tick this?*

That answer is assembled from Portage's own data (the description, the
dependencies the flag pulls in, the packages it forces the flag onto) using
sentence templates that go through ``tr()``. The templates are ours and are
translated; the atoms and flag names inside them are not, because they are the
strings the user would type into a terminal.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ...core.depgraph_hints import FlagEffect
from ...core.useflags import DescriptionSource, FlagLock, FlagSource, UseFlag
from ..theme import tokens as t
from .clickable_label import ClickableLabel

#: How many pulled-in atoms to list before saying "and N more".
_MAX_ATOMS = 8


class UseFlagRow(QFrame):
    """A single flag: state, provenance, description, and an expandable panel."""

    toggled = pyqtSignal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("useFlagRow")
        self._flag: UseFlag | None = None
        self._effect: FlagEffect | None = None
        self._required = False
        self._expanded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.SPACE_3, t.SPACE_2, t.SPACE_3, t.SPACE_2)
        layout.setSpacing(t.SPACE_1)

        top = QHBoxLayout()
        top.setSpacing(t.SPACE_3)

        self._box = QCheckBox()
        self._box.toggled.connect(self._on_toggled)
        top.addWidget(self._box)

        self._name = QLabel()
        self._name.setObjectName("useFlagName")
        top.addWidget(self._name)

        self._origin = QLabel()
        self._origin.setObjectName("useFlagOrigin")
        top.addWidget(self._origin)

        self._note = QLabel()
        self._note.setProperty("role", "caption")
        top.addWidget(self._note)
        top.addStretch(1)

        self._toggle_details = ClickableLabel()
        self._toggle_details.setProperty("role", "mono-accent")
        self._toggle_details.clicked.connect(self._flip)
        top.addWidget(self._toggle_details)
        layout.addLayout(top)

        self._description = QLabel()
        self._description.setProperty("role", "caption")
        self._description.setWordWrap(True)
        self._description.setContentsMargins(t.SPACE_6 + t.SPACE_3, 0, 0, 0)
        layout.addWidget(self._description)

        self._details = QWidget()
        self._details.setObjectName("useFlagDetails")
        details = QVBoxLayout(self._details)
        details.setContentsMargins(t.SPACE_6 + t.SPACE_3, t.SPACE_2, t.SPACE_3, t.SPACE_2)
        details.setSpacing(t.SPACE_2)

        self._effect_on = QLabel()
        self._effect_on.setWordWrap(True)
        self._effect_on.setProperty("role", "body")
        details.addWidget(self._effect_on)

        self._effect_off = QLabel()
        self._effect_off.setWordWrap(True)
        self._effect_off.setProperty("role", "body")
        details.addWidget(self._effect_off)

        self._effect_propagate = QLabel()
        self._effect_propagate.setWordWrap(True)
        self._effect_propagate.setProperty("role", "body")
        details.addWidget(self._effect_propagate)

        self._provenance = QLabel()
        self._provenance.setProperty("role", "mono")
        details.addWidget(self._provenance)

        self._details.hide()
        layout.addWidget(self._details)

    # -- contents ----------------------------------------------------------

    def set_flag(self, flag: UseFlag, effect: FlagEffect | None, required: bool) -> None:
        """Show *flag*. *required* means it appears in ``REQUIRED_USE``."""
        self._flag = flag
        self._effect = effect
        self._required = required

        self._box.blockSignals(True)
        self._box.setChecked(flag.enabled)
        self._box.setEnabled(not flag.is_locked)
        self._box.blockSignals(False)

        self.setProperty("locked", "yes" if flag.is_locked else "no")
        # A locked flag is never "changed by you": use.force and use.mask win
        # over package.use, so whatever it differs from, it was not the user.
        overridden = flag.is_overridden and not flag.is_locked
        self.setProperty("changed", "yes" if overridden else "no")
        self.retranslate_ui()

    @property
    def flag_name(self) -> str:
        return self._flag.name if self._flag is not None else ""

    def set_checked(self, checked: bool) -> None:
        self._box.blockSignals(True)
        self._box.setChecked(checked)
        self._box.blockSignals(False)

    def _on_toggled(self, checked: bool) -> None:
        if self._flag is not None:
            self.toggled.emit(self._flag.name, checked)

    def _flip(self) -> None:
        self._expanded = not self._expanded
        self._details.setVisible(self._expanded)
        self._toggle_details.setText(self._expand_label())

    # -- the sentences -----------------------------------------------------

    def _expand_label(self) -> str:
        return self.tr("Collapse") if self._expanded else self.tr("What does this change?")

    def _origin_text(self, flag: UseFlag) -> str:
        """The badge saying who decided this flag."""
        return {
            FlagSource.EBUILD: self.tr("ebuild default"),
            FlagSource.PROFILE: self.tr("profile"),
            FlagSource.MAKE_CONF: self.tr("make.conf"),
            FlagSource.PACKAGE_USE: self.tr("per package"),
            FlagSource.ENVIRONMENT: self.tr("environment"),
            FlagSource.DEFAULT_OFF: self.tr("off by default"),
        }[flag.source]

    def _note_text(self, flag: UseFlag) -> str:
        if flag.lock is FlagLock.FORCED:
            return (
                self.tr("locked on by the profile")
                if flag.lock_scope == "profile"
                else self.tr("locked on for this package")
            )
        if flag.lock is FlagLock.MASKED:
            return (
                self.tr("masked by the profile")
                if flag.lock_scope == "profile"
                else self.tr("masked for this package")
            )
        if flag.is_overridden:
            return self.tr("changed by you")  # locks were handled above
        if self._required:
            return self.tr("named in REQUIRED_USE")
        return ""

    def _atom_list(self, atoms: tuple[str, ...]) -> str:
        shown = list(atoms[:_MAX_ATOMS])
        text = ", ".join(shown)
        if len(atoms) > _MAX_ATOMS:
            text += " " + self.tr("and %n more", "", len(atoms) - _MAX_ATOMS)
        return text

    def _fill_details(self, flag: UseFlag) -> None:
        effect = self._effect

        pulls = tuple(item.atom for item in effect.pulls_in) if effect else ()
        if pulls:
            self._effect_on.setText(
                self.tr("With {flag} on, this also installs: {atoms}").format(
                    flag=flag.name, atoms=self._atom_list(pulls)
                )
            )
        else:
            self._effect_on.setText(
                self.tr("{flag} adds no extra packages — it only changes how this "
                        "one is built.").format(flag=flag.name)
            )
        self._effect_on.setVisible(True)

        off = tuple(item.atom for item in effect.pulls_in_when_off) if effect else ()
        self._effect_off.setText(
            self.tr("With {flag} off, it installs instead: {atoms}").format(
                flag=flag.name, atoms=self._atom_list(off)
            )
        )
        self._effect_off.setVisible(bool(off))

        propagates = effect.propagates_to if effect else ()
        self._effect_propagate.setText(
            self.tr(
                "These have to carry the same setting, so changing it may rebuild "
                "them: {atoms}"
            ).format(atoms=self._atom_list(propagates))
        )
        self._effect_propagate.setVisible(bool(propagates))

        self._provenance.setText(
            {
                DescriptionSource.METADATA: self.tr("description from metadata.xml"),
                DescriptionSource.LOCAL: self.tr("description from use.local.desc"),
                DescriptionSource.GLOBAL: self.tr("description from use.desc"),
                DescriptionSource.EXPAND: self.tr("description from profiles/desc"),
                DescriptionSource.NONE: self.tr("no description in the repository"),
            }[flag.description_source]
        )

    # -- i18n --------------------------------------------------------------

    def retranslate_ui(self) -> None:
        flag = self._flag
        if flag is None:
            return
        marker = " *" if self._required else ""
        self._name.setText(f"{flag.label}{marker}")
        self._origin.setText(self._origin_text(flag))
        self._note.setText(self._note_text(flag))
        self._description.setText(flag.description or self.tr("No description available."))
        self._toggle_details.setText(self._expand_label())
        self._fill_details(flag)

    def changeEvent(self, event: QEvent | None) -> None:  # noqa: N802 - Qt API
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)
