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

"""Shared test fixtures.

The Qt application is created once for the whole session — a second
``QApplication`` in one process is not allowed — and it is pointed at a throwaway
configuration directory so running the tests never touches the settings or the
log of the person running them.

:func:`portage_env` is the gate in front of every test that asks this machine a
question rather than a fixture. It lives here because four modules had a copy of
it, and because the copies knew about only one of the two ways a host can fail
to be a Gentoo system.
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


@pytest.fixture(scope="session")
def portage_env():
    """The machine's own Portage, or a skip — for tests that ask it questions.

    Two different absences, and they look nothing alike. On a machine with no
    Gentoo on it the module is not there at all and :func:`env` raises. In CI it
    is there — ``pip install portage`` puts a working 3.0.x on any host — and
    then answers every question with nothing: no arch, no installed packages, a
    repository list built from whatever ``/etc/portage`` happens to hold. The
    first failed loudly and skipped; the second failed as ``assert 0 > 100``,
    which reads like a broken test rather than a host that has no packages.

    Both mean the same thing to a test written against a real system, so both
    skip here.
    """
    from gentstore.core.packages import installed_cps  # noqa: PLC0415 - slow import
    from gentstore.core.portage_env import PortageUnavailableError, env  # noqa: PLC0415

    try:
        environment = env()
    except PortageUnavailableError as exc:  # pragma: no cover - non-Gentoo host
        pytest.skip(f"no usable Portage installation: {exc}")

    if not environment.arch or not installed_cps(environment):  # pragma: no cover - CI
        pytest.skip(
            "Portage is importable here but describes no installed system: "
            f"arch={environment.arch!r}, repositories={environment.repo_names}"
        )
    return environment
