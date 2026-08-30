"""USE flags: what they are set to, who set them, and what they mean.

This is the part of Gentstore that exists because ``emerge`` cannot easily tell
you. Portage will happily report that ``vulkan`` is on; what it will not say in
one place is that it is on *because the ebuild enables it by default*, that the
profile could have turned it off, that ``lua_single_target_luajit`` is forced and
cannot be changed at all, or what any of them actually do.

Five layers decide a flag, lowest priority first:

1. the ebuild's own default — ``+flag`` in ``IUSE``;
2. the profile;
3. ``USE`` in ``make.conf``;
4. ``/etc/portage/package.use``;
5. ``USE`` in the environment.

On top of that, ``use.force`` and ``use.mask`` (and their per-package variants)
take a flag out of the user's hands entirely. Those are shown as locked rather
than hidden: "you cannot change this, and here is why" is information, and
silently omitting a flag somebody read about in the handbook is not.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from xml.etree import ElementTree

from .portage_env import PortageEnv
from .portage_env import env as _default_env

log = logging.getLogger(__name__)


class FlagSource(StrEnum):
    """Which layer decided a flag's current value."""

    EBUILD = "ebuild"
    PROFILE = "profile"
    MAKE_CONF = "make.conf"
    PACKAGE_USE = "package.use"
    ENVIRONMENT = "environment"
    #: Nobody mentions it, so it is off — the default default.
    DEFAULT_OFF = "default"


class FlagLock(StrEnum):
    """Whether the flag can be changed at all."""

    NONE = "none"
    #: ``use.force`` — always on, changing it would be ignored.
    FORCED = "forced"
    #: ``use.mask`` — always off, usually because it does not work here.
    MASKED = "masked"


class DescriptionSource(StrEnum):
    METADATA = "metadata.xml"
    LOCAL = "use.local.desc"
    GLOBAL = "use.desc"
    EXPAND = "desc"
    NONE = ""


@dataclass(frozen=True, slots=True)
class UseFlag:
    """One flag of one package."""

    name: str
    #: The value Portage would use right now.
    enabled: bool
    #: What it would be without ``/etc/portage/package.use``.
    #:
    #: The difference between this and :attr:`enabled` is exactly what belongs
    #: in a ``package.use`` line, which is why it is carried around rather than
    #: recomputed: writing out a flag that the profile already sets is noise
    #: that will one day disagree with a profile update.
    baseline: bool
    source: FlagSource
    lock: FlagLock
    #: Where the lock came from: ``profile`` or ``package``. Empty when unlocked.
    lock_scope: str
    description: str
    description_source: DescriptionSource
    #: ``PYTHON_SINGLE_TARGET`` and friends: one variable, many flags.
    expand_variable: str

    @property
    def is_locked(self) -> bool:
        return self.lock is not FlagLock.NONE

    @property
    def is_overridden(self) -> bool:
        """Set by ``package.use`` to something other than the default."""
        return self.enabled != self.baseline

    @property
    def is_expand(self) -> bool:
        return bool(self.expand_variable)

    @property
    def label(self) -> str:
        """What to show. Expanded flags carry a prefix nobody needs to read."""
        if not self.expand_variable:
            return self.name
        prefix = f"{self.expand_variable.lower()}_"
        return self.name[len(prefix):] if self.name.startswith(prefix) else self.name


@dataclass(frozen=True, slots=True)
class UseState:
    """Every flag of one package, plus the rule that constrains them."""

    cpv: str
    cp: str
    repo: str
    flags: tuple[UseFlag, ...]
    required_use: str

    def flag(self, name: str) -> UseFlag | None:
        return next((item for item in self.flags if item.name == name), None)

    @property
    def enabled(self) -> frozenset[str]:
        return frozenset(item.name for item in self.flags if item.enabled)

    @property
    def changeable(self) -> tuple[UseFlag, ...]:
        return tuple(item for item in self.flags if not item.is_locked)

    def grouped(self) -> tuple[tuple[str, tuple[UseFlag, ...]], ...]:
        """Plain flags first, then one group per ``USE_EXPAND`` variable.

        Twenty ``python_single_target_*`` entries mixed in with ``alsa`` and
        ``vulkan`` bury the flags somebody actually came to look at.
        """
        plain = tuple(item for item in self.flags if not item.is_expand)
        groups: dict[str, list[UseFlag]] = {}
        for item in self.flags:
            if item.is_expand:
                groups.setdefault(item.expand_variable, []).append(item)
        return (("", plain), *((name, tuple(items)) for name, items in sorted(groups.items())))


# ---------------------------------------------------------------------------
# reading the configuration
# ---------------------------------------------------------------------------

#: ``config.setcpv()`` mutates the object it is called on, so the clone used for
#: it never leaves this module and only one thread reads it at a time.
_lock = threading.Lock()
_clone = None
_clone_for: PortageEnv | None = None


