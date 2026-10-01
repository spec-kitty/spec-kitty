"""Show resolution origin for all known assets.

Enumerates templates, command-templates, missions, scripts, and AGENTS.md
through the 4-tier resolution chain and reports where each asset resolves
from.

PRD §6.4 requires coverage of: templates, missions, commands, scripts,
and AGENTS.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from specify_cli.runtime.home import get_package_asset_root
from specify_cli.runtime.resolver import (
    resolve_command,
    resolve_mission,
    resolve_template,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardcoded fallback lists (used when dynamic discovery fails)
# ---------------------------------------------------------------------------

_FALLBACK_TEMPLATE_NAMES = [
    "spec-template.md",
    "plan-template.md",
    "tasks-template.md",
    "task-prompt-template.md",
]

_FALLBACK_COMMAND_NAMES = [
    "specify.md",
    "plan.md",
    "tasks.md",
    "implement.md",
    "review.md",
    "accept.md",
    "merge.md",
]


@dataclass
class OriginEntry:
    """A single resolved asset with its tier origin."""

    asset_type: str  # "template", "command", "mission", "script", "file"
    name: str  # "spec-template.md", "software-dev", etc.
    resolved_path: Path | None
    tier: str | None  # "override", "legacy", "global_mission", "global", "package_default"
    error: str | None  # If resolution failed


# ---------------------------------------------------------------------------
# Dynamic discovery helpers
# ---------------------------------------------------------------------------


def _discover_mission_names() -> list[str]:
    """Discover all mission directories from the package defaults."""
    try:
        pkg_root = get_package_asset_root()
        return sorted(d.name for d in pkg_root.iterdir() if d.is_dir() and (d / "mission.yaml").is_file())
    except OSError as exc:
        logger.debug("Cannot discover missions from package: %s", exc)
        # Single-source the built-in roster (#2669) instead of a hand-kept
        # partial list (the old literal was missing ``plan``).
        from charter.missions import builtin_mission_type_ids  # noqa: PLC0415

        return sorted(builtin_mission_type_ids())


def _discover_command_names(mission: str) -> list[str]:
    """Discover all command template filenames for a mission.

    Scans across all 4 tiers so that overrides and global additions are
    included alongside the package defaults.
    """
    names: set[str] = set()

    # Tier 4 -- package defaults (most reliable source)
    try:
        pkg_root = get_package_asset_root()
        pkg_cmd_dir = pkg_root / mission / "command-templates"
        if pkg_cmd_dir.is_dir():
            names.update(f.name for f in pkg_cmd_dir.iterdir() if f.is_file() and f.suffix == ".md")
        pkg_steps_dir = pkg_root / "mission-steps" / mission
        if pkg_steps_dir.is_dir():
            names.update(
                f"{step_dir.name}.md"
                for step_dir in pkg_steps_dir.iterdir()
                if step_dir.is_dir() and (step_dir / "prompt.md").is_file()
            )
    except OSError:
        pass

    if not names:
        names.update(_FALLBACK_COMMAND_NAMES)

    return sorted(names)


def _discover_template_names(mission: str) -> list[str]:
    """Discover all template filenames for a mission from package defaults."""
    names: set[str] = set()

    try:
        pkg_root = get_package_asset_root()
        pkg_tpl_dir = pkg_root / mission / "templates"
        if pkg_tpl_dir.is_dir():
            # Only top-level .md files (not subdirectory templates like divio/)
            names.update(f.name for f in pkg_tpl_dir.iterdir() if f.is_file() and f.suffix == ".md")
    except OSError:
        pass

    if not names:
        names.update(_FALLBACK_TEMPLATE_NAMES)

    return sorted(names)


def _discover_scripts(project_dir: Path) -> list[OriginEntry]:
    """Discover scripts from .kittify/scripts/ and package defaults.

    Scripts don't use the 4-tier resolver (they are project-local or
    package-bundled), so we report them with a simplified tier label.
    """
    entries: list[OriginEntry] = []

    # Project-local scripts
    project_scripts = project_dir / ".kittify" / "scripts"
    if project_scripts.is_dir():
        for script_file in sorted(project_scripts.rglob("*")):
            if script_file.is_file():
                rel = script_file.relative_to(project_scripts)
                entries.append(OriginEntry("script", str(rel), script_file, "project", None))

    # Package-bundled scripts (discover from src/specify_cli/scripts/)
    try:
        import specify_cli

        pkg_scripts = Path(specify_cli.__file__).parent / "scripts"
        if pkg_scripts.is_dir():
            for script_file in sorted(pkg_scripts.rglob("*")):
                if script_file.is_file():
                    rel = script_file.relative_to(pkg_scripts)
                    # Skip if already found at project level (project takes precedence)
                    if not any(e.name == str(rel) for e in entries):
                        entries.append(OriginEntry("script", str(rel), script_file, "package_default", None))
    except (ImportError, OSError):
        pass

    return entries


def _discover_agents_md(project_dir: Path) -> OriginEntry:
    """Discover AGENTS.md from project or package defaults.

    Checks project-local .kittify/AGENTS.md first, then the package
    default at specify_cli/templates/AGENTS.md.
    """
    # Project-local
    project_agents = project_dir / ".kittify" / "AGENTS.md"
    if project_agents.is_file():
        return OriginEntry("file", "AGENTS.md", project_agents, "project", None)

    # Package default
    try:
        import specify_cli

        pkg_agents = Path(specify_cli.__file__).parent / "templates" / "AGENTS.md"
        if pkg_agents.is_file():
            return OriginEntry("file", "AGENTS.md", pkg_agents, "package_default", None)
    except (ImportError, OSError):
        pass

    return OriginEntry("file", "AGENTS.md", None, None, "AGENTS.md not found at any location")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def collect_origins(
    project_dir: Path,
    mission: str = "software-dev",
) -> list[OriginEntry]:
    """Collect resolution origin for all known assets.

    Dynamically discovers templates, command-templates, missions, scripts,
    and AGENTS.md, resolving each through the 4-tier precedence chain
    where applicable.

    Covers PRD §6.4 requirements: templates, missions, commands, scripts,
    and AGENTS.md.

    Args:
        project_dir: Project root containing ``.kittify/``.
        mission: Mission key for template/command resolution.

    Returns:
        List of OriginEntry with resolution details for every known asset.
    """
    entries: list[OriginEntry] = []

    # Templates (dynamically discovered)
    template_names = _discover_template_names(mission)
    for name in template_names:
        try:
            result = resolve_template(name, project_dir, mission)
            entries.append(OriginEntry("template", name, result.path, result.tier.value, None))
        except FileNotFoundError as e:
            entries.append(OriginEntry("template", name, None, None, str(e)))

    # Command templates (dynamically discovered)
    command_names = _discover_command_names(mission)
    for name in command_names:
        try:
            result = resolve_command(name, project_dir, mission)
            entries.append(OriginEntry("command", name, result.path, result.tier.value, None))
        except FileNotFoundError as e:
            entries.append(OriginEntry("command", name, None, None, str(e)))

    # Missions (dynamically discovered)
    mission_names = _discover_mission_names()
    for name in mission_names:
        try:
            result = resolve_mission(name, project_dir)
            entries.append(OriginEntry("mission", name, result.path, result.tier.value, None))
        except FileNotFoundError as e:
            entries.append(OriginEntry("mission", name, None, None, str(e)))

    # Scripts
    entries.extend(_discover_scripts(project_dir))

    # AGENTS.md
    entries.append(_discover_agents_md(project_dir))

    return entries
