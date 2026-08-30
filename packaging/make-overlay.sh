#!/usr/bin/env bash
# Put Gentstore into an overlay so Portage can install, update and remove it.
#
#     sudo packaging/make-overlay.sh             a synced overlay (the default)
#     sudo packaging/make-overlay.sh --no-sync   a pinned copy, never updated
#     sudo packaging/make-overlay.sh --local     build from this working tree
#
# By default Portage clones the `overlay` branch of the repository, so the
# overlay is a synced one: later ebuilds arrive with an ordinary "emerge --sync"
# and no second visit here. This needs no clone of your own, which is what the
# README's one-liner relies on — the configuration is all this writes, and the
# ebuilds come down with the first sync.
#
# --no-sync is the older behaviour: the ebuild is copied in once and Portage is
# told to leave the overlay alone. Choose it if you want a package that cannot
# change under you until you say so. Without a clone to copy from, it downloads
# the two files it cannot generate and checks they look like an ebuild first.
#
# --local exists for two situations: an upstream root cannot reach (a private
# repository, no credentials for the portage user) and testing a change before
# pushing it. It rewrites EGIT_REPO_URI in the copy that goes into the overlay,
# so `grep EGIT_REPO_URI` on the installed ebuild always says where the code
# came from. Either way git-r3 builds the last commit, never the working tree.
#
# Everything this writes is printed before it is written, nothing already there
# is overwritten without saying so, and running it twice changes nothing the
# second time. It stops short of `emerge` on purpose: installing is your call,
# and the command to run is the last thing printed.
#
# Undo with packaging/make-overlay.sh --remove.

set -euo pipefail

REPO_NAME="gentstore"
REPO_PATH="/var/db/repos/${REPO_NAME}"
CONF="/etc/portage/repos.conf/${REPO_NAME}.conf"
ACCEPT_DIR="/etc/portage/package.accept_keywords"
ACCEPT="${ACCEPT_DIR}/${REPO_NAME}"
ATOM="app-portage/gentstore"

#: Where to fetch the ebuild from when there is no clone to read it out of.
#: GENTSTORE_REF picks a branch or tag; the default is whatever main holds.
GENTSTORE_REF="${GENTSTORE_REF:-main}"
GITHUB_REPO="https://github.com/JamJan05/GentStore.git"
OVERLAY_BRANCH="overlay"
RAW_BASE="https://raw.githubusercontent.com/JamJan05/GentStore/${GENTSTORE_REF}"
SELF_URL="${RAW_BASE}/packaging/make-overlay.sh"

# Piped into bash, BASH_SOURCE is "bash" or empty and there is no tree above it.
# Both cases mean the same thing: fetch what we need instead of reading it.
SELF="${BASH_SOURCE[0]:-}"
if [[ -f ${SELF} ]]; then
	SOURCE="$(cd -- "$(dirname -- "${SELF}")/.." && pwd)"
else
	SOURCE=""
fi
EBUILD="${SOURCE:+${SOURCE}/packaging/${ATOM}/gentstore-9999.ebuild}"
FETCHED=false
[[ -n ${EBUILD} && -f ${EBUILD} ]] || FETCHED=true

LOCAL=false

say()  { printf '  %s\n' "$*"; }
step() { printf '\n\033[1m%s\033[0m\n' "$*"; }
skip() { printf '  \033[2m%s\033[0m\n' "$*"; }

# How to tell the reader to re-run us. Piped from the network there is no path
# to name, so name the command that got them here instead.
rerun_as() {
	if [[ -f ${SELF} ]]; then echo "sudo ${SELF}${*:+ $*}"
	else echo "curl -fsSL ${SELF_URL} | sudo bash${*:+ -s -- $*}"; fi
}

need_root() {
	if [[ ${EUID} -ne 0 ]]; then
		echo "This writes to /var/db/repos and /etc/portage, so it needs root:" >&2
		echo "    $(rerun_as "$@")" >&2
		exit 1
	fi
}