def _configured(env: PortageEnv, cpv: str, repo: str):  # noqa: ANN202 - portage type
    """A configuration with ``setcpv`` applied for *cpv*. Call under ``_lock``."""
    global _clone, _clone_for
    import portage  # noqa: PLC0415 — slow import, deferred

    if _clone is None or _clone_for is not env:
        _clone = portage.config(clone=env.settings)
        _clone_for = env
    _clone.setcpv(cpv, mydb=env.portdb)
    return _clone


def clear_caches() -> None:
    """Forget the cloned configuration and the parsed description files."""
    global _clone, _clone_for
    with _lock:
        _clone = None
        _clone_for = None
    _GLOBAL_DESCRIPTIONS.clear()
    _EXPAND_DESCRIPTIONS.clear()
    _LOCAL_DESCRIPTIONS.clear()


def _split(value: str | None) -> list[str]:
    return (value or "").split()


def _layer_state(layer: list[str], flag: str) -> bool | None:
    """What *layer* says about *flag*: ``True``, ``False`` or nothing.

    Scanned from the end, and that is the whole point of keeping these as lists
    rather than sets. Portage flattens the profile stack by concatenating each
    profile's ``USE`` in order, so a single layer routinely contains both
    ``sdl`` and ``-sdl`` — one profile turning it on, a later one turning it
    back off. Set membership cannot tell those apart and would have reported
    ``sdl`` as enabled for every package on this system.
    """
    for token in reversed(layer):
        if token == flag:
            return True
        if token == f"-{flag}":
            return False
    return None


def collect(cpv: str, repo: str = "", env: PortageEnv | None = None) -> UseState:
    """Everything about one package's USE flags."""
    env = env or _default_env()
    cp = _cp_of(cpv)

    with _lock:
        settings = _configured(env, cpv, repo)
        iuse_raw, required_use = env.portdb.aux_get(
            cpv, ["IUSE", "REQUIRED_USE"], myrepo=repo or None
        )
        effective = _split(settings.get("PORTAGE_USE"))
        layers = {
            FlagSource.ENVIRONMENT: _split(os.environ.get("USE")),
            FlagSource.PACKAGE_USE: _split(settings.configdict["pkg"].get("USE")),
            FlagSource.MAKE_CONF: _split(settings.configdict["conf"].get("USE")),
            FlagSource.PROFILE: _split(settings.configdict["defaults"].get("USE")),
            FlagSource.EBUILD: _split(settings.configdict["pkginternal"].get("USE")),
        }
        masked = set(settings.usemask)
        forced = set(settings.useforce)
        expand_variables = tuple((settings.get("USE_EXPAND") or "").split())
        repo_location = env.repo_location(repo or _repo_of(env, cpv)) or ""

    descriptions = _Descriptions(repo_location, cp)
    flags = []
    for name in sorted({token.lstrip("+-") for token in iuse_raw.split()}):
        source = next(
            (layer for layer, values in layers.items() if _layer_state(values, name) is not None),
            FlagSource.DEFAULT_OFF,
        )
        lock, scope = _lock_of(name, masked, forced, layers)
        baseline = _baseline(name, layers)
        variable = _expand_variable(name, expand_variables)
        text, origin = descriptions.for_flag(name, variable)
        flags.append(
            UseFlag(
                name=name,
                enabled=name in effective,
                baseline=baseline,
                source=source,
                lock=lock,
                lock_scope=scope,
                description=text,
                description_source=origin,
                expand_variable=variable,
            )
        )

    return UseState(
        cpv=cpv, cp=cp, repo=repo, flags=tuple(flags), required_use=required_use
    )


def _baseline(name: str, layers: dict[FlagSource, list[str]]) -> bool:
    """What the flag would be with ``package.use`` taken out of the picture."""
    for layer in (
        FlagSource.ENVIRONMENT,
        FlagSource.MAKE_CONF,
        FlagSource.PROFILE,
        FlagSource.EBUILD,
    ):
        state = _layer_state(layers[layer], name)
        if state is not None:
            return state
    return False


def _lock_of(
    name: str, masked: set[str], forced: set[str], layers: dict[FlagSource, list[str]]
) -> tuple[FlagLock, str]:
    """Whether the flag is out of the user's hands, and roughly on whose orders.

    Portage does not report which file a mask came from, so the scope is
    inferred: a flag that ``package.use`` also mentions was almost certainly
    masked for this package, anything else comes from the profile. It is a hint
    for the interface, never the basis of a decision.
    """
    if name in masked:
        return FlagLock.MASKED, "package" if name in layers[FlagSource.PACKAGE_USE] else "profile"
    if name in forced:
        return FlagLock.FORCED, "package" if name in layers[FlagSource.PACKAGE_USE] else "profile"
    return FlagLock.NONE, ""


def _expand_variable(name: str, variables: tuple[str, ...]) -> str:
    """``python_single_target_python3_14`` → ``PYTHON_SINGLE_TARGET``."""
    best = ""
    for variable in variables:
        prefix = f"{variable.lower()}_"
        # Longest match wins: ABI_X86 and ABI_X86_32 would both claim a flag.
        if name.startswith(prefix) and len(prefix) > len(best):
            best = variable
    return best


