# Copyright 2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

PYTHON_COMPAT=( python3_{12..15} )
DISTUTILS_USE_PEP517=setuptools
inherit desktop distutils-r1 git-r3 optfeature xdg

DESCRIPTION="A graphical front-end for Portage"
HOMEPAGE="https://github.com/JamJan05/GentStore"
EGIT_REPO_URI="https://github.com/JamJan05/GentStore.git"

LICENSE="GPL-2+"
SLOT="0"
# A live ebuild: there is no release to point a tarball at yet, so this stays
# unkeyworded and needs "=app-portage/gentstore-9999 **" to be accepted.
KEYWORDS=""

RDEPEND="
	dev-python/pyqt6[gui,widgets,${PYTHON_USEDEP}]
	app-eselect/eselect-repository
	sys-apps/portage[${PYTHON_USEDEP}]
	sys-auth/polkit
"
# lrelease turns the .ts catalogues into the .qm files the application loads.
# They are generated rather than committed, so this is needed to build at all.
BDEPEND="
	dev-qt/qttools:6[linguist]
"

distutils_enable_tests pytest

python_prepare_all() {
	distutils-r1_python_prepare_all

	# Before python_compile, not after: with PEP 517 each wheel is built from
	# this tree, and a catalogue produced later would never reach the package.
	# The script only needs the standard library and lrelease, so any one of
	# the enabled interpreters will do.
	python_setup
	"${EPYTHON}" tools/i18n.py compile || die "compiling the translations failed"
}

python_test() {
	# No display in the sandbox; Qt's offscreen platform is what the test
	# suite is written against anyway.
	QT_QPA_PLATFORM=offscreen epytest
}

python_install_all() {
	distutils-r1_python_install_all

	# The privileged half. Two standalone programs, reached only through
	# pkexec, that between them are the only code here allowed to write
	# outside the user's home directory. See Docs/04-privileges.md.
	exeinto /usr/libexec/gentstore
	newexe gentstore/helper/gentstore_helper.py gentstore-helper
	newexe gentstore/helper/gentstore_launcher.py gentstore-launcher

	insinto /usr/share/polkit-1/actions
	doins data/org.gentoo.gentstore.policy

	domenu data/gentstore.desktop
	doicon -s scalable data/icons/gentstore.svg

	dodoc README.md
	dodoc -r Docs
}

pkg_postinst() {
	xdg_pkg_postinst

	optfeature "scanning for security advisories (GLSA)" app-portage/gentoolkit
	optfeature "suggesting CPU_FLAGS_X86" app-portage/cpuid2cpuflags

	elog ""
	elog "Gentstore never runs as root. Everything privileged goes through"
	elog "pkexec and one of two short programs in /usr/libexec/gentstore,"
	elog "both of which are worth reading before you trust them."
}
