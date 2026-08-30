"""Resources that outlive any single screen.

Three things belong here so far.

The **search index** takes a couple of seconds to build and every screen that
lists packages will want the same one; rebuilding it per screen would be both
slow and a source of disagreement between screens. It is built once, in the
background, and handed out through :attr:`index_ready`.

The **"only ::gentoo" state** lives here for the opposite reason: it is set in
the toolbar but read by the screens, and routing it through the window would
make every screen depend on the window's internals.

The **command runner** is here because there is exactly one of it. Any screen
can ask to run something; it always lands in the same log panel, and a second
command cannot start while the first is going. Two ``emerge`` processes at once
is not a state Portage is willing to be in, and the surest way to prevent it is
to have only one place that can start one.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal

from ..core import portage_env, useflags
from ..core.backup import BackupTracker, latest
from ..core.packages import SearchIndex
from ..runner.command import Command, CommandError, CommandSpec
from ..settings import Settings
from .tasks import ProgressReporter, run_async

log = logging.getLogger(__name__)


class AppContext(QObject):
    """Shared state handed to every page when it is built."""

    #: The index finished building; the payload is a
    #: :class:`~gentstore.core.packages.SearchIndex`.
    index_ready = pyqtSignal(object)
    #: ``(done, total)`` while the index is being built.
    index_progress = pyqtSignal(int, int)
    #: Building the index failed; the payload is the exception.
    index_failed = pyqtSignal(object)
    #: ``(enabled, mode)`` — see :class:`~gentstore.ui.widgets.OfficialOnlyControl`.
    official_only_changed = pyqtSignal(bool, str)
    #: A command is about to run; the window reveals the log panel.
    command_starting = pyqtSignal(object)
    #: A command could not be started at all; the payload is a message.
    command_refused = pyqtSignal(str)
    #: The set of backups on disk changed.
    backups_changed = pyqtSignal()
    #: ``(page_id, text)`` — a screen wants a count on its sidebar row.
    sidebar_badge = pyqtSignal(str, str)

    def __init__(self, settings: Settings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._index: SearchIndex | None = None
        self._loading = False
        self._error: Exception | None = None
        # Held for the lifetime of the context: a garbage-collected reporter
        # silently stops delivering progress.
        self._reporter = ProgressReporter(self)
        self._reporter.progress.connect(self.index_progress)

        self.command = Command(self)
        self.backups = BackupTracker()
        self.apply_privilege_preference()

    # -- the search index --------------------------------------------------

    @property
    def index(self) -> SearchIndex | None:
        """The index, or ``None`` while it is still being built."""
        return self._index

    @property
    def is_index_loading(self) -> bool:
        return self._loading

    @property
    def index_error(self) -> Exception | None:
        """Why the last build failed, if it did."""
        return self._error

    def ensure_index(self) -> None:
        """Start building the index unless it is ready or already building."""
        if self._index is not None or self._loading:
            return
        self._loading = True
        self._error = None
        log.info("Building the package index")
        run_async(SearchIndex.build, self._on_ready, self._on_failed, None, self._reporter.report)

    def reload_index(self) -> None:
        """Throw the index away and build it again — after a sync, say."""
        self._index = None
        self.ensure_index()

    def install_index(self, index: SearchIndex) -> None:
        """Adopt an index that was built elsewhere and announce it.

        The normal path goes through :meth:`ensure_index`; this is for an index
        that already exists — one built by a screen that had to rebuild it after
        a sync, and the one the tests hand in instead of reading the real tree.
        """
        self._loading = False
        self._error = None
        self._index = index
        self.index_ready.emit(index)

    def refresh_installed(self) -> None:
        """Re-read which packages are installed, without a full rebuild."""
        if self._index is not None:
            self._index.refresh_installed()

    def _on_ready(self, index: object) -> None:
        self._loading = False
        if isinstance(index, SearchIndex):
            self.install_index(index)

    def _on_failed(self, error: Exception) -> None:
        self._loading = False
        self._error = error
        log.error("Building the package index failed: %s", error)
        self.index_failed.emit(error)

    # -- running commands --------------------------------------------------

    def run(self, spec: CommandSpec) -> bool:
        """Start *spec*, or explain why not. ``True`` if it started.

        The refusal is a signal rather than an exception because every caller
        would otherwise write the same try/except around a button click.
        """
        try:
            self.command.start(spec)
        except CommandError as exc:
            log.warning("Refused to run %s: %s", spec.display, exc)
            self.command_refused.emit(str(exc))
            return False
        self.command_starting.emit(spec)
        return True

    @property
    def is_running(self) -> bool:
        return self.command.is_running()

    # -- backups -----------------------------------------------------------

    def latest_backup_label(self) -> str | None:
        """Timestamp of the newest backup, for the sidebar."""
        backup = latest()
        return backup.label if backup is not None else None

    def reload_portage(self) -> None:
        """Re-read Portage's configuration after ``/etc/portage`` changed.

        Roughly sixty milliseconds, and it happens once, right after a write —
        so it is done here and now rather than on a worker thread, where the
        screen would have to cope with briefly showing the old answer.

        The search index is deliberately *not* rebuilt: it describes which
        packages exist, and a USE flag change does not alter that.
        """
        try:
            portage_env.reload()
        except portage_env.PortageUnavailableError as exc:  # pragma: no cover
            log.error("Could not re-read the Portage configuration: %s", exc)
            return
        useflags.clear_caches()

    def main_repo_name(self) -> str:
        """Usually ``gentoo``; asked rather than assumed."""
        try:
            return portage_env.env().main_repo_name or "gentoo"
        except portage_env.PortageUnavailableError:  # pragma: no cover
            return "gentoo"

    def settings_summary_keywords(self) -> str:
        """``ACCEPT_KEYWORDS`` as configured, for the masks screen's header."""
        try:
            return " ".join(portage_env.env().accept_keywords)
        except portage_env.PortageUnavailableError:  # pragma: no cover
            return ""

    # -- "only ::gentoo" ---------------------------------------------------

    @property
    def use_binaries(self) -> bool:
        """Whether install commands should carry ``--getbinpkg``."""
        return self.settings.use_binaries

    @property
    def official_only(self) -> bool:
        return self.settings.official_only

    @property
    def official_mode(self) -> str:
        return self.settings.official_mode

    def apply_privilege_preference(self) -> None:
        """Tell the runner which way the user wants to become root."""
        from ..runner import privilege  # noqa: PLC0415 — avoids a cycle at import

        privilege.preferred = self.settings.escalation

    def backup_options(self) -> dict[str, object]:
        """The backup fields every mutating helper request carries."""
        return {
            "archive": self.settings.backup_form == "archive",
            "keep": self.settings.backup_keep,
        }

    def set_official_only(self, enabled: bool, mode: str) -> None:
        self.settings.official_only = enabled
        self.settings.official_mode = mode  # type: ignore[assignment]
        self.official_only_changed.emit(enabled, mode)
