"""The application window: menu bar, toolbar, sidebar, page stack, status bar."""

from __future__ import annotations

import logging
import os

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QCloseEvent, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QStackedWidget,
    QToolBar,
    QWidget,
)

from .. import APP_NAME, __version__
from ..core import backup as backup_core
from ..runner import helper_client, privilege
from ..settings import FONT_SCALES, Settings
from ..sysinfo import SystemInfo, collect
from .context import AppContext
from .i18n import untranslated
from .pages import PAGES, PAGES_BY_ID, Page, create_page
from .tasks import run_async
from .theme import icons
from .theme import tokens as t
from .widgets import LogView, OfficialOnlyControl, Sidebar

log = logging.getLogger(__name__)

#: Toolbar entries: action key, icon, target page, and the command it stands for.
TOOLBAR_ACTIONS = (
    ("sync", "arrows-clockwise", "update", "emaint sync -a"),
    ("update", "arrow-circle-up", "update", "emerge -avuDN @world"),
    ("overlays", "git-branch", "repos", "eselect repository"),
    ("log", "terminal-window", "elog", "emerge log"),
)


class MainWindow(QMainWindow):
    """Top-level window. Owns the page stack and the persistent chrome."""

    language_change_requested = pyqtSignal(str)
    font_scale_change_requested = pyqtSignal(float)

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.context = AppContext(settings, self)
        self._sysinfo = SystemInfo()
        self._pages: dict[str, Page] = {}
        #: Set by :meth:`load_system_info`. Until then the window is still being
        #: assembled and no screen is allowed to start reading from Portage —
        #: a constructor that quietly kicks off seconds of I/O is exactly what
        #: S1 moved out of ``__init__`` in the first place.
        self._started = False
        self._page_actions: dict[str, QAction] = {}
        self._toolbar_actions: dict[str, QAction] = {}

        self.setWindowTitle(APP_NAME)
        self.resize(*t.WINDOW_DEFAULT_SIZE)
        self.setMinimumSize(*t.WINDOW_MINIMUM_SIZE)

        self._build_menus()
        self._build_toolbar()
        self._build_body()
        self._build_log_dock()
        self._build_statusbar()
        self._connect_runner()

        self._restore_state()
        self.retranslate_ui()

    # ------------------------------------------------------------------ UI --

    def _build_menus(self) -> None:
        bar = self.menuBar()
        assert bar is not None
        bar.setMinimumHeight(t.MENUBAR_HEIGHT)

        self._menu_file = bar.addMenu("")
        self._act_settings = self._menu_file.addAction("")
        self._act_settings.triggered.connect(self._show_settings)
        self._menu_file.addSeparator()
        self._act_quit = self._menu_file.addAction("")
        self._act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        self._act_quit.triggered.connect(self.close)

        self._menu_repos = bar.addMenu("")
        self._act_sync_all = self._menu_repos.addAction("")
        self._act_sync_all.triggered.connect(lambda: self.set_page("update"))
        self._act_manage_overlays = self._menu_repos.addAction("")
        self._act_manage_overlays.triggered.connect(lambda: self.set_page("repos"))

        self._menu_package = bar.addMenu("")
        self._act_search = self._menu_package.addAction("")
        self._act_search.setShortcut(QKeySequence("Ctrl+F"))
        self._act_search.triggered.connect(lambda: self.set_page("search"))
        self._act_update_world = self._menu_package.addAction("")
        self._act_update_world.triggered.connect(lambda: self.set_page("update"))

        self._menu_system = bar.addMenu("")
        for key, page_id in (
            ("_act_portage_settings", "makeconf"),
            ("_act_profile", "profile"),
            ("_act_config_files", "cfg"),
            ("_act_elog", "elog"),
        ):
            action = self._menu_system.addAction("")
            action.triggered.connect(lambda _checked=False, p=page_id: self.set_page(p))
            setattr(self, key, action)

        self._menu_view = bar.addMenu("")
        self._menu_goto = QMenu(self._menu_view)
        self._menu_view.addMenu(self._menu_goto)
        for index, spec in enumerate(PAGES, start=1):
            action = self._menu_goto.addAction("")
            action.setShortcut(QKeySequence(f"Ctrl+{index}"))
            action.triggered.connect(lambda _checked=False, p=spec.page_id: self.set_page(p))
            self._page_actions[spec.page_id] = action

        self._menu_view.addSeparator()
        self._menu_language = QMenu(self._menu_view)
        self._menu_view.addMenu(self._menu_language)
        self._language_group = QActionGroup(self)
        self._language_group.setExclusive(True)
        self._language_actions: dict[str, QAction] = {}
        for code in ("system", "pl", "en"):
            action = self._menu_language.addAction("")
            action.setCheckable(True)
            action.setChecked(self.settings.language == code)
            action.triggered.connect(
                lambda _checked=False, c=code: self.language_change_requested.emit(c)
            )
            self._language_group.addAction(action)
            self._language_actions[code] = action

        self._menu_font = QMenu(self._menu_view)
        self._menu_view.addMenu(self._menu_font)
        self._font_group = QActionGroup(self)
        self._font_group.setExclusive(True)
        self._font_actions: dict[float, QAction] = {}
        for scale in FONT_SCALES:
            action = self._menu_font.addAction(f"{round(scale * 100)} %")
            action.setCheckable(True)
            action.setChecked(abs(self.settings.font_scale - scale) < 0.01)
            action.triggered.connect(
                lambda _checked=False, sc=scale: self.font_scale_change_requested.emit(sc)
            )
            self._font_group.addAction(action)
            self._font_actions[scale] = action

        self._menu_help = bar.addMenu("")
        self._act_about = self._menu_help.addAction("")
        self._act_about.triggered.connect(self._show_about)
        self._act_show_log = self._menu_help.addAction("")
        self._act_show_log.triggered.connect(self._show_log_location)

        self._act_toggle_log = QAction(self)
        self._act_toggle_log.setShortcut(QKeySequence("Ctrl+L"))
        self._act_toggle_log.triggered.connect(self.toggle_log)
        self.addAction(self._act_toggle_log)
        self._menu_view.addSeparator()
        self._menu_view.addAction(self._act_toggle_log)

        self._chrome_info = QLabel()
        self._chrome_info.setObjectName("chromeInfo")
        self._chrome_info.setContentsMargins(0, 0, t.SPACE_4, 0)
        self._chrome_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bar.setCornerWidget(self._chrome_info, Qt.Corner.TopRightCorner)

    def _build_toolbar(self) -> None:
        self._toolbar = QToolBar()
        self._toolbar.setObjectName("mainToolbar")
        self._toolbar.setMovable(False)
        self._toolbar.setFloatable(False)
        self._toolbar.setMinimumHeight(t.TOOLBAR_HEIGHT)
        self._toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(self._toolbar)

        for key, icon_name, page_id, _command in TOOLBAR_ACTIONS:
            action = QAction(self)
            action.setIcon(self._toolbar_icon(icon_name))
            action.triggered.connect(lambda _checked=False, p=page_id: self.set_page(p))
            self._toolbar.addAction(action)
            self._toolbar_actions[key] = action

        self._toolbar.addSeparator()

        self._official = OfficialOnlyControl()
        self._official.set_state(self.settings.official_only, self.settings.official_mode)
        self._official.changed.connect(self._on_official_changed)
        self._toolbar.addWidget(self._official)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._toolbar.addWidget(spacer)

        self._sync_label = QLabel()
        self._sync_label.setObjectName("chromeInfo")
        self._sync_label.setContentsMargins(0, 0, t.SPACE_4, 0)
        self._toolbar.addWidget(self._sync_label)

    def _build_body(self) -> None:
        body = QWidget()
        layout = QHBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.page_requested.connect(self.set_page)
        self.sidebar.restore_requested.connect(self._on_restore_requested)
        layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        for spec in PAGES:
            page = create_page(spec, self.context, self.stack)
            self._pages[spec.page_id] = page
            self.stack.addWidget(page)
        layout.addWidget(self.stack, 1)

        self.setCentralWidget(body)

    def _build_log_dock(self) -> None:
        """The command log, as a panel along the bottom.

        A dock rather than a page: a build has to stay readable while the user
        goes back to the package list, and its visibility and height are part of
        what ``saveState`` remembers between runs.
        """
        self.log_view = LogView()
        self.log_view.abort_requested.connect(self.context.command.abort)
        self.log_view.close_requested.connect(self._hide_log)

        self.log_dock = QDockWidget(self)
        # saveState() identifies docks by object name; without one the panel
        # comes back in the wrong place, or not at all.
        self.log_dock.setObjectName("logDock")
        self.log_dock.setWidget(self.log_view)
        self.log_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.log_dock.hide()

    def _connect_runner(self) -> None:
        runner = self.context.command
        runner.started.connect(self._on_command_started)
        runner.output.connect(self.log_view.append)
        runner.finished.connect(self._on_command_finished)
        runner.failed.connect(self._on_command_failed)
        self.context.command_refused.connect(self._on_command_refused)
        self.context.backups_changed.connect(self._refresh_backup)
        self.context.sidebar_badge.connect(self.sidebar.set_badge)

    def _build_statusbar(self) -> None:
        bar = self.statusBar()
        assert bar is not None
        bar.setMinimumHeight(t.STATUSBAR_HEIGHT)
        bar.setSizeGripEnabled(False)

        # QStatusBar lays its children out itself and ignores margins set on it,
        # so the breathing room goes on the labels.
        self._status_left = QLabel()
        self._status_left.setProperty("role", "mono")
        self._status_left.setContentsMargins(t.SPACE_4, 0, 0, 0)
        bar.addWidget(self._status_left)

        self._status_right = QLabel()
        self._status_right.setProperty("role", "mono")
        self._status_right.setContentsMargins(0, 0, t.SPACE_4, 0)
        bar.addPermanentWidget(self._status_right)

    # ------------------------------------------------------------- actions --

    def set_page(self, page_id: str) -> None:
        """Switch to a screen and remember it for the next launch."""
        page = self._pages.get(page_id)
        if page is None:
            log.warning("Unknown page requested: %s", page_id)
            return
        self.stack.setCurrentWidget(page)
        self.sidebar.set_active_page(page_id)
        self.settings.last_page = page_id
        if self._started:
            page.activated()

    def current_page_id(self) -> str:
        widget = self.stack.currentWidget()
        return widget.page_id if isinstance(widget, Page) else PAGES[0].page_id

    def _on_official_changed(self, enabled: bool, mode: str) -> None:
        self.context.set_official_only(enabled, mode)
        log.info("Official-only filter: enabled=%s mode=%s", enabled, mode)
        bar = self.statusBar()
        if bar is not None:
            if not enabled:
                bar.showMessage(self.tr("Showing packages from all repositories."), 4000)
            elif mode == "hide":
                bar.showMessage(
                    self.tr("Overlay packages are hidden in the interface only."), 4000
                )
            else:
                bar.showMessage(
                    self.tr(
                        "Masking happens per overlay on the Repositories screen — "
                        "nothing has been written yet."
                    ),
                    8000,
                )

    # ------------------------------------------------------------ the log --

    def _on_command_started(self, spec: object) -> None:
        display = getattr(spec, "display", "")
        self.log_view.start(display)
        self.log_dock.show()
        self.log_dock.raise_()

    def _on_command_finished(self, code: int) -> None:
        if code == 0:
            self.log_view.finish(self.tr("Finished."), "ok")
        else:
            self.log_view.finish(self.tr("Exit code {code}.").format(code=code), "err")
        # A command that ran may well have installed or removed something.
        self.context.refresh_installed()
        self.refresh_system_info()

    def _on_command_failed(self, message: str) -> None:
        self.log_view.finish(message, "err")
        self.context.refresh_installed()

    def _on_command_refused(self, message: str) -> None:
        QMessageBox.warning(self, self.tr("Cannot run this"), message)

    def _hide_log(self) -> None:
        self.log_dock.hide()

    def toggle_log(self) -> None:
        """Ctrl+L: show the log panel, or hide it if it is already up."""
        self.log_dock.setVisible(not self.log_dock.isVisible())
        if self.log_dock.isVisible():
            self.log_dock.raise_()

    # -------------------------------------------------------- the backups --

    def _refresh_backup(self) -> None:
        self.sidebar.set_backup(self.context.latest_backup_label())

    def _on_restore_requested(self) -> None:
        """Docs/04-privileges.md §5: show the difference, then ask.

        A dialog rather than a yes/no box, because "restore the most recent
        one" is not a decision anybody can make sensibly — the copies are named
        after timestamps, and the only way to tell them apart is to see what
        going back to each would undo.
        """
        from ..core.makeconf import path_for  # noqa: PLC0415 — needs Portage
        from .widgets.restore_dialog import RestoreDialog  # noqa: PLC0415

        backups = backup_core.list_backups()
        if not backups:
            QMessageBox.information(
                self,
                self.tr("Restore backup"),
                self.tr("There are no backups of /etc/portage yet."),
            )
            return

        dialog = RestoreDialog(backups, path_for().parent, self)
        if dialog.exec() != RestoreDialog.DialogCode.Accepted:
            return
        chosen = dialog.chosen
        if chosen is None:
            return

        run_async(
            helper_client.restore_backup,
            self._on_restore_done,
            self._on_restore_failed,
            chosen.name,
        )

    def _on_restore_done(self, result: object) -> None:
        ok = getattr(result, "ok", False)
        if ok:
            self.context.backups.reset()
            self.context.backups_changed.emit()
            self.context.reload_index()
            QMessageBox.information(
                self,
                self.tr("Restore backup"),
                self.tr("/etc/portage was restored from {path}.").format(
                    path=getattr(result, "data", {}).get("restored_from", "")
                ),
            )
        elif getattr(result, "cancelled", False):
            log.info("The restore was cancelled at the authentication dialog")
        else:
            QMessageBox.warning(
                self, self.tr("Restore backup"), getattr(result, "error", "")
            )

    def _on_restore_failed(self, error: Exception) -> None:
        log.error("Restoring the backup failed: %s", error)
        QMessageBox.warning(self, self.tr("Restore backup"), str(error))

    def _warn_if_helper_stale(self) -> None:
        """Say so when the installed privileged programs are from an older build.

        The two halves of Gentstore are versioned together. An installed helper
        that predates the interface refuses operations this version considers
        perfectly ordinary, and the message it gives back is true and useless.
        Better to say it once, up front, than to let it surface as a puzzling
        refusal halfway through a change.
        """
        stale = privilege.stale_programs()
        if not stale:
            return
        names = ", ".join(status.name for status in stale)
        log.warning("Installed privileged programs are out of date: %s", names)
        bar = self.statusBar()
        if bar is not None:
            bar.showMessage(
                self.tr(
                    "The installed {names} is from an older version. "
                    "Run `sudo make install-system` — until then, writing to "
                    "/etc may be refused."
                ).format(names=names),
                15000,
            )

    def warn_if_root(self) -> None:
        """Say so if the whole application was started as root.

        Docs/04-privileges.md §1: there is no "run Gentstore with sudo" mode,
        and there does not need to be — everything privileged goes through
        pkexec and a short-lived helper. Running a Qt application as root is a
        habit worth naming rather than quietly tolerating.

        It lives on the window rather than in ``app.py`` for a duller reason:
        ``self.tr()`` is the only form the string extractor can attribute to a
        class. ``window.tr("…")`` called from elsewhere is skipped silently and
        the text stays English in every language.
        """
        if os.geteuid() != 0:
            return
        log.warning("Gentstore is running as root; this is neither needed nor a good idea")
        QMessageBox.warning(
            self,
            self.tr("Running as root"),
            self.tr(
                "Gentstore is running as root. It does not need to be: it asks for "
                "privileges only for the individual operations that require them.\n\n"
                "Running a graphical application as root puts your whole desktop "
                "session at its mercy. Please close it and start it as your normal user."
            ),
        )

    def _show_settings(self) -> None:
        from .settings_dialog import SettingsDialog  # noqa: PLC0415 — pulls in the runner

        dialog = SettingsDialog(self.settings, self)
        dialog.language_changed.connect(self.language_change_requested)
        dialog.font_scale_changed.connect(self.font_scale_change_requested)
        dialog.exec()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            self.tr("About {app}").format(app=APP_NAME),
            self.tr(
                "{app} {version}\n\n"
                "A graphical front-end for Portage on Gentoo Linux.\n"
                "Licensed under the GNU GPL version 2."
            ).format(app=APP_NAME, version=__version__),
        )

    def _show_log_location(self) -> None:
        from ..logging_setup import state_dir

        QMessageBox.information(
            self,
            self.tr("Log file"),
            self.tr("Messages are written to:\n{path}").format(
                path=state_dir() / "gentstore.log"
            ),
        )

    # ---------------------------------------------------------- system info --

    def load_system_info(self) -> None:
        """Populate the chrome from Portage, in the background.

        Called explicitly after the window is shown rather than from ``__init__``:
        importing and initialising Portage takes seconds, and a constructor that
        quietly starts I/O is awkward to test and to reason about.
        """
        self._started = True
        run_async(collect, self._on_system_info, self._on_system_info_failed)
        self._refresh_backup()
        self._warn_if_helper_stale()
        # The visible screen gets its data going; the rest wait until they are
        # opened. Both go through the same hook, so no screen is a special case.
        current = self.stack.currentWidget()
        if isinstance(current, Page):
            current.activated()

    def _on_system_info(self, info: object) -> None:
        if isinstance(info, SystemInfo):
            self._sysinfo = info
            self.retranslate_ui()

    def _on_system_info_failed(self, error: Exception) -> None:
        log.error("Reading system info failed: %s", error)

    def refresh_system_info(self) -> None:
        """Re-read the chrome after something changed the system."""
        if self._started:
            run_async(collect, self._on_system_info, self._on_system_info_failed, True)

    # ------------------------------------------------------------- i18n ---- #

    def retranslate_ui(self) -> None:
        """Re-apply every string owned by the window chrome."""
        self._menu_file.setTitle(self.tr("&File"))
        self._act_settings.setText(self.tr("Settings…"))
        self._act_quit.setText(self.tr("Quit"))

        self._menu_repos.setTitle(self.tr("&Repositories"))
        self._act_sync_all.setText(self.tr("Synchronise all repositories"))
        self._act_manage_overlays.setText(self.tr("Manage overlays"))

        self._menu_package.setTitle(self.tr("&Package"))
        self._act_search.setText(self.tr("Search…"))
        self._act_update_world.setText(self.tr("Update @world"))

        self._menu_system.setTitle(self.tr("&System"))
        self._act_portage_settings.setText(self.tr("Portage settings"))
        self._act_profile.setText(self.tr("Profile"))
        self._act_config_files.setText(self.tr("Configuration files"))
        self._act_elog.setText(self.tr("elog messages"))

        self._menu_view.setTitle(self.tr("&View"))
        self._menu_goto.setTitle(self.tr("Go to"))
        for page_id, action in self._page_actions.items():
            action.setText(PAGES_BY_ID[page_id].title)

        self._menu_language.setTitle(self.tr("Language"))
        # Language names stay in their own language on purpose.
        self._language_actions["system"].setText(self.tr("System default"))
        self._language_actions["pl"].setText(untranslated("Polski"))
        self._language_actions["en"].setText(untranslated("English"))

        self._menu_font.setTitle(self.tr("Interface size"))
        self._act_toggle_log.setText(self.tr("Command log"))

        self._menu_help.setTitle(self.tr("&Help"))
        self._act_about.setText(self.tr("About {app}").format(app=APP_NAME))
        self._act_show_log.setText(self.tr("Where is the log file?"))

        for key, _icon, _page, command in TOOLBAR_ACTIONS:
            action = self._toolbar_actions[key]
            action.setText(self._toolbar_label(key))
            action.setToolTip(command)

        self._set_chrome_info(self._sysinfo.chrome_line())
        self._sync_label.setText(self._sync_text())
        self._status_left.setText(self._status_left_text())
        self._status_right.setText(self._status_right_text())

        self.sidebar.retranslate_ui()
        self._official.retranslate_ui()
        self.log_view.retranslate_ui()
        self.log_dock.setWindowTitle(self.tr("Command log"))

    def _set_chrome_info(self, text: str) -> None:
        """Put *text* in the menu bar's right-hand corner.

        QMenuBar measures a corner widget when it is installed and does not
        re-measure it when the widget's own size hint later grows, so the label
        is re-installed after the text changes. Without that it keeps the width
        it had while it was still empty and shows a single clipped letter.
        """
        self._chrome_info.setText(text)
        self._chrome_info.adjustSize()
        self._chrome_info.setFixedWidth(self._chrome_info.sizeHint().width())
        bar = self.menuBar()
        if bar is not None:
            bar.setCornerWidget(self._chrome_info, Qt.Corner.TopRightCorner)
            bar.updateGeometry()

    def _toolbar_label(self, key: str) -> str:
        return {
            "sync": self.tr("Synchronise"),
            "update": self.tr("Update @world"),
            "overlays": self.tr("Overlays"),
            "log": self.tr("Log"),
        }[key]

    def _sync_text(self) -> str:
        if self._sysinfo.last_sync is None:
            return self.tr("never synchronised")
        return self.tr("sync: {when}").format(
            when=self._sysinfo.last_sync.strftime("%Y-%m-%d %H:%M")
        )

    def _status_left_text(self) -> str:
        if self._sysinfo.world_count is None:
            return self.tr("@world: unknown")
        return self.tr("@world: %n entry(s)", "", self._sysinfo.world_count)

    def _status_right_text(self) -> str:
        parts = []
        if self._sysinfo.makeopts:
            parts.append(f'MAKEOPTS="{self._sysinfo.makeopts}"')
        if self._sysinfo.features:
            # FEATURES is routinely a couple of hundred characters; the status bar
            # shows the head of it and the full value lives in Portage settings.
            features = self._sysinfo.features
            if len(features) > 56:
                features = features[:55].rsplit(" ", 1)[0] + " …"
            parts.append(f'FEATURES="{features}"')
        return " · ".join(parts)

    def changeEvent(self, event: QEvent | None) -> None:  # noqa: N802 - Qt API
        if event is not None and event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    # ----------------------------------------------------------- lifecycle --

    def _toolbar_icon(self, icon_name: str) -> QIcon:
        """A toolbar glyph sized to follow the current interface scale."""
        size = max(14, round(self.fontMetrics().height() * 1.05))
        return QIcon(
            icons.tinted_pixmap(icon_name, t.NEUTRAL_300, size, self.devicePixelRatioF())
        )

    def refresh_icons(self) -> None:
        """Rebuild toolbar icons after a font-scale change."""
        for key, icon_name, _page, _command in TOOLBAR_ACTIONS:
            self._toolbar_actions[key].setIcon(self._toolbar_icon(icon_name))
        for page in self._pages.values():
            page.update()

    def _restore_state(self) -> None:
        geometry = self.settings.window_geometry
        if geometry is not None:
            self.restoreGeometry(geometry)
        state = self.settings.window_state
        if state is not None:
            self.restoreState(state)
        self.set_page(self.settings.last_page)

    def closeEvent(self, event: QCloseEvent | None) -> None:  # noqa: N802 - Qt API
        # A command still running has to be stopped before its process outlives
        # the window that was showing its output. The launcher treats the closed
        # stdin as an abort, so a privileged build stops too.
        self.context.command.close()
        self.settings.window_geometry = self.saveGeometry()
        self.settings.window_state = self.saveState()
        self.settings.sync()
        super().closeEvent(event)
