# Installing the parts that have to live in system directories.
#
# The Python package installs the ordinary way — pip, or the ebuild in
# packaging/ — and does not need this file. What does need it is everything
# root owns: the two privileged programs, the polkit policy, and the desktop
# entry that puts Gentstore in the application menu.
#
#     sudo make install          everything below
#     sudo make install-system   only the privileged programs and the policy
#
# PREFIX and DESTDIR behave as usual, so a package manager can stage the lot
# into a build root.

PREFIX  ?= /usr
DESTDIR ?=

LIBEXEC  := $(DESTDIR)$(PREFIX)/libexec/gentstore
POLKIT   := $(DESTDIR)$(PREFIX)/share/polkit-1/actions
APPS     := $(DESTDIR)$(PREFIX)/share/applications
ICONS    := $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps

PYTHON  ?= python3

.PHONY: help install install-system install-desktop uninstall uninstall-system \
        overlay overlay-remove translations check

help:
	@echo "make install           install everything that belongs to root (needs root)"
	@echo "make install-system    only the helper, the launcher and the polkit policy"
	@echo "make install-desktop   only the desktop entry and the icon"
	@echo "make uninstall         remove all of it again"
	@echo "make overlay           put the ebuild in a local overlay (needs root)"
	@echo "make overlay-remove    take the overlay away again"
	@echo "make translations      compile the .qm catalogues the application loads"
	@echo "make check             run the tests and the linter"

install: install-system install-desktop

install-system:
	install -d -m 0755 $(LIBEXEC)
	install -m 0755 gentstore/helper/gentstore_helper.py   $(LIBEXEC)/gentstore-helper
	install -m 0755 gentstore/helper/gentstore_launcher.py $(LIBEXEC)/gentstore-launcher
	install -d -m 0755 $(POLKIT)
	install -m 0644 data/org.gentoo.gentstore.policy $(POLKIT)/org.gentoo.gentstore.policy
	@echo
	@echo "Installed:"
	@echo "  $(LIBEXEC)/gentstore-helper"
	@echo "  $(LIBEXEC)/gentstore-launcher"
	@echo "  $(POLKIT)/org.gentoo.gentstore.policy"
	@echo
	@echo "polkit picks the policy up on its own; no restart is needed."

install-desktop:
	install -d -m 0755 $(APPS) $(ICONS)
	install -m 0644 data/gentstore.desktop $(APPS)/gentstore.desktop
	install -m 0644 data/icons/gentstore.svg $(ICONS)/gentstore.svg
	-update-desktop-database $(APPS) 2>/dev/null || true
	-gtk-update-icon-cache -qtf $(DESTDIR)$(PREFIX)/share/icons/hicolor 2>/dev/null || true

uninstall: uninstall-system
	rm -f $(APPS)/gentstore.desktop $(ICONS)/gentstore.svg

uninstall-system:
	rm -f $(LIBEXEC)/gentstore-helper $(LIBEXEC)/gentstore-launcher
	rm -f $(POLKIT)/org.gentoo.gentstore.policy
	-rmdir $(LIBEXEC) 2>/dev/null || true

# Portage's own way in: a local overlay with the live ebuild. Unlike the
# targets above this does not install anything itself — it ends by printing the
# emerge command, because whether to run it is not the Makefile's decision.
overlay:
	packaging/make-overlay.sh

overlay-remove:
	packaging/make-overlay.sh --remove

translations:
	$(PYTHON) tools/i18n.py all

check:
	$(PYTHON) -m pytest -q
	ruff check .
