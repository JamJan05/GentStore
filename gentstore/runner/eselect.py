"""Command lines for managing repositories.

``eselect repository`` is the supported way to add and remove overlays on
Gentoo, and using it rather than writing ``repos.conf`` ourselves means the
result looks exactly like one made from a terminal — including landing in the
same ``eselect-repo.conf``, which is where anyone looking for it will look.

Refreshing the catalogue is the one command here that needs no privileges: it
writes to the user's own cache, and it is also the only thing in Gentstore that
reaches the network on its own account, which is why it is a visible command in
the log rather than a quiet download.
"""

from __future__ import annotations

from .command import CommandSpec


def list_repositories() -> CommandSpec:
    """``eselect repository list`` — fetches and caches ``repositories.xml``."""
    return CommandSpec(
        argv=("eselect", "repository", "list"),
        privileged=False,
        description="catalogue",
    )


def enable(name: str) -> CommandSpec:
    """Add a repository from the published catalogue."""
    return CommandSpec(
        argv=("eselect", "repository", "enable", name),
        privileged=True,
        description="enable repository",
    )


def add(name: str, sync_type: str, uri: str) -> CommandSpec:
    """Add a repository that is *not* in the catalogue.

    The riskier door of the two: nobody has vouched for this source, and its
    ebuilds run as root while building. The screen says so before getting here.
    """
    return CommandSpec(
        argv=("eselect", "repository", "add", name, sync_type, uri),
        privileged=True,
        description="add repository",
    )


def disable(name: str, *, force: bool = False) -> CommandSpec:
    """Stop using a repository but leave its files on disk."""
    return CommandSpec(
        argv=("eselect", "repository", "disable", *(("-f",) if force else ()), name),
        privileged=True,
        description="disable repository",
    )


def remove(name: str, *, force: bool = True) -> CommandSpec:
    """Remove a repository and delete its checkout.

    ``-f`` is the default because without it eselect refuses whenever anything
    is installed from the repository — which is precisely the case the interface
    has already warned about and had confirmed.
    """
    return CommandSpec(
        argv=("eselect", "repository", "remove", *(("-f",) if force else ()), name),
        privileged=True,
        description="remove repository",
    )


def sync(name: str) -> CommandSpec:
    """``emaint sync -r <name>`` — the supported way to sync one repository."""
    return CommandSpec(
        argv=("emaint", "sync", "-r", name),
        privileged=True,
        description="sync repository",
    )


def sync_all() -> CommandSpec:
    return CommandSpec(
        argv=("emaint", "sync", "-a"), privileged=True, description="sync all"
    )


def read_news(*, privileged: bool) -> CommandSpec:
    """``eselect news read`` — mark every unread item as read.

    Whether this needs privileges depends on the machine: the state lives in
    ``/var/lib/gentoo/news``, which is group-writable by ``portage``. Users in
    that group can do it themselves; everybody else goes through pkexec, and
    asking for a password that changes nothing would be rude.
    """
    return CommandSpec(
        argv=("eselect", "news", "read"),
        privileged=privileged,
        description="mark news read",
    )


def check_glsa() -> CommandSpec:
    """``glsa-check -l affected`` — advisories this system may be exposed to."""
    return CommandSpec(
        argv=("glsa-check", "-l", "affected"),
        privileged=False,
        description="security advisories",
        environment={"LC_ALL": "C.UTF-8", "NOCOLOR": "true"},
    )


def fix_glsa(identifiers: tuple[str, ...] = ()) -> CommandSpec:
    """``glsa-check -f`` — install the fixes for the named advisories."""
    return CommandSpec(
        argv=("glsa-check", "-f", *(identifiers or ("affected",))),
        privileged=True,
        description="apply security fixes",
    )


def list_profiles() -> CommandSpec:
    """``eselect profile list`` — reads a symlink, needs no privileges."""
    return CommandSpec(
        argv=("eselect", "profile", "list"),
        privileged=False,
        description="profiles",
        environment={"LC_ALL": "C.UTF-8", "NOCOLOR": "true"},
    )


def set_profile(index: int) -> CommandSpec:
    """``eselect profile set N`` — repoints /etc/portage/make.profile.

    By number rather than by path, because the number is what eselect itself
    prints and what the user would type; the screen shows the path beside it so
    nobody has to trust the number alone.
    """
    return CommandSpec(
        argv=("eselect", "profile", "set", str(index)),
        privileged=True,
        description="set profile",
    )
