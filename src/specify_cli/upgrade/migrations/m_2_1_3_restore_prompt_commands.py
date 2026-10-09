"""Migration 2.1.3: Replace thin shims for prompt-driven commands with full prompts.

Consumer projects that were initialized or upgraded while feature 057 (hybrid
prompt-and-shim) was in a transitional state may have thin 3-line shim files for
all 16 commands, including the 9 prompt-driven commands (specify, plan, tasks, …).

This migration detects those thin shims and replaces them with full prompt template
files sourced from the global runtime (~/.kittify/missions/software-dev/).

Detection heuristic
-------------------
A command file is considered a "thin shim" if it satisfies **both** conditions:

    1.  The file has fewer than 10 non-empty lines.
    2.  The file contains the string ``"spec-kitty agent shim"``.

Any file that does not match both conditions is left untouched — it may be a
project-level override or already a full prompt.

Idempotency
-----------
After the first run the affected files are full prompts (many more than 10 lines).
On a second run ``_is_thin_shim()`` returns ``False`` for every file, so nothing is
changed and the ``changes_made`` list will contain a "nothing to do" sentinel message.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from specify_cli.runtime.generated_writer import write_generated_file

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult
from .m_0_9_1_complete_lane_migration import get_agent_dirs_for_project

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SHIM_MARKER = "spec-kitty agent shim"
SHIM_LINE_THRESHOLD = 10
_DEFAULT_SCRIPT_TYPE = "sh"
_MISSION_NAME = "software-dev"


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _is_thin_shim(file_path: Path) -> bool:
    """Return ``True`` if *file_path* looks like a thin shim generated for a prompt-driven command.

    A file is a thin shim when **both** hold:

    - Non-empty line count is below :data:`SHIM_LINE_THRESHOLD`, AND
    - The file body contains :data:`SHIM_MARKER`.

    Args:
        file_path: Path to the command file to inspect.

    Returns:
        ``True`` when the file matches the thin-shim heuristic; ``False`` otherwise.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError:
        return False
    non_empty_lines = [line for line in content.splitlines() if line.strip()]
    return len(non_empty_lines) < SHIM_LINE_THRESHOLD and SHIM_MARKER in content


def _get_runtime_command_templates_dir() -> Path | None:
    """Return the runtime command prompt source directory, or ``None`` if not found.

    Resolution order:

    1. ``SPEC_KITTY_HOME`` environment variable override (for tests and CI).
    2. Package-bundled doctrine mission steps.
    3. Legacy package-bundled missions (``get_package_asset_root()``).
    4. ``~/.kittify/missions/software-dev/command-templates/`` (installed runtime).
    """
    try:
        from charter.missions import (  # noqa: PLC0415
            MissionsRootNotFound,
            MissionTemplateRepository,
        )

        # Typed pin: ``charter.*`` is ``follow_imports = "skip"`` in pyproject, so the
        # facade re-export is ``Any`` to mypy; the runtime type is ``Path``.
        offering_steps: Path = (
            MissionTemplateRepository.default_missions_root()
            / "mission-steps"
            / _MISSION_NAME
        )
        if offering_steps.is_dir():
            return offering_steps
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
    """Return the platform-appropriate script type for rendering command templates.

    Uses Windows detection (same logic as ``init.py``) to pick ``"ps"`` or ``"sh"``.
    Migration-level rendering does not consult the project config because
    ``script_type`` is not persisted there; we fall back to the same auto-detection
    that ``spec-kitty init`` uses.
    """
    return "ps" if os.name == "nt" else _DEFAULT_SCRIPT_TYPE


def _resolve_template_path(templates_dir: Path, command: str) -> Path:
    """Support canonical mission-step prompts and legacy flat templates."""
    prompt_path = templates_dir / command / "prompt.md"
    if prompt_path.is_file():
        return prompt_path
    return templates_dir / f"{command}.md"


