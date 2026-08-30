#!/usr/bin/env bash
# Put Gentstore into a local overlay so Portage can install and remove it.
#
#     sudo packaging/make-overlay.sh            build from EGIT_REPO_URI
#     sudo packaging/make-overlay.sh --local     build from this working tree
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

SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
EBUILD="${SOURCE}/packaging/${ATOM}/gentstore-9999.ebuild"
# Read from the ebuild, not from `git remote`: the local remote is very likely
# an ssh:// URL that works for you and not for the root-owned clone emerge makes.
UPSTREAM="$(sed -n 's/^EGIT_REPO_URI="\(.*\)"$/\1/p' "${EBUILD}" 2>/dev/null || true)"
UPSTREAM="${UPSTREAM:-the URL in EGIT_REPO_URI}"

LOCAL=false

say()  { printf '  %s\n' "$*"; }
step() { printf '\n\033[1m%s\033[0m\n' "$*"; }
skip() { printf '  \033[2m%s\033[0m\n' "$*"; }

need_root() {
	if [[ ${EUID} -ne 0 ]]; then
		echo "This writes to /var/db/repos and /etc/portage, so it needs root:" >&2
		echo "    sudo $0${*:+ $*}" >&2
		exit 1
	fi
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

install_overlay() {
	need_root
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

case "${1:-}" in
	--remove|-r) remove ;;
	--help|-h)   sed -n '2,20p' "$0" | sed 's/^# \?//' ;;
	--local|-l)  LOCAL=true; install_overlay ;;
	"")          install_overlay ;;
	*)           echo "Unknown option: $1 (try --help)" >&2; exit 1 ;;
esac