download() { # url destination
	if command -v curl >/dev/null; then
		curl -fsSL --proto '=https' --tlsv1.2 -o "$2" "$1"
	elif command -v wget >/dev/null; then
		wget -q --https-only -O "$2" "$1"
	else
		echo "Neither curl nor wget is installed, so there is no way to fetch" >&2
		echo "${1}. Install one of them, or clone the repository and run" >&2
		echo "packaging/make-overlay.sh out of it." >&2
		exit 1
	fi
}

# Without a clone the only things missing are the two files this script cannot
# generate. Fetch them into a temporary directory that goes away on exit, so a
# half-finished download can never be what lands in the overlay.
fetch_sources() {
	step "0/4  No clone here — fetching the ebuild from ${GENTSTORE_REF}"
	SOURCE="$(mktemp -d)"
	trap 'rm -rf -- "${SOURCE}"' EXIT
	local dir="${SOURCE}/packaging/${ATOM}"
	mkdir -p "${dir}"
	EBUILD="${dir}/gentstore-9999.ebuild"
	download "${RAW_BASE}/packaging/${ATOM}/gentstore-9999.ebuild" "${EBUILD}"
	download "${RAW_BASE}/packaging/${ATOM}/metadata.xml" "${dir}/metadata.xml"
	# A 404 page or a captive portal is still a 200 to the shell. The ebuild has
	# to look like one before it is allowed anywhere near /var/db/repos.
	if ! grep -q '^EGIT_REPO_URI=' "${EBUILD}"; then
		echo "  What came back from ${RAW_BASE} is not an ebuild." >&2
		echo "  Check the URL and the network, then try again." >&2
		exit 1
	fi
	say "fetched gentstore-9999.ebuild and metadata.xml"
}

# git-r3 fetches as the portage user, with none of your credentials. A private
# repository therefore fails in src_unpack with "could not read Username",
# which is a long way from the decision that caused it.
check_reachable() {
	command -v git >/dev/null || return 0
	if GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/true \
		timeout 20 git ls-remote "${UPSTREAM}" HEAD >/dev/null 2>&1; then
		say "checked: ${UPSTREAM} is readable without credentials"
		return 0
	fi
	cat >&2 <<-EOF

	  Warning: nothing can read ${UPSTREAM} anonymously.
	  If it is a private repository, emerge will fail in the unpack phase with
	  "could not read Username for https://github.com". Two ways out: make the
	  repository public, or re-run this script with --local to build from
	  ${SOURCE} instead.

	EOF
}

# A local build is only local if the unprivileged user doing it can read the
# clone. Home directories are 0700 often enough to be worth checking.
check_readable_by_portage() {
	local user=portage
	id "${user}" >/dev/null 2>&1 || return 0
	# su would ask for a password if we were not root, and this check is not
	# worth hanging a script over.
	[[ ${EUID} -eq 0 ]] || return 0
	if su -s /bin/sh "${user}" -c "test -r '${SOURCE}/.git/HEAD'" </dev/null 2>/dev/null; then
		say "checked: the ${user} user can read ${SOURCE}"
	else
		cat >&2 <<-EOF

		  Warning: the ${user} user cannot read ${SOURCE}/.git.
		  git-r3 fetches unprivileged, so the unpack phase will fail. Either
		  loosen the permissions on the path (chmod o+x on each directory up to
		  and including it) or keep the clone somewhere world-readable.

		EOF
	fi
}

remove() {
	need_root --remove
	step "Removing the overlay"
	for path in "${CONF}" "${ACCEPT}"; do
		if [[ -e ${path} ]]; then rm -f "${path}"; say "removed ${path}"
		else skip "not there: ${path}"; fi
	done
	if [[ -d ${REPO_PATH} ]]; then rm -rf "${REPO_PATH}"; say "removed ${REPO_PATH}"
	else skip "not there: ${REPO_PATH}"; fi
	printf '\nGone. If Gentstore is still installed, remove it with:\n    emerge --deselect --unmerge %s\n' "${ATOM}"
}

