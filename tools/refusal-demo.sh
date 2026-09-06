#!/usr/bin/env bash
# Run Gentstore against packages Portage will refuse to install.
#
#     tools/refusal-demo.sh            open the window with four broken packages
#     tools/refusal-demo.sh --emerge   print what emerge says about each, no window
#
# The install gate on the search screen opens when an analysis comes back with
# nothing to write and nothing conflicting. A refusal is neither — Portage
# prints its reason and stops, with no merge list, no blocker row and no lines
# to write — so a refusal has to be recognised for what it is or the gate opens
# over a package that cannot be built. There are four ways Portage says it
# (`_emerge/depgraph.py`: `_show_unsatisfied_dep`), and this puts one package in
# front of you for each:
#
#     app-misc/gs-demo-no-ebuild      an atom no enabled repository provides
#     app-misc/gs-demo-missing-use    a USE flag no candidate version has
#     app-misc/gs-demo-masked         a mask --autounmask will not lift
#     app-misc/gs-demo-required-use   a USE combination REQUIRED_USE forbids
#
# Search for "gs-demo", pick one, press "Analyse requirements". All four must
# leave the install button disabled and show Portage's own words underneath.
# The last one also offers a line to write, and that is correct: Portage really
# does propose `-icu` for a package whose REQUIRED_USE says `inspector? ( icu )`,
# so writing it and looking again produces the identical output. The line is
# still offered, because it is Portage's proposal; the refusal is shown beside
# it and the gate stays shut.
#
# Getting all four out of a healthy system is not a matter of picking awkward
# packages: with --autounmask on, Portage answers most refusals with a line to
# write rather than a refusal. Hence four one-line ebuilds of our own.
#
# Nothing on the system is changed and nothing needs root. The repository is
# built under TMPDIR and handed to Portage in PORTAGE_REPOSITORIES, which
# replaces repos.conf for this one process and its children; the live
# configuration is copied into it first, so the window looks exactly as it
# always does with four extra packages in it. Undo by deleting the directory
# named on the first line of output, or by rebooting.
#
# The same technique recorded tests/fixtures/pretend-{no-ebuild,missing-use,
# masked,required-use}.txt — see the README beside them.

set -euo pipefail

SRC=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
REPO=${TMPDIR:-/tmp}/gentstore-refusal-demo-$(id -u)
NAME=gs-refusal-demo

rm -rf "$REPO"
mkdir -p "$REPO/profiles" "$REPO/metadata"
echo "$NAME" > "$REPO/profiles/repo_name"
printf 'masters = gentoo\nthin-manifests = true\n' > "$REPO/metadata/layout.conf"

ebuild() {  # name, description, RDEPEND, EAPI
    local dir="$REPO/app-misc/$1"
    mkdir -p "$dir"
    cat > "$dir/$1-1.ebuild" <<EOF
# Distributed under the terms of the GNU General Public License v2

EAPI=${4:-8}

DESCRIPTION="$2"
HOMEPAGE="https://example.invalid/"
LICENSE="GPL-2"
SLOT="0"
KEYWORDS="amd64"

RDEPEND="$3"
EOF
}

ebuild gs-demo-no-ebuild \
    "Refusal: depends on a package no enabled repository provides" \
    "dev-libs/gs-only-in-an-overlay"
ebuild gs-demo-missing-use \
    "Refusal: depends on a USE flag no candidate version has" \
    "media-video/ffmpeg[-encode]"
ebuild gs-demo-masked \
    "Refusal: depends on a package masked in a way autounmask will not lift" \
    "app-misc/gs-demo-eapi"
ebuild gs-demo-required-use \
    "Refusal: depends on a USE combination REQUIRED_USE forbids" \
    "net-libs/nodejs[inspector,-icu]"

# Not one of the four; it is what gs-demo-masked cannot have. An EAPI this
# Portage does not support is a mask autounmask has no answer to, which is
# harder to arrange with a real package than it sounds.
ebuild gs-demo-eapi "An EAPI this Portage does not support" "" 99

PORTAGE_REPOSITORIES="$(portageq repos_config /)
[$NAME]
location = $REPO
auto-sync = no
masters = gentoo
priority = 50
"
export PORTAGE_REPOSITORIES

echo "throwaway repository: $REPO"

if [[ ${1:-} == --emerge ]]; then
    for package in no-ebuild missing-use masked required-use; do
        echo
        echo "===== app-misc/gs-demo-$package"
        LC_ALL=C.UTF-8 emerge --ignore-default-opts --color=n --nospinner \
            --pretend --verbose --autounmask --autounmask-license=y \
            "app-misc/gs-demo-$package" 2>&1 | tail -n 14 || true
    done
    exit 0
fi

# From the checkout rather than from whatever is installed: the point of the
# exercise is the code in this working tree. A fresh index too, because the
# cached one was built without this repository.
export GENTSTORE_INDEX_CACHE=0
cd "$SRC"
exec python3 -m gentstore "$@"
