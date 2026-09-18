"""Regenerate all agent command files (CLI commands + prompt-driven templates).

Writes all 16 consumer-facing command files for every configured agent:

- **CLI-driven** commands (7): thin command files calling canonical
  ``spec-kitty`` commands directly (e.g. ``spec-kitty agent action implement``).
- **Prompt-driven** commands (9): full rendered prompt templates from
  the package-bundled mission command-templates.

After generation, any ``spec-kitty.*`` files that remain in agent command
directories but were **not** freshly written are deleted as stale.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from kernel.paths import is_windows

logger = logging.getLogger(__name__)

_MISSION_NAME = "software-dev"
_DEFAULT_SCRIPT_TYPE = "sh"


@dataclass
class RewriteResult:
    """Summary of a :func:`rewrite_agent_commands` run.

    Attributes:
        agents_processed: Number of agent directories touched.
        files_written: Paths of command files that were written (created or
            overwritten).
        files_deleted: Paths of stale command files that were removed.
        warnings: List of non-fatal warning messages.
    """

    agents_processed: int = 0
    files_written: list[Path] = field(default_factory=list)
    files_deleted: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _get_command_templates_dir() -> Path | None:
    """Return the bundled command prompt source directory, or ``None``."""
    try:
        from charter.missions import (  # noqa: PLC0415
            MissionsRootNotFound,
            MissionTemplateRepository,
        )

        # Typed pin: ``charter.*`` is ``follow_imports = "skip"`` in pyproject, so the
        # facade re-export is ``Any`` to mypy; the runtime type is ``Path``.
        doctrine_steps: Path = MissionTemplateRepository.default_missions_root() / "mission-steps" / _MISSION_NAME
        if doctrine_steps.is_dir():
            return doctrine_steps
    except (ImportError, MissionsRootNotFound):
        pass

    from specify_cli.runtime.home import get_kittify_home, get_package_asset_root

    # Legacy package-bundled assets.
    try:
        pkg_root = get_package_asset_root()
        pkg_templates = pkg_root / _MISSION_NAME / "command-templates"
        if pkg_templates.is_dir():
            return pkg_templates
    except FileNotFoundError:
        pass

    # Global runtime (~/.kittify/) — populated by historical ensure_runtime().
    runtime_templates = get_kittify_home() / "missions" / _MISSION_NAME / "command-templates"
    if runtime_templates.is_dir():
        return runtime_templates

    return None


def _resolve_script_type() -> str:
    """Return the platform-appropriate script type."""
    return "ps" if is_windows() else _DEFAULT_SCRIPT_TYPE


def _compute_output_filename(command: str, agent_key: str) -> str:
    """Return the correct on-disk filename for *command* + *agent_key*."""
    from specify_cli.core.config import AGENT_COMMAND_CONFIG

    config = AGENT_COMMAND_CONFIG.get(agent_key)
    if config is None:
        return f"spec-kitty.{command}.md"

    ext: str = config["ext"]
    stem = command
    if agent_key == "codex":
        stem = stem.replace("-", "_")
    if ext:
        return f"spec-kitty.{stem}.{ext}"
    return f"spec-kitty.{stem}"


def _generate_prompt_templates(repo_root: Path) -> list[Path]:
    """Render prompt-driven command templates for all configured agents.

    Returns:
        Sorted list of paths written, or empty list on failure.
    """
    from specify_cli.agent_utils.directories import (
        AGENT_DIR_TO_KEY,
        get_agent_dirs_for_project,
    )
    from specify_cli.core.config import AGENT_COMMAND_CONFIG
    from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS
    from specify_cli.template.asset_generator import render_command_template

    templates_dir = _get_command_templates_dir()
    if templates_dir is None:
        logger.warning("Command templates directory not found — skipping prompt-driven templates")
        return []

    script_type = _resolve_script_type()
    agent_dirs = get_agent_dirs_for_project(repo_root)
    written: list[Path] = []

    for agent_root, command_subdir in agent_dirs:
        agent_key = AGENT_DIR_TO_KEY.get(agent_root)
        if agent_key is None:
            continue

        config = AGENT_COMMAND_CONFIG.get(agent_key)
        if config is None:
            continue

        agent_cmd_dir = repo_root / agent_root / command_subdir
        agent_cmd_dir.mkdir(parents=True, exist_ok=True)

        for command in sorted(PROMPT_DRIVEN_COMMANDS):
            template_path = templates_dir / command / "prompt.md"
            if not template_path.is_file():
                template_path = templates_dir / f"{command}.md"
            if not template_path.is_file():
                logger.warning("Template not found: %s — skipping", template_path)
                continue

            try:
                rendered = render_command_template(
                    template_path=template_path,
                    script_type=script_type,
                    agent_key=agent_key,
                    arg_format=config["arg_format"],
                    extension=config["ext"],
                    repo_root=repo_root,
                )
            except Exception as exc:
                logger.warning("Failed to render %s for %s: %s", command, agent_key, exc)
                continue

            filename = _compute_output_filename(command, agent_key)
            out_path = agent_cmd_dir / filename
            out_path.write_text(rendered, encoding="utf-8")
            written.append(out_path)

    return sorted(written)


def rewrite_agent_shims(repo_root: Path) -> RewriteResult:
    """Regenerate all agent command files: CLI shims + prompt-driven templates.

    Writes all 16 consumer-facing command files for every configured agent,
    then deletes any ``spec-kitty.*`` files that are not in the freshly
    generated set (stale files from previous versions).

    Only processes agent directories configured in ``.kittify/config.yaml``
    (via :func:`~specify_cli.agent_utils.directories.get_agent_dirs_for_project`).

    Args:
        repo_root: Absolute path to the project root.

    Returns:
        :class:`RewriteResult` with counts of agents processed, files written,
        and files deleted.
    """
    from specify_cli.shims.generator import generate_all_shims
    from specify_cli.agent_utils.directories import get_agent_dirs_for_project

    result = RewriteResult()

    # Step 1: Generate CLI-driven thin shims (7 commands)
    try:
        shim_written = generate_all_shims(repo_root)
        result.files_written.extend(shim_written)
    except Exception as exc:
        msg = f"generate_all_shims failed: {exc}"
        logger.error(msg)
        result.warnings.append(msg)
        return result

    # Step 2: Generate prompt-driven full templates (9 commands)
    try:
        prompt_written = _generate_prompt_templates(repo_root)
        result.files_written.extend(prompt_written)
    except Exception as exc:
        msg = f"_generate_prompt_templates failed: {exc}"
        logger.warning(msg)
        result.warnings.append(msg)
        # Continue — CLI shims are still valid, prompt templates are non-fatal

    written_set: set[Path] = set(result.files_written)

    # Step 3: Build the set of prompt files that SHOULD exist for each agent.
    # Any expected file that wasn't successfully written is preserved during
    # stale-file cleanup — this prevents partial generation failures or
    # unavailable templates from destroying working prompt files.
    from specify_cli.agent_utils.directories import AGENT_DIR_TO_KEY
    from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS

    expected_prompt_files: set[Path] = set()
    agent_dirs = get_agent_dirs_for_project(repo_root)

    for agent_root, command_subdir in agent_dirs:
        agent_key = AGENT_DIR_TO_KEY.get(agent_root)
        if agent_key is None:
            continue
        agent_cmd_dir = repo_root / agent_root / command_subdir
        for command in PROMPT_DRIVEN_COMMANDS:
            filename = _compute_output_filename(command, agent_key)
            expected_prompt_files.add(agent_cmd_dir / filename)

    # Step 4: Delete stale files not in the generated or expected-prompt sets
    seen_dirs: set[Path] = set()

    for agent_root, command_subdir in agent_dirs:
        agent_cmd_dir = repo_root / agent_root / command_subdir
        if not agent_cmd_dir.is_dir():
            continue

        if agent_cmd_dir in seen_dirs:
            continue
        seen_dirs.add(agent_cmd_dir)
        result.agents_processed += 1

        for stale_file in sorted(agent_cmd_dir.glob("spec-kitty.*")):
            if stale_file in written_set:
                continue

            # Preserve prompt files that weren't regenerated — they may
            # still be working templates from a prior successful run.
            if stale_file in expected_prompt_files:
                logger.info("Preserving %s (not regenerated this run)", stale_file)
                continue

            try:
                stale_file.unlink()
                result.files_deleted.append(stale_file)
                logger.info("Deleted stale command file: %s", stale_file)
            except Exception as exc:
                msg = f"Failed to delete stale file {stale_file}: {exc}"
                logger.warning(msg)
                result.warnings.append(msg)

    logger.info(
        "rewrite_agent_shims: %d agents, %d written, %d deleted",
        result.agents_processed,
        len(result.files_written),
        len(result.files_deleted),
    )
    return result
