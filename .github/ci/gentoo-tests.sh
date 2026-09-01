#!/bin/bash
# Run the suite inside a Gentoo stage3, the way the ebuild's src_test does.
#
# Called by .github/workflows/tests-gentoo.yml with the working directory
# mounted at /src and a repository snapshot mounted from the gentoo/portage
# image, so there is nothing to sync. Kept as a file rather than inside the
# workflow's `run:` because a shell script wrapped in YAML wrapped in `bash -c`
# is three quoting rules deep, and here-documents lose to all three.
set -euo pipefail

# Binary packages: PyQt6 built from source is an hour on a runner. `getuto`
# installs the keys Portage checks their signatures against — without it every
# one of them is refused, which reads as "binhost is empty".
getuto

cat >> /etc/portage/make.conf <<'EOF'
FEATURES="${FEATURES} getbinpkg"
EMERGE_DEFAULT_OPTS="--quiet-build --jobs 4 --load-average 4"
EOF

mkdir -p /etc/portage/binrepos.conf
cat > /etc/portage/binrepos.conf/gentoo.conf <<'EOF'
[binhost]
priority = 9999
sync-uri = https://distfiles.gentoo.org/releases/amd64/binpackages/23.0/x86-64
EOF

# qttools[linguist] is the ebuild's own BDEPEND, and for the same reason: the
# .qm catalogues are generated from the .ts files, never committed, and the two
# tests that switch the interface to Polish have nothing to load without them.
mkdir -p /etc/portage/package.use
echo "dev-qt/qttools linguist" > /etc/portage/package.use/gentstore-tests
cd /src
# git, so the tests that ask the repository whether CHANGELOG.md's refs resolve
# have something to ask. A stage3 has no VCS in it.
emerge --quiet --usepkg dev-python/pytest dev-python/pyqt6 dev-qt/qttools dev-vcs/git

python tools/i18n.py compile

# Not as root, for the same reason `emerge` runs src_test as the portage user
# rather than as root: half of what this application does is decided by who is
# asking. privilege.detect() answers "direct" to uid 0 — nothing to escalate —
# so every test about pkexec and sudo fails, and the helper's ownership check on
# CONFIG_PROTECT refuses a temporary directory under a world-writable /tmp,
# which is correct of it and useless as a test. The suite is written from the
# position the application actually runs in.
useradd --create-home --shell /bin/bash tester
chown -R tester:tester /src
git config --global --add safe.directory /src

# What this job is here for: the tests that need a real tree. They skip without
# one (tests/conftest.py), so a run that skipped them all would be a green light
# for nothing at all.
su tester -c "cd /src && QT_QPA_PLATFORM=offscreen python -m pytest -q -rs"