def _compute_output_filename(command: str, agent_key: str) -> str:
    """Return the correct on-disk filename for *command* + *agent_key*.

    Mirrors the filename logic in :func:`~specify_cli.template.asset_generator.generate_agent_assets`.

    Args:
        command: Command stem, e.g. ``"specify"``.
        agent_key: Agent key, e.g. ``"claude"`` or ``"gemini"``.

    Returns:
        Filename string such as ``"spec-kitty.specify.md"`` or ``"spec-kitty.specify.toml"``.
    """
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


def _render_full_prompt(
    template_path: Path,
    agent_key: str,
    script_type: str,
    *,
    repo_root: Path | None = None,
) -> str | None:
    """Render a single command template for *agent_key*.

    Args:
        template_path: Path to the source ``.md`` template file.
        agent_key:     Agent key, e.g. ``"claude"``.
        script_type:   Script type string, e.g. ``"sh"`` or ``"ps"``.
        repo_root:     Project repository root used to gate the SPDD/REASONS
                       conditional prompt fragment renderer.

    Returns:
        Rendered string, or ``None`` on any rendering error.
    """
    from specify_cli.core.config import AGENT_COMMAND_CONFIG
    from specify_cli.template.asset_generator import render_command_template

    config = AGENT_COMMAND_CONFIG.get(agent_key)
    if config is None:
        return None

    try:
        return render_command_template(
            template_path=template_path,
            script_type=script_type,
            agent_key=agent_key,
            arg_format=config["arg_format"],
            extension=config["ext"],
            repo_root=repo_root,
        )
    except Exception as exc:  # pragma: no cover — rendering failure is non-fatal
        logger.warning("Failed to render %s for agent %s: %s", template_path.name, agent_key, exc)
        return None


# ---------------------------------------------------------------------------
# Migration class
# ---------------------------------------------------------------------------


