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

"""Application bootstrap: QApplication, theme, translations, main window."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from PyQt6.QtCore import QLibraryInfo, QLocale, QTranslator
from PyQt6.QtWidgets import QApplication

from . import APP_NAME, ORG_DOMAIN, ORG_NAME, __version__
from .logging_setup import setup_logging
from .settings import FONT_SCALES, Settings
from .ui.main_window import MainWindow
from .ui.tasks import wait_for_tasks
from .ui.theme import icons
from .ui.theme.palette import build_palette
from .ui.theme.qss import build_qss

log = logging.getLogger(__name__)

I18N_DIR = Path(__file__).parent / "i18n"
SUPPORTED_LANGUAGES = ("pl", "en")


class GentstoreApplication(QApplication):
    """The application object; owns the theme and the active translators."""

    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.setApplicationName(APP_NAME)
        self.setApplicationDisplayName(APP_NAME)
        self.setApplicationVersion(__version__)
        self.setOrganizationName(ORG_NAME)
        self.setOrganizationDomain(ORG_DOMAIN)
        self.setStyle("Fusion")
        self.setPalette(build_palette())

        self.settings = Settings()
        self._app_translator = QTranslator(self)
        self._qt_translator = QTranslator(self)
        self._font_scale = self.settings.font_scale
        self.apply_font_scale(self._font_scale)

    # -- theme -------------------------------------------------------------

    def apply_font_scale(self, scale: float) -> None:
        """Rebuild the stylesheet at *scale* and remember the choice."""
        if scale not in FONT_SCALES:
            scale = 1.0
        self._font_scale = scale
        self.settings.font_scale = scale
        icons.clear_cache()
        self.setStyleSheet(build_qss(scale))

    @property
    def font_scale(self) -> float:
        return self._font_scale

    # -- translations ------------------------------------------------------

    def resolve_language(self, preference: str) -> str:
        """Turn a stored preference into a concrete language code."""
        if preference in SUPPORTED_LANGUAGES:
            return preference
        system = QLocale.system().name()  # e.g. "pl_PL"
        return "pl" if system.startswith("pl") else "en"

    def apply_language(self, preference: str) -> None:
        """Install the translators for *preference* ("system", "pl" or "en")."""
        self.settings.language = preference  # type: ignore[assignment]
        code = self.resolve_language(preference)

        self.removeTranslator(self._app_translator)
        self.removeTranslator(self._qt_translator)

        qm = I18N_DIR / f"gentstore_{code}.qm"
        if qm.is_file() and self._app_translator.load(str(qm)):
            self.installTranslator(self._app_translator)
            log.info("Loaded translation %s", qm.name)
        elif code != "en":
            log.warning(
                "Translation %s is missing — run tools/i18n.py to build it. "
                "Falling back to the English source strings.",
                qm.name,
            )

        qt_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if self._qt_translator.load(f"qtbase_{code}", qt_dir):
            self.installTranslator(self._qt_translator)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="gentstore",
        description="Graphical front-end for Portage on Gentoo Linux.",
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    parser.add_argument(
        "--lang",
        choices=("system", *SUPPORTED_LANGUAGES),
        help="override the interface language for this run",
    )
    parser.add_argument(
        "--debug", action="store_true", help="verbose logging, also written to stderr"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    argv = list(sys.argv if argv is None else argv)
    options = parse_args(argv[1:])

    log_file = setup_logging(options.debug)
    log.info("%s %s starting, logging to %s", APP_NAME, __version__, log_file)

    app = GentstoreApplication(argv)
    app.apply_language(options.lang or app.settings.language)

    window = MainWindow(app.settings)
    window.warn_if_root()
    window.language_change_requested.connect(app.apply_language)
    window.font_scale_change_requested.connect(
        lambda scale: (app.apply_font_scale(scale), window.refresh_icons())
    )
    window.show()
    window.load_system_info()

    try:
        return app.exec()
    finally:
        if not wait_for_tasks():
            log.warning("A background task was still running at shutdown")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
