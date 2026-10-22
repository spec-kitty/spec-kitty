"""Which agent-folder paths Spec Kitty owns, and so gitignores (#6474).

Spec Kitty used to ignore whole agent folders (``.claude/``, ``.gemini/``,
``.kiro/`` ...), which also hid the files a team commits there on purpose:
``.claude/settings.json``, ``.claude/rules/``, ``.kiro/steering/``. The ignore
set is now narrow, and is computed here from the configured agents:

- **Secrets and runtime state**, for every agent whether configured or not:
  credential and local-only files (``.codex/auth.json``, ``.gemini/.env``,
  ``.claude/settings.local.json`` ...) and the state folders of Vibe, Pi,
  Letta and Copilot. These guard a credential, not ownership, so they never
  depend on config.
- **Generated command files** (``<command dir>/spec-kitty.*``) for each
  configured slash-command agent.
- **Generated skill folders** in each configured agent's primary skill root
  (and, for every project, Spec Kitty's reserved names in ``.agents/skills/``):
  the reserved ``spec-kitty``/``spec-kitty-*``/``spec-kitty.*``/``spk-*``
  names, the shipped built-in skills with other names, and every pack-skill
  folder the skills manifest records for that agent.
- **Projected agent profiles** that the profile manifest records
  (``.claude/agents/<id>.md`` ...).
- **Generated session files** that Spec Kitty writes whole
  (``.cursor/rules/spec-kitty.mdc``, ``.windsurf/rules/spec-kitty.md``,
  ``.kiro/steering/spec-kitty.md``). Files Spec Kitty only appends a section to
  (``.claude/CLAUDE.md``, ``AGENTS.md``) stay the team's.

The result feeds :meth:`specify_cli.gitignore_manager.GitignoreManager.sync_agent_block`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable, Sequence
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from specify_cli.core.config import AGENT_COMMAND_CONFIG, AGENT_SKILL_CONFIG, AI_CHOICES

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "SECRET_ENTRIES",
    "STATE_DIR_ENTRIES",
    "agent_ignore_entries",
    "ignored_agent_keys",
]

#: Credential and local-only files inside folders that otherwise hold team config.
#: ``.codex/`` also covers a project-local ``CODEX_HOME`` (history, sessions, logs);
#: the Gemini CLI family reads an API key from ``.env`` in its project folder.
SECRET_ENTRIES: tuple[str, ...] = (
    ".codex/auth.json",
    ".codex/history.jsonl",
    ".codex/sessions/",
    ".codex/log/",
    ".claude/settings.local.json",
    ".gemini/.env",
    ".qwen/.env",
    ".llxprt/.env",
)

#: Folders that hold an agent's runtime state, sessions or auth; ignored whole.
STATE_DIR_ENTRIES: tuple[str, ...] = (".vibe/", ".pi/", ".letta/", ".github/copilot/")

#: Skill-folder names reserved for Spec Kitty (CLAUDE.md, "Pack skills").
_RESERVED_SKILL_DIR_PATTERNS: tuple[str, ...] = ("spec-kitty/", "spec-kitty-*/", "spec-kitty.*/", "spk-*/")

#: The shared skills root. Its reserved names are Spec Kitty's projection whatever the
#: configured agents (``skills.ownership.is_projected_skills_path`` is agent-agnostic),
#: and earlier releases projected there for every agent, so they stay ignored always.
_SHARED_SKILL_ROOT = ".agents/skills/"

_COMMAND_FILE_PATTERN = "spec-kitty.*"


def ignored_agent_keys(project_path: Path) -> tuple[str, ...]:
    """Agents whose generated files are ignored, read from ``.kittify/config.yaml``.

    An explicit list (empty included, #6494) is used as is. A config with no
    ``available`` list at all is a legacy project and keeps every agent, the
    same fallback as ``get_agent_dirs_for_project`` (#6501 owns that case).
    An unreadable config raises ``AgentConfigError``.
    """
    from specify_cli.core.agent_config import load_agent_config

    config = load_agent_config(project_path)
    if config.available or config.explicit_agent_list:
        return tuple(config.available)
    return tuple(AI_CHOICES)


def agent_ignore_entries(project_path: Path, agent_keys: Sequence[str]) -> list[str]:
    """Return the ``.gitignore`` patterns for *agent_keys* in *project_path*.

    Secrets and state folders come first, in a fixed order; the generated
    paths follow, sorted and without duplicates, so the same inputs always
    give the same block.
    """
    agents = [key for key in agent_keys if key in AI_CHOICES]
    generated: set[str] = {f"{_SHARED_SKILL_ROOT}{pattern}" for pattern in _RESERVED_SKILL_DIR_PATTERNS}
    for key in agents:
        generated.update(_agent_generated_entries(key))
    generated.update(_builtin_skill_dirs(agents))
    generated.update(_manifest_skill_dirs(project_path, agents))
    generated.update(_profile_files(project_path))
    fixed = [*SECRET_ENTRIES, *STATE_DIR_ENTRIES]
    return fixed + sorted(generated - set(fixed))


def _agent_generated_entries(agent_key: str) -> list[str]:
    entries: list[str] = []
    command = AGENT_COMMAND_CONFIG.get(agent_key)
    if command is not None:
        entries.append(f"{command['dir']}/{_COMMAND_FILE_PATTERN}")
    root = _primary_skill_root(agent_key)
    if root is not None:
        entries.extend(f"{root}{pattern}" for pattern in _RESERVED_SKILL_DIR_PATTERNS)
    session_file = _whole_session_file(agent_key)
    if session_file is not None:
        entries.append(session_file)
    return entries


def _primary_skill_root(agent_key: str) -> str | None:
    from specify_cli.skills.paths import get_primary_project_skill_root

    root = get_primary_project_skill_root(agent_key)
    if root is None:
        return None
    return root if root.endswith("/") else f"{root}/"


def _whole_session_file(agent_key: str) -> str | None:
    """The session file Spec Kitty writes whole for *agent_key*, if any.

    Append-mode files and files outside an agent folder (``AGENTS.md``,
    ``GEMINI.md``) are shared with the team and never ignored.
    """
    from specify_cli.session_presence.writers.markdown_rules import MarkdownRulesWriter
    from specify_cli.session_presence.writers.registry import WRITER_REGISTRY

    writer = WRITER_REGISTRY.get(agent_key)
    if not isinstance(writer, MarkdownRulesWriter) or writer.append_mode:
        return None
    if len(PurePosixPath(writer.rules_path).parts) < 2:  # noqa: PLR2004 - a root-level file
        return None
    return str(writer.rules_path)


def _builtin_skill_dirs(agents: Iterable[str]) -> set[str]:
    """Shipped built-in skills whose names the reserved patterns miss (``adversarial-squad``).

    Read from the shipped catalog rather than the per-machine skills manifest,
    so every clone on one CLI version writes the same committed block.
    """
    from specify_cli.skills.catalog import resolve_builtin_skill_catalog

    catalog = resolve_builtin_skill_catalog()
    if catalog is None:
        return set()
    names = [skill.name for skill in catalog.discover_skills() if not _is_reserved_skill_name(skill.name)]
    roots = {root for root in (_primary_skill_root(key) for key in agents) if root is not None}
    return {f"{root}{name}/" for root in roots for name in names}


def _is_reserved_skill_name(name: str) -> bool:
    return name == "spec-kitty" or name.startswith(("spec-kitty-", "spec-kitty.", "spk-"))


def _profile_files(project_path: Path) -> set[str]:
    """Agent profile files the profile manifest records as projected by Spec Kitty.

    An unreadable manifest contributes nothing; ``doctor`` reports it.
    """
    from specify_cli.tool_surface.profiles.manifest import ProfileManifest

    try:
        manifest = ProfileManifest.load(project_path)
    except (OSError, ValueError):
        return set()
    files: set[str] = set()
    for output_path in manifest.output_paths():
        with contextlib.suppress(ValueError):  # recorded outside the project: not ours to list
            files.add(output_path.relative_to(project_path).as_posix())
    return files


def _manifest_skill_dirs(project_path: Path, agents: Iterable[str]) -> set[str]:
    """Pack-skill folders the skills manifest records for *agents*.

    An unreadable manifest contributes nothing: the reserved patterns still
    cover Spec Kitty's own skills, and a pack skill left visible is a file
    to review, not a leaked secret.
    """
    from specify_cli.skills.manifest import ORIGIN_PACK, load_manifest

    manifest = load_manifest(project_path)  # None when absent or unreadable
    if manifest is None:
        return set()
    wanted = set(agents)
    dirs: set[str] = set()
    for entry in manifest.entries:
        if entry.agent_key not in wanted or entry.origin != ORIGIN_PACK:
            continue
        skill_dir = _skill_dir_of(entry.installed_path, entry.agent_key)
        if skill_dir is not None:
            dirs.add(skill_dir)
    return dirs


def _skill_dir_of(installed_path: str, agent_key: str) -> str | None:
    """``<root><skill>/`` for a file installed under one of the agent's skill roots."""
    config = AGENT_SKILL_CONFIG.get(agent_key)
    roots = config.get("skill_roots") if config else None
    if not isinstance(roots, list):
        return None
    path = PurePosixPath(installed_path)
    for root in roots:
        root_path = PurePosixPath(root)
        if path.is_relative_to(root_path) and len(path.parts) > len(root_path.parts) + 1:
            return f"{root_path.as_posix()}/{path.parts[len(root_path.parts)]}/"
    return None
