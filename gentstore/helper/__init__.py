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

"""The privileged half of Gentstore.

Two small programs, installed under ``/usr/libexec/gentstore`` and reached only
through ``pkexec``:

``gentstore_helper``
    writes to ``/etc/portage`` — the only code in the project that writes
    anything outside the user's home directory;
``gentstore_launcher``
    runs ``emerge`` and friends, streams their output back and can stop them.

Neither imports Qt or anything from :mod:`gentstore.ui`. They are meant to be
read end to end by a suspicious user, because that is what Gentoo users are.
"""
