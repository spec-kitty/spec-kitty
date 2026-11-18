"""Helpers for mapping canonical skill roots between project and user scopes."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat

from specify_cli.tool_surface.operations import FileState

from specify_cli.core.config import AGENT_SKILL_CONFIG, SKILL_CLASS_WRAPPER

#: Claude Code reads its user configuration from this directory when it is set
#: (default ``~/.claude``), so user-global commands and skills must land there (#7701).
CLAUDE_CONFIG_DIR_ENV = "CLAUDE_CONFIG_DIR"
_CLAUDE_AGENT_KEY = "claude"
_CLAUDE_PROJECT_DIR = ".claude"


def get_claude_user_config_root() -> Path:
    """Return Claude Code's user-global config root: ``$CLAUDE_CONFIG_DIR`` when set, else ``~/.claude``."""
    custom = os.environ.get(CLAUDE_CONFIG_DIR_ENV)
    if custom:
        return Path(custom).expanduser()
    return Path.home() / _CLAUDE_PROJECT_DIR


def get_primary_project_skill_root(agent_key: str) -> str | None:
    """Return the primary project-local skill root for an agent."""
    config = AGENT_SKILL_CONFIG.get(agent_key)
    if config is None or config["class"] == SKILL_CLASS_WRAPPER:
        return None

    roots = config["skill_roots"]
    if not isinstance(roots, list) or not roots:
        return None

    root = roots[0]
    return root if isinstance(root, str) else None


def get_primary_global_skill_root(agent_key: str) -> Path | None:
    """Return the user-global canonical skill root for an agent.

    The global root mirrors the project-local root beneath the user's home
    directory, for example:

    - ``.claude/skills`` -> ``~/.claude/skills``
    - ``.agents/skills`` -> ``~/.agents/skills``

    Claude Code's root follows ``$CLAUDE_CONFIG_DIR`` when it is set
    (``.claude/skills`` -> ``$CLAUDE_CONFIG_DIR/skills``).
    """
    root = get_primary_project_skill_root(agent_key)
    if root is None:
        return None

    normalized = root.strip("/")
    if agent_key == _CLAUDE_AGENT_KEY:
        parts = Path(normalized).parts
        if parts and parts[0] == _CLAUDE_PROJECT_DIR:
            return get_claude_user_config_root().joinpath(*parts[1:])
    return Path.home() / normalized


def get_project_skill_root_for_global_root(global_root: Path) -> str | None:
    """Return the project-relative skill root whose user-global root is *global_root*, if any."""
    for agent_key in iter_installable_agents():
        if get_primary_global_skill_root(agent_key) == global_root:
            root = get_primary_project_skill_root(agent_key)
            return None if root is None else root.strip("/")
    return None


def iter_installable_agents() -> list[str]:
    """Return all agents that support a skill root."""
    installable: list[str] = []

    for agent_key, config in AGENT_SKILL_CONFIG.items():
        if config["class"] == SKILL_CLASS_WRAPPER:
            continue
        installable.append(agent_key)

    return installable


@dataclass(frozen=True)
class SkillPathObservation:
    """Immutable node identity used by the managed-skill pre-write boundary."""

    path: Path
    state: FileState
    identity: tuple[int, int] | None = None
    children: tuple[str, ...] | None = None


def observe_skill_path(path: Path, *, members: bool = False) -> SkillPathObservation:
    """Observe a node without following its final symlink."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return SkillPathObservation(path, FileState("absent"))
    mode = stat.S_IMODE(info.st_mode)
    identity = info.st_dev, info.st_ino
    if stat.S_ISLNK(info.st_mode):
        state = FileState("symlink", target=os.readlink(path), mode=mode, mtime_ns=info.st_mtime_ns)
    elif stat.S_ISDIR(info.st_mode):
        children = tuple(sorted(child.name for child in path.iterdir())) if members else None
        return SkillPathObservation(path, FileState("directory", mode=mode), identity, children)
    elif stat.S_ISREG(info.st_mode):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()  # noqa: TID251 -- managed file integrity, not charter hashing
        state = FileState("file", sha256=digest, mode=mode, mtime_ns=info.st_mtime_ns)
    else:
        raise ValueError(f"Unsupported managed-skill node: {path}")
    return SkillPathObservation(path, state, identity)


def skill_path_observations(root: Path, path: Path) -> tuple[SkillPathObservation, ...]:
    """Check confined lexical ancestry before reading a managed path."""
    relative = path.relative_to(root)
    if any(part in {"..", "."} for part in relative.parts):
        raise ValueError(f"Unsafe managed-skill path: {path}")
    observations = []
    for parent in (root, *(root / Path(*relative.parts[:i]) for i in range(1, len(relative.parts)))):
        observed = observe_skill_path(parent)
        if observed.state.kind not in {"absent", "directory"}:
            raise ValueError(f"Managed-skill parent is not a directory: {parent}")
        observations.append(observed)
    observations.append(observe_skill_path(path))
    return tuple(observations)


def recheck_skill_paths(observations: tuple[SkillPathObservation, ...]) -> None:
    """Refuse the complete input set before writing, including parent identity."""
    for previous in observations:
        current = observe_skill_path(previous.path, members=previous.children is not None)
        if current != previous:
            raise ValueError(f"Managed-skill input changed: {previous.path}")