def _cp_of(cpv: str) -> str:
    from portage.versions import cpv_getkey  # noqa: PLC0415 — slow import

    return cpv_getkey(cpv) or cpv


def _repo_of(env: PortageEnv, cpv: str) -> str:
    try:
        return env.portdb.aux_get(cpv, ["repository"])[0]
    except Exception:  # pragma: no cover - the ebuild went away
        return env.main_repo_name or ""


@dataclass(frozen=True, slots=True)
class UsePicture:
    """Everything the flag panel needs, gathered in one call.

    The two halves come from different places and cost very different amounts —
    reading the descriptions dominates — so they are fetched together, once, on
    a worker thread, rather than leaving the screen to make two round trips.
    """

    state: UseState
    effects: dict[str, object]


def picture(cpv: str, repo: str = "", env: PortageEnv | None = None) -> UsePicture:
    """The flag state and what each flag pulls in."""
    from .depgraph_hints import effects as _effects  # noqa: PLC0415 — avoids a cycle

    env = env or _default_env()
    return UsePicture(state=collect(cpv, repo, env), effects=_effects(cpv, repo, env))


# ---------------------------------------------------------------------------
# descriptions
# ---------------------------------------------------------------------------

_GLOBAL_DESCRIPTIONS: dict[str, dict[str, str]] = {}
_EXPAND_DESCRIPTIONS: dict[tuple[str, str], dict[str, str]] = {}
_LOCAL_DESCRIPTIONS: dict[tuple[str, str], dict[str, str]] = {}

_DESC_LINE = re.compile(r"^([^\s#][^\s]*)\s+-\s+(.*)$")


class _Descriptions:
    """Where a flag's one-line description comes from, most specific first.

    ``metadata.xml`` is written by the package's own maintainer and is the only
    one that can talk about *this* package; ``use.local.desc`` is the same text
    flattened into one huge file; ``use.desc`` describes flags that mean roughly
    the same thing everywhere.
    """

    def __init__(self, repo_location: str, cp: str) -> None:
        self._location = repo_location
        self._cp = cp
        self._metadata = _metadata_descriptions(repo_location, cp)
        self._local = _local_descriptions(repo_location, cp)

    def for_flag(self, name: str, expand_variable: str) -> tuple[str, DescriptionSource]:
        if name in self._metadata:
            return self._metadata[name], DescriptionSource.METADATA
        if name in self._local:
            return self._local[name], DescriptionSource.LOCAL
        if expand_variable:
            values = _expand_descriptions(self._location, expand_variable)
            value = name[len(expand_variable) + 1:]
            if value in values:
                return values[value], DescriptionSource.EXPAND
        globals_ = _global_descriptions(self._location)
        if name in globals_:
            return globals_[name], DescriptionSource.GLOBAL
        return "", DescriptionSource.NONE


def _parse_desc(path: Path, strip_prefix: str = "") -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        with path.open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                if strip_prefix and not line.startswith(strip_prefix):
                    continue
                match = _DESC_LINE.match(line[len(strip_prefix):].rstrip())
                if match:
                    result[match.group(1)] = match.group(2)
    except OSError:
        return {}
    return result


def _global_descriptions(location: str) -> dict[str, str]:
    if location not in _GLOBAL_DESCRIPTIONS:
        _GLOBAL_DESCRIPTIONS[location] = _parse_desc(Path(location) / "profiles" / "use.desc")
    return _GLOBAL_DESCRIPTIONS[location]


def _expand_descriptions(location: str, variable: str) -> dict[str, str]:
    key = (location, variable)
    if key not in _EXPAND_DESCRIPTIONS:
        path = Path(location) / "profiles" / "desc" / f"{variable.lower()}.desc"
        _EXPAND_DESCRIPTIONS[key] = _parse_desc(path)
    return _EXPAND_DESCRIPTIONS[key]


def _local_descriptions(location: str, cp: str) -> dict[str, str]:
    """The ``cat/pkg:flag - text`` lines for one package.

    ``use.local.desc`` is three quarters of a megabyte, so it is scanned for the
    one prefix that matters rather than parsed whole — about ten milliseconds —
    and the answer is kept.
    """
    key = (location, cp)
    if key not in _LOCAL_DESCRIPTIONS:
        path = Path(location) / "profiles" / "use.local.desc"
        _LOCAL_DESCRIPTIONS[key] = _parse_desc(path, strip_prefix=f"{cp}:")
    return _LOCAL_DESCRIPTIONS[key]


def _metadata_descriptions(location: str, cp: str) -> dict[str, str]:
    """``<use><flag name="…">`` from the package's own ``metadata.xml``."""
    path = Path(location) / cp / "metadata.xml"
    try:
        tree = ElementTree.parse(path)
    except (OSError, ElementTree.ParseError):
        return {}

    result: dict[str, str] = {}
    for element in tree.getroot().iterfind("./use/flag"):
        name = element.get("name")
        if not name:
            continue
        # itertext(), not .text: descriptions embed <pkg> and <code> elements,
        # and taking only .text would truncate at the first one.
        text = " ".join("".join(element.itertext()).split())
        if text:
            result[name] = text
    return result
