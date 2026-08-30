"""Shared test fixtures.

The Qt application is created once for the whole session — a second
``QApplication`` in one process is not allowed — and it is pointed at a throwaway
configuration directory so running the tests never touches the settings or the
log of the person running them.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from gentstore.app import GentstoreApplication  # noqa: E402


@pytest.fixture(scope="session")
def app(tmp_path_factory: pytest.TempPathFactory) -> GentstoreApplication:
    sandbox = tmp_path_factory.mktemp("xdg")
    os.environ["XDG_CONFIG_HOME"] = str(sandbox / "config")
    os.environ["XDG_STATE_HOME"] = str(sandbox / "state")

    existing = GentstoreApplication.instance()
    return existing if isinstance(existing, GentstoreApplication) else GentstoreApplication([])
