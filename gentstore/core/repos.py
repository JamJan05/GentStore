"""Reading ``repos.conf``: which repositories exist and what state they are in.

Only the read half lives here. Enabling, adding, syncing and removing overlays —
everything that runs ``eselect repository`` or writes to ``/etc/portage`` — comes
in session S7, together with the ``repositories.xml`` catalogue of overlays that
are *not* installed yet.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .confedit import WritePlan, plan_entry, plan_removal, read_entries
from .portage_env import PortageEnv
from .portage_env import env as _default_env

log = logging.getLogger(__name__)

#: Where a repository records when it was last updated, best source first.
#: ``timestamp.chk`` is written by rsync syncs, ``timestamp.x`` by git ones, and
#: the git metadata is the last resort for overlays that write neither.
_TIMESTAMP_FILES = (
    "metadata/timestamp.chk",
    "metadata/timestamp.x",
    "metadata/timestamp",
    ".git/FETCH_HEAD",
    ".git/HEAD",
)


@dataclass(frozen=True, slots=True)
class RepositoryInfo:
    """One entry of ``repos.conf``, as Portage understands it."""

    name: str
    location: str
    priority: int | None
    sync_type: str | None
    sync_uri: str | None
    auto_sync: str | None
    masters: tuple[str, ...]
    is_main: bool
    last_sync: datetime | None
    package_count: int | None

    @property
    def is_official(self) -> bool:
        """Whether this is the main ``::gentoo`` repository.

        The "Only ::gentoo" switch is built on exactly this distinction, so it
        is named rather than re-derived at each call site.
        """
        return self.is_main

    @property
    def config_file(self) -> Path | None:
        """The most likely ``repos.conf`` file for this repository.

        A guess, not a fact: ``repos.conf`` may be a single file holding every
        repository. It is used only as a starting point for "show me the file",
        never for writing.
        """
        candidate = Path("/etc/portage/repos.conf") / f"{self.name}.conf"
        return candidate if candidate.is_file() else None


def _last_sync(location: str) -> datetime | None:
    base = Path(location)
    for name in _TIMESTAMP_FILES:
        stamp = base / name
        try:
            if stamp.is_file():
                return datetime.fromtimestamp(stamp.stat().st_mtime)
        except OSError:  # pragma: no cover - racing with a running sync
            continue
    try:
        return datetime.fromtimestamp(base.stat().st_mtime)
    except OSError:
        return None


def list_repositories(
    env: PortageEnv | None = None, *, count_packages: bool = True
) -> tuple[RepositoryInfo, ...]:
    """Every configured repository, in Portage's priority order.

    Counting packages costs roughly a fifth of a second per repository, so it is
    optional: the status bar does not need it, the repositories screen does.
    """
    env = env or _default_env()
    main = env.main_repo_name
    result: list[RepositoryInfo] = []

    for repo in env.repos():
        location = getattr(repo, "location", "") or ""
        count = None
        if count_packages and location:
            try:
                count = len(env.portdb.cp_all(trees=[location]))
            except Exception:  # pragma: no cover - a repository being synced
                log.warning("Could not count packages in %s", repo.name, exc_info=True)
        result.append(
            RepositoryInfo(
                name=repo.name,
                location=location,
                priority=getattr(repo, "priority", None),
                sync_type=getattr(repo, "sync_type", None),
                sync_uri=getattr(repo, "sync_uri", None),
                auto_sync=getattr(repo, "auto_sync", None),
                masters=tuple(m.name for m in getattr(repo, "masters", ()) or ()),
                is_main=repo.name == main,
                last_sync=_last_sync(location) if location else None,
                package_count=count,
            )
        )
    return tuple(result)


def repository(
    name: str, env: PortageEnv | None = None, *, count_packages: bool = False
) -> RepositoryInfo | None:
    """One repository by name, or ``None`` when it is not configured."""
    entries = list_repositories(env, count_packages=count_packages)
    return next((r for r in entries if r.name == name), None)


# ---------------------------------------------------------------------------
# what came from where
# ---------------------------------------------------------------------------


def installed_from(repo: str, env: PortageEnv | None = None) -> tuple[str, ...]:
    """Installed packages that came out of *repo*.

    The number that matters before removing an overlay: those packages stay on
    the system but stop having an ebuild behind them, so nothing will ever
    update or rebuild them again.
    """
    env = env or _default_env()
    found = []
    for cpv in env.vardb.cpv_all():
        try:
            if env.vardb.aux_get(cpv, ["repository"])[0] == repo:
                found.append(str(cpv))
        except Exception:  # pragma: no cover - a half-written /var/db/pkg entry
            continue
    return tuple(sorted(found))


def config_files(
    env: PortageEnv | None = None, config_dir: Path | None = None
) -> tuple[Path, ...]:
    """The ``repos.conf`` files in effect, so the interface can show them.

    ``eselect repository`` writes every repository it manages into one
    ``eselect-repo.conf`` rather than a file each, which is worth showing as it
    really is rather than as the tidier arrangement one might expect.
    """
    if config_dir is not None:
        directory = config_dir / "repos.conf"
    else:
        base = Path(env.settings.get("PORTAGE_CONFIGROOT", "/")) if env else Path("/")
        directory = base / "etc" / "portage" / "repos.conf"
    if directory.is_dir():
        return tuple(sorted(item for item in directory.iterdir() if item.is_file()))
    if directory.is_file():
        return (directory,)
    return ()


def config_section(
    repo: str, env: PortageEnv | None = None, config_dir: Path | None = None
) -> tuple[Path, str] | None:
    """The ``[repo]`` block that defines *repo*, and the file it is in."""
    header = f"[{repo}]"
    for path in config_files(env, config_dir):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:  # pragma: no cover
            continue
        if header not in (line.strip() for line in lines):
            continue
        collected: list[str] = []
        inside = False
        for line in lines:
            stripped = line.strip()
            if stripped == header:
                inside = True
            elif inside and stripped.startswith("[") and stripped.endswith("]"):
                break
            if inside:
                collected.append(line)
        return path, "\n".join(collected).strip()
    return None


# ---------------------------------------------------------------------------
# hiding a whole repository from Portage
# ---------------------------------------------------------------------------

#: What "only ::gentoo, for real" writes: every package from one repository.
MASK_FILE = "package.mask"


def mask_atom(repo: str) -> str:
    return f"*/*::{repo}"


def is_masked(repo: str, env: PortageEnv | None = None, config_dir: Path | None = None) -> bool:
    """Whether ``*/*::repo`` is already in ``package.mask``."""
    atom = mask_atom(repo)
    return any(
        line.split()[0] == atom
        for _path, line in read_entries(MASK_FILE, env, config_dir)
        if line.split()
    )


def masked_repos(
    env: PortageEnv | None = None, config_dir: Path | None = None
) -> frozenset[str]:
    """Every repository currently masked wholesale."""
    found = set()
    for _path, line in read_entries(MASK_FILE, env, config_dir):
        token = line.split()[0] if line.split() else ""
        if token.startswith("*/*::"):
            found.add(token.removeprefix("*/*::"))
    return frozenset(found)


def plan_mask(
    repo: str, env: PortageEnv | None = None, config_dir: Path | None = None
) -> WritePlan:
    """Plan the line that stops Portage offering anything from *repo*.

    The repository keeps syncing and its files stay on disk; Portage simply
    stops considering its ebuilds. Reversible with one line removed, which is
    the whole reason this is done with a mask rather than by disabling the
    repository.
    """
    return plan_entry(
        MASK_FILE, mask_atom(repo), mask_atom(repo), (), env, config_dir, target_name=repo
    )


def plan_unmask(
    repo: str, env: PortageEnv | None = None, config_dir: Path | None = None
) -> WritePlan:
    return plan_removal(
        MASK_FILE, mask_atom(repo), mask_atom(repo), env, config_dir, target_name=repo
    )