@MigrationRegistry.register
class RestorePromptCommandsMigration(BaseMigration):
    """Replace thin shims for prompt-driven commands with full prompts.

    Idempotent: files that are already full prompts (≥ 10 non-empty lines, or
    lacking the shim marker) are skipped on every subsequent run.
    """

    migration_id = "2.1.3_restore_prompt_commands"
    description = (
        "Replace thin shims for prompt-driven commands (specify, plan, tasks, …) "
        "with full prompt template files from the global runtime"
    )
    target_version = "2.1.3"

    def detect(self, project_path: Path) -> bool:
        """Return ``True`` if any prompt-driven command file is a thin shim."""
        from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS

        agent_dirs = get_agent_dirs_for_project(project_path)
        for agent_root, subdir in agent_dirs:
            agent_dir = project_path / agent_root / subdir
            if not agent_dir.is_dir():
                continue
            for command in PROMPT_DRIVEN_COMMANDS:
                # Check both the correct-extension filename and a legacy .md shim
                for candidate in _candidate_shim_paths(agent_dir, command, agent_root):
                    if candidate.exists() and _is_thin_shim(candidate):
                        return True
        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Check that runtime templates are available for rendering."""
        templates_dir = _get_runtime_command_templates_dir()
        if templates_dir is None:
            return (
                False,
                "Runtime command templates not found. "
                "Run 'spec-kitty upgrade' again after reinstalling spec-kitty-cli.",
            )
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Replace thin shims for prompt-driven commands with full prompts.

        Idempotent: files that are already full prompts (≥ 10 non-empty lines, or
        lacking the shim marker) are skipped on every subsequent run.

        Args:
            project_path: Root of the consumer project.
            dry_run:      When ``True``, report what *would* change but write nothing.

        Returns:
            :class:`~specify_cli.upgrade.migrations.base.MigrationResult` with
            ``changes_made`` listing each file that was (or would be) replaced.
        """
        from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS

        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        templates_dir = _get_runtime_command_templates_dir()
        if templates_dir is None:
            return MigrationResult(
                success=False,
                changes_made=changes,
                errors=["Runtime command templates not found — cannot restore full prompts"],
                warnings=warnings,
            )

        script_type = _resolve_script_type()
        agent_dirs = get_agent_dirs_for_project(project_path)

        for agent_root, subdir in agent_dirs:
            agent_dir = project_path / agent_root / subdir
            if not agent_dir.is_dir():
                continue

            agent_key = _agent_root_to_key(agent_root)
            if agent_key is None:
                logger.debug("Skipping unknown agent root %s", agent_root)
                continue

            for command in sorted(PROMPT_DRIVEN_COMMANDS):
                template_path = _resolve_template_path(templates_dir, command)
                if not template_path.is_file():
                    warnings.append(
                        f"Template not found for command '{command}' in {templates_dir} — skipping"
                    )
                    continue

                # Determine which existing file(s) might be a thin shim for this command.
                # The shim generator always writes .md; the full prompt may use a different ext.
                shim_candidates = _candidate_shim_paths(agent_dir, command, agent_root)
                thin_shim_file: Path | None = None
                for candidate in shim_candidates:
                    if candidate.exists() and _is_thin_shim(candidate):
                        thin_shim_file = candidate
                        break

                if thin_shim_file is None:
                    # No thin shim — already a full prompt or not present; skip
                    continue

                # Compute the correct output filename for this agent
                output_filename = _compute_output_filename(command, agent_key)
                output_path = agent_dir / output_filename

                rel_shim = str(thin_shim_file.relative_to(project_path))
                rel_output = str(output_path.relative_to(project_path))

                if dry_run:
                    changes.append(f"Would restore: {rel_shim} → {rel_output}")
                    continue

                # Render the full prompt
                rendered = _render_full_prompt(
                    template_path, agent_key, script_type, repo_root=project_path
                )
                if rendered is None:
                    errors.append(f"Failed to render {command} for {agent_key}")
                    continue

                # Write the full prompt to the correctly-named output file
                try:
                    write_generated_file(output_path, rendered)
                except OSError as exc:
                    errors.append(f"Failed to write {rel_output}: {exc}")
                    continue

                # If the old shim had a different filename, remove it
                if thin_shim_file != output_path:
                    try:
                        thin_shim_file.unlink()
                        changes.append(f"Restored: {rel_shim} → {rel_output} (removed stale shim)")
                    except OSError as exc:
                        warnings.append(f"Could not remove stale shim {rel_shim}: {exc}")
                        changes.append(f"Restored: {rel_shim} → {rel_output}")
                else:
                    changes.append(f"Restored: {rel_output}")

        if not changes and not errors and not warnings:
            changes.append("No thin shims found for prompt-driven commands — nothing to do")

        return MigrationResult(
            success=len(errors) == 0,
            changes_made=changes,
            errors=errors,
            warnings=warnings,
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _agent_root_to_key(agent_root: str) -> str | None:
    """Map an agent directory root (e.g. ``.claude``) to its agent key (e.g. ``"claude"``).

    Args:
        agent_root: Agent directory name, e.g. ``".claude"``.

    Returns:
        Agent key string, or ``None`` if not recognised.
    """
    from specify_cli.agent_utils.directories import AGENT_DIR_TO_KEY

    return AGENT_DIR_TO_KEY.get(agent_root)


def _candidate_shim_paths(agent_dir: Path, command: str, agent_root: str) -> list[Path]:
    """Return candidate paths where a thin shim for *command* might reside.

    The shim generator (feature 057) always wrote ``.md`` files regardless of the
    agent's canonical extension.  The canonical full-prompt file may have a different
    extension (e.g. ``.toml`` for Gemini, ``.prompt.md`` for Copilot).

    We check:

    - The canonical output filename for this agent (may be ``.toml`` etc.).
    - A plain ``.md`` fallback (the shim generator's legacy output).

    Args:
        agent_dir:  Full path to the agent command directory.
        command:    Command stem, e.g. ``"specify"``.
        agent_root: Agent directory root, e.g. ``".claude"``.

    Returns:
        List of :class:`~pathlib.Path` candidates (may contain duplicates if the
        canonical name is already ``.md``).
    """
    agent_key = _agent_root_to_key(agent_root)
    candidates: list[Path] = []
    if agent_key is not None:
        canonical = _compute_output_filename(command, agent_key)
        candidates.append(agent_dir / canonical)

    # Always also check the legacy .md shim path (from feature 057)
    legacy_md = agent_dir / f"spec-kitty.{command}.md"
    if not candidates or candidates[0] != legacy_md:
        candidates.append(legacy_md)

    return candidates
