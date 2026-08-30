"""Persistent user settings.

A thin, typed wrapper over :class:`QSettings` so the rest of the code never has
to remember a key name or guess at a default. Everything lives under
``~/.config/Gentstore/Gentstore.conf``.
"""

from __future__ import annotations

from typing import Literal

from PyQt6.QtCore import QByteArray, QSettings

Language = Literal["system", "pl", "en"]
OfficialMode = Literal["hide", "mask"]
#: How to become root. ``auto`` prefers pkexec and falls back to sudo.
Escalation = Literal["auto", "pkexec", "sudo"]
#: A directory of files, or one compressed archive.
BackupForm = Literal["directory", "archive"]

#: How many copies of /etc/portage to keep. The helper clamps this as well.
BACKUP_KEEP_DEFAULT = 10

#: Font scale presets offered in the View menu.
FONT_SCALES: tuple[float, ...] = (1.0, 1.15, 1.3)


class Settings:
    """Typed access to the application's persisted preferences."""

    def __init__(self) -> None:
        self._s = QSettings()

    # -- interface ---------------------------------------------------------

    @property
    def language(self) -> Language:
        value = str(self._s.value("ui/language", "system"))
        return value if value in ("system", "pl", "en") else "system"  # type: ignore[return-value]

    @language.setter
    def language(self, value: Language) -> None:
        self._s.setValue("ui/language", value)

    @property
    def font_scale(self) -> float:
        try:
            value = float(self._s.value("ui/fontScale", 1.0))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 1.0
        return value if value in FONT_SCALES else 1.0

    @font_scale.setter
    def font_scale(self, value: float) -> None:
        self._s.setValue("ui/fontScale", value)

    @property
    def last_page(self) -> str:
        return str(self._s.value("ui/lastPage", "search"))

    @last_page.setter
    def last_page(self, value: str) -> None:
        self._s.setValue("ui/lastPage", value)

    # -- building ----------------------------------------------------------

    @property
    def use_binaries(self) -> bool:
        """Whether to pass ``--getbinpkg``: fetch a binary when one fits.

        Off by default, because building from source is what Gentoo is, and a
        setting that quietly changes how packages arrive should be one somebody
        turned on.
        """
        return str(self._s.value("build/useBinaries", "false")).lower() == "true"

    @use_binaries.setter
    def use_binaries(self, value: bool) -> None:
        self._s.setValue("build/useBinaries", "true" if value else "false")

    # -- privileges and backups --------------------------------------------

    @property
    def escalation(self) -> Escalation:
        value = str(self._s.value("privilege/method", "auto"))
        return value if value in ("auto", "pkexec", "sudo") else "auto"  # type: ignore[return-value]

    @escalation.setter
    def escalation(self, value: Escalation) -> None:
        self._s.setValue("privilege/method", value)

    @property
    def backup_form(self) -> BackupForm:
        value = str(self._s.value("backup/form", "directory"))
        return value if value in ("directory", "archive") else "directory"  # type: ignore[return-value]

    @backup_form.setter
    def backup_form(self, value: BackupForm) -> None:
        self._s.setValue("backup/form", value)

    @property
    def backup_keep(self) -> int:
        try:
            value = int(self._s.value("backup/keep", BACKUP_KEEP_DEFAULT))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return BACKUP_KEEP_DEFAULT
        return max(1, min(100, value))

    @backup_keep.setter
    def backup_keep(self, value: int) -> None:
        self._s.setValue("backup/keep", max(1, min(100, int(value))))

    # -- window geometry ---------------------------------------------------

    @property
    def window_geometry(self) -> QByteArray | None:
        value = self._s.value("window/geometry")
        return value if isinstance(value, QByteArray) and not value.isEmpty() else None

    @window_geometry.setter
    def window_geometry(self, value: QByteArray) -> None:
        self._s.setValue("window/geometry", value)

    @property
    def window_state(self) -> QByteArray | None:
        value = self._s.value("window/state")
        return value if isinstance(value, QByteArray) and not value.isEmpty() else None

    @window_state.setter
    def window_state(self, value: QByteArray) -> None:
        self._s.setValue("window/state", value)

    # -- "official repository only" ---------------------------------------

    @property
    def official_only(self) -> bool:
        return self._s.value("portage/officialOnly", False, type=bool)

    @official_only.setter
    def official_only(self, value: bool) -> None:
        self._s.setValue("portage/officialOnly", value)

    @property
    def official_mode(self) -> OfficialMode:
        value = str(self._s.value("portage/officialMode", "hide"))
        return value if value in ("hide", "mask") else "hide"  # type: ignore[return-value]

    @official_mode.setter
    def official_mode(self, value: OfficialMode) -> None:
        self._s.setValue("portage/officialMode", value)

    # ----------------------------------------------------------------------

    def sync(self) -> None:
        """Flush pending writes to disk."""
        self._s.sync()
