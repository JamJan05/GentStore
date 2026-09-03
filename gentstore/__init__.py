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

"""Gentstore — a graphical front-end for Portage on Gentoo Linux."""

__version__ = "1.3.1"
APP_NAME = "Gentstore"
ORG_NAME = "Gentstore"
ORG_DOMAIN = "gentstore.gentoo.org"

#: The basename of our installed desktop entry, without the extension. Qt hands
#: this to the compositor as the Wayland ``app_id``; without it Qt falls back to
#: the basename of ``/proc/self/exe``, which for anything started through a
#: Python entry point is the interpreter — the window announced itself as
#: "python3.14" and the desktop, finding no ``python3.14.desktop``, had no name
#: and no icon to show for it. Must stay equal to ``data/gentstore.desktop``.
DESKTOP_ID = "gentstore"

#: ``Icon=`` in that entry, and the basename under ``hicolor/scalable/apps``.
ICON_NAME = "gentstore"
