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

"""Qt models — the adaptation layer between ``core`` and the widgets.

Nothing here computes anything about packages; it takes what ``core`` returns
and presents it the way Qt's item views expect. The direction of dependency is
one-way: ``ui → models → core``.
"""

from .packages import PackageListModel
from .update import MergePreviewModel

__all__ = ["MergePreviewModel", "PackageListModel"]
