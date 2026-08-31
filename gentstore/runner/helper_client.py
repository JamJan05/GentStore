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

"""Talking to the privileged helper.

One request, one process, one answer. The helper is short-lived by design: it
does a single thing and exits, so there is never a root process of ours sitting
around waiting to be asked for something else.

These calls block — ``pkexec`` puts up a password dialog and waits — so the
interface runs them through :func:`gentstore.ui.tasks.run_async`.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Any

from . import privilege

log = logging.getLogger(__name__)

#: Long enough for somebody to find their password and type it.
TIMEOUT_SECONDS = 180

#: polkit's exit code when the user dismissed the dialog. Worth telling apart
#: from a real failure: cancelling is a decision, not an error.
_PKEXEC_DISMISSED = 126


@dataclass(frozen=True, slots=True)
class HelperResult:
    """What the helper reported back."""

    ok: bool
    code: str = ""
    error: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def changed(self) -> bool:
        return bool(self.data.get("changed"))

    @property
    def cancelled(self) -> bool:
        """The user dismissed the authentication dialog."""
        return self.code == "cancelled"

    @property
    def backup(self) -> str | None:
        value = self.data.get("backup")
        return str(value) if value else None


def _failure(code: str, error: str) -> HelperResult:
    return HelperResult(ok=False, code=code, error=error)


def request(op: str, *, ensure_backup: bool = False, **fields: Any) -> HelperResult:
    """Run one helper operation and return its answer.

    *ensure_backup* asks the helper to copy ``/etc/portage`` aside first, in the
    same privileged run as the change itself — so a backup can never be missing
    for a change that went through.
    """
    escalation = privilege.detect()
    if not escalation.is_available:
        return _failure("no_privilege", escalation.problem or "cannot become root")

    helper = privilege.helper_command()
    if helper is None:
        return _failure(
            "no_helper",
            f"{privilege.HELPER_NAME} is not installed in {privilege.INSTALL_DIR}. "
            f"Run `sudo make install-system`.",
        )

    payload = json.dumps({"op": op, "ensure_backup": ensure_backup, **fields})
    argv = escalation.wrap(helper.argv)
    log.info("Helper request: %s %s", op, fields.get("path", ""))

    try:
        completed = subprocess.run(  # noqa: S603 - argv is built here, not passed in
            list(argv),
            input=payload,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _failure("timeout", "the helper did not answer in time")
    except OSError as exc:
        return _failure("spawn_failed", str(exc))

    if not completed.stdout.strip():
        if completed.returncode == _PKEXEC_DISMISSED:
            return _failure("cancelled", "authentication was dismissed")
        return _failure(
            "no_answer",
            completed.stderr.strip() or f"the helper exited with status {completed.returncode}",
        )

    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return _failure("bad_answer", f"the helper's answer was not JSON: {exc}")

    if not response.get("ok"):
        return HelperResult(
            ok=False,
            code=str(response.get("code", "error")),
            error=_annotate(str(response.get("error", ""))),
            data=response,
        )
    return HelperResult(ok=True, data=response)


def _annotate(error: str) -> str:
    """Add the reason a refusal may make no sense, when it applies.

    An installed helper from an older Gentstore refuses operations this version
    knows are allowed. The message it gives is then technically true and
    completely baffling, so the real explanation goes next to it.
    """
    stale = privilege.stale_programs()
    if not stale:
        return error
    names = ", ".join(status.name for status in stale)
    return (
        f"{error}\n\n"
        f"The installed {names} is from an older version of Gentstore. "
        f"Run `sudo make install-system` to bring it up to date."
    )


def make_backup() -> HelperResult:
    """Copy ``/etc/portage`` aside now, without changing anything."""
    return request("backup")


def restore_backup(name: str) -> HelperResult:
    """Put a named backup back, keeping a copy of the current state first."""
    return request("restore", name=name)
