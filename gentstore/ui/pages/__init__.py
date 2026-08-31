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

"""The application's screens.

``create_page`` is the one place that decides which widget backs a screen. As
sessions land, entries move out of the placeholder fallback and into the real
implementations.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import QWidget

from ..context import AppContext
from .base import Page
from .cfgfiles import CfgFilesPage
from .elog import ElogPage
from .makeconf import MakeConfPage
from .masks import MasksPage
from .placeholder import PlaceholderPage
from .profile import ProfilePage
from .registry import PAGES, PAGES_BY_ID, PageSpec
from .repos import ReposPage
from .search import SearchPage
from .split_page import SplitPage
from .update import UpdatePage
from .world import WorldPage

__all__ = [
    "PAGES",
    "PAGES_BY_ID",
    "Page",
    "PageSpec",
    "CfgFilesPage",
    "ElogPage",
    "MakeConfPage",
    "MasksPage",
    "ProfilePage",
    "ReposPage",
    "SearchPage",
    "UpdatePage",
    "WorldPage",
    "SplitPage",
    "create_page",
]

#: Screens that have their real implementation. Everything else falls back to
#: the placeholder, which names the session that will build it.
_IMPLEMENTED: dict[str, Callable[..., Page]] = {
    "search": SearchPage,
    "mask": MasksPage,
    "repos": ReposPage,
    "update": UpdatePage,
    "cfg": CfgFilesPage,
    "makeconf": MakeConfPage,
    "profile": ProfilePage,
    "elog": ElogPage,
    "world": WorldPage,
}


def create_page(spec: PageSpec, context: AppContext, parent: QWidget | None = None) -> Page:
    """Build the widget for one screen."""
    factory = _IMPLEMENTED.get(spec.page_id, PlaceholderPage)
    return factory(spec, context, parent)
