"""Application logging.

Writes to ``$XDG_STATE_HOME/gentstore/gentstore.log`` (rotated) and, when
``--debug`` is passed, mirrors everything to stderr. The log is the first place
to look when a Portage call or a privileged write misbehaves, so command lines
and helper responses are logged in full.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)-7s %(name)-28s %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def state_dir() -> Path:
    """Return the directory used for logs and other local state."""
    base = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / "gentstore"


def setup_logging(debug: bool = False) -> Path:
    """Configure root logging and return the path of the log file."""
    directory = state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    log_file = directory / "gentstore.log"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)

    file_handler = RotatingFileHandler(
        log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    root.addHandler(file_handler)

    if debug:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(logging.DEBUG)
        root.addHandler(stream_handler)

    return log_file