# The synced overlay: Portage clones the `overlay` branch and every later
# ebuild arrives with an ordinary `emerge --sync`. Nothing is copied here, so
# this path needs neither a clone nor the two files fetch_sources downloads.
install_synced() {
	need_root

	if [[ -d ${REPO_PATH} && ! -d ${REPO_PATH}/.git ]]; then
		echo "  ${REPO_PATH} exists and is not a git checkout — an older" >&2
		echo "  copy-mode install. Remove it first:" >&2
		echo "      $(rerun_as --remove)" >&2
		exit 1
	fi

	step "1/3  Telling Portage where to sync from — ${CONF}"
	install -d -m 0755 /etc/portage/repos.conf
	if [[ -e ${CONF} ]] && ! grep -q "location = ${REPO_PATH}" "${CONF}"; then
		echo "  ${CONF} already exists and points somewhere else. Leaving it alone." >&2
		echo "  Check it by hand, then re-run." >&2
		exit 1
	fi
	cat > "${CONF}" <<-EOF
		[${REPO_NAME}]
		location = ${REPO_PATH}
		sync-type = git
		sync-uri = ${GITHUB_REPO}
		# The ebuilds live on their own branch, because the root of this
		# repository is the application, not an overlay.
		sync-git-clone-extra-opts = --branch ${OVERLAY_BRANCH} --single-branch
		auto-sync = yes
		masters = gentoo
	EOF
	say "wrote ${CONF}"
	say "syncs from ${GITHUB_REPO} (branch ${OVERLAY_BRANCH})"

	step "2/3  Accepting the ebuilds — ${ACCEPT}"
	install -d -m 0755 "${ACCEPT_DIR}"
	cat > "${ACCEPT}" <<-EOF
		# 9999 is the live ebuild and carries no keywords at all, so it needs the
		# "**" that accepts anything. The release ebuilds are keyworded ~amd64,
		# which a stable system would otherwise refuse; the second line is what
		# lets you choose either.
		=${ATOM}-9999 **
		${ATOM} ~amd64
	EOF
	say "accepted =${ATOM}-9999 ** and ${ATOM} ~amd64"

	step "3/3  First sync"
	say "running: emaint sync -r ${REPO_NAME}"
	if emaint sync -r "${REPO_NAME}"; then
		say "synced"
	else
		echo "  The sync failed. The configuration above is written and correct;" >&2
		echo "  re-run 'emaint sync -r ${REPO_NAME}' once the network is back." >&2
		exit 1
	fi

	cat <<-EOF

	Done. The overlay is registered, synced and accepted.

	Install the release:
	    emerge --ask ${ATOM}

	Or track the git tip instead:
	    emerge --ask =${ATOM}-9999

	The overlay is a synced repository now, so "emerge --sync" (or the Sync
	step in Gentstore itself) brings in later ebuilds on its own. A live
	install is rebuilt from the newest commit by:
	    emerge --ask @live-rebuild
	EOF
}

