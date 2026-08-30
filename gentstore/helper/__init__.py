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
