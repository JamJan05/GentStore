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

"""Reusable widgets shared between screens."""

from .block_notice import BlockNotice
from .chips import Pill, ToggleChip
from .clickable_label import ClickableLabel
from .diff_view import DiffView
from .flow_layout import FlowLayout, FlowWidget
from .licence_dialog import LicenceDialog
from .log_view import LogView
from .nav_item import NavItem
from .official_toggle import OfficialOnlyControl
from .package_list import PackageDelegate, PackageListView
from .repo_badge import RepoBadge
from .restore_dialog import RestoreDialog
from .sidebar import Sidebar
from .use_flag_row import UseFlagRow
from .use_flags_panel import UseFlagsPanel
from .write_preview import WritePreview

__all__ = [
    "BlockNotice",
    "ClickableLabel",
    "DiffView",
    "FlowLayout",
    "FlowWidget",
    "LicenceDialog",
    "LogView",
    "NavItem",
    "OfficialOnlyControl",
    "PackageDelegate",
    "PackageListView",
    "Pill",
    "RepoBadge",
    "RestoreDialog",
    "Sidebar",
    "ToggleChip",
    "UseFlagRow",
    "UseFlagsPanel",
    "WritePreview",
]