install_overlay() {
	need_root
	${FETCHED} && fetch_sources

	# Read from the ebuild, not from `git remote`: a local remote is very likely
	# an ssh:// URL that works for you and not for the root-owned clone emerge
	# makes. Done here rather than at the top because without a clone there is
	# no ebuild to read until fetch_sources has run.
	UPSTREAM="$(sed -n 's/^EGIT_REPO_URI="\(.*\)"$/\1/p' "${EBUILD}" 2>/dev/null || true)"
	UPSTREAM="${UPSTREAM:-the URL in EGIT_REPO_URI}"

	step "1/4  The overlay itself — ${REPO_PATH}"
	install -d -m 0755 "${REPO_PATH}/metadata" "${REPO_PATH}/profiles"

	# masters = gentoo, because every eclass this ebuild inherits lives there.
	cat > "${REPO_PATH}/metadata/layout.conf" <<-'EOF'
		masters = gentoo
		thin-manifests = true
		sign-commits = false
		sign-manifests = false
		# No SRC_URI anywhere in here: the one ebuild is a live one that clones
		# from git, so there are no distfiles to checksum and no Manifest to
		# generate. That is why this script never runs "ebuild manifest".
	EOF
	say "wrote metadata/layout.conf"
	echo "${REPO_NAME}" > "${REPO_PATH}/profiles/repo_name"
	say "wrote profiles/repo_name"

	step "2/4  The package — ${ATOM}"
	install -d -m 0755 "${REPO_PATH}/${ATOM}"
	install -m 0644 "${EBUILD}" "${REPO_PATH}/${ATOM}/gentstore-9999.ebuild"
	install -m 0644 "${SOURCE}/packaging/${ATOM}/metadata.xml" \
		"${REPO_PATH}/${ATOM}/metadata.xml"
	say "copied gentstore-9999.ebuild and metadata.xml"

	if ${LOCAL}; then
		sed -i "s|^EGIT_REPO_URI=.*|EGIT_REPO_URI=\"${SOURCE}\"|" \
			"${REPO_PATH}/${ATOM}/gentstore-9999.ebuild"
		UPSTREAM="${SOURCE}"
		say "repointed EGIT_REPO_URI at ${SOURCE}"
		check_readable_by_portage
	else
		check_reachable
	fi

	step "3/4  Telling Portage the overlay exists — ${CONF}"
	install -d -m 0755 /etc/portage/repos.conf
	if [[ -e ${CONF} ]] && ! grep -q "location = ${REPO_PATH}" "${CONF}"; then
		echo "  ${CONF} already exists and points somewhere else. Leaving it alone." >&2
		echo "  Check it by hand, then re-run." >&2
		exit 1
	fi
	cat > "${CONF}" <<-EOF
		[${REPO_NAME}]
		location = ${REPO_PATH}
		# Not a synced repository: this script is what puts the ebuild there, so
		# "emaint sync -a" has nothing to fetch and correctly skips it.
		auto-sync = no
		masters = gentoo
	EOF
	say "wrote ${CONF}"

	step "4/4  Accepting the live ebuild — ${ACCEPT}"
	# 9999 carries no keywords, so without this emerge refuses it as masked.
	install -d -m 0755 "${ACCEPT_DIR}"
	local line="=${ATOM}-9999 **"
	if [[ -f ${ACCEPT} ]] && grep -qxF "${line}" "${ACCEPT}"; then
		skip "already accepted"
	else
		printf '# Gentstore is a live ebuild and has no keywords of its own.\n%s\n' \
			"${line}" > "${ACCEPT}"
		say "wrote ${line}"
	fi

	local remind=""
	${LOCAL} || remind=" — and push, since this builds from the remote"

	cat <<-EOF

	Done. The overlay is registered and the ebuild is accepted.

	Install it with:
	    emerge --ask ${ATOM}

	It builds the last commit in ${UPSTREAM},
	not your working tree. Commit before re-emerging${remind}.

	Later, to pick up new commits:
	    emerge --ask --update ${ATOM}
	EOF
}

usage() {
	if [[ -f ${SELF} ]]; then
		sed -n '2,31p' "${SELF}" | sed 's/^# \?//'
	else
		cat <<-EOF
		Put Gentstore into an overlay so Portage can install, update and remove it.

		    curl -fsSL ${SELF_URL} | sudo bash
		    curl -fsSL ${SELF_URL} | sudo bash -s -- --no-sync
		    curl -fsSL ${SELF_URL} | sudo bash -s -- --remove

		By default this registers a synced overlay: Portage clones the
		${OVERLAY_BRANCH} branch, and later ebuilds arrive with an ordinary
		"emerge --sync" without another visit here. --no-sync pins a copy that
		never changes under you instead.

		It never runs emerge, and prints the command to run instead. --local
		needs a clone, so it is not available here. For the full commentary,
		read the script rather than piping it:

		    curl -fsSL -O ${SELF_URL}
		EOF
	fi
}

case "${1:-}" in
	--remove|-r) remove ;;
	--help|-h)   usage ;;
	--local|-l)
		if ${FETCHED}; then
			echo "--local builds from a working tree, and there is no clone here." >&2
			echo "Clone the repository and run packaging/make-overlay.sh out of it." >&2
			exit 1
		fi
		LOCAL=true; install_overlay ;;
	# A pinned overlay that never changes under you: the ebuild is copied in
	# once and Portage is told not to sync it. What the installer did before
	# syncing existed, kept for anyone who wants exactly that.
	--no-sync|-n) install_overlay ;;
	"")          install_synced ;;
	*)           echo "Unknown option: $1 (try --help)" >&2; exit 1 ;;
esac
