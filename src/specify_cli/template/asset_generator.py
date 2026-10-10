"""Agent-specific asset rendering helpers."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from collections.abc import Mapping

import yaml

from kernel.tree_removal import remove_tool_owned_tree

from specify_cli.core.config import AGENT_COMMAND_CONFIG
from specify_cli.agent_upgrade_prompt import prepend_agent_upgrade_check
from specify_cli.template.renderer import parse_frontmatter, render_template_text, rewrite_paths


def _get_cli_version() -> str:
    """Return the current CLI version string."""
    try:
        from importlib.metadata import version

        return str(version("spec-kitty-cli"))
    except Exception:
        from specify_cli import __version__

        return str(__version__)


def _toml_basic_string(value: str) -> str:
    """Return a TOML basic-string literal for a single-line value."""
    return json.dumps(value, ensure_ascii=False)


def prepare_command_templates(
    base_templates_dir: Path,
    mission_templates_dir: Path | None,
) -> Path:
    """Prepare command templates with mission overrides applied.

    Returns a directory containing base templates, with any mission templates
    overlaid to enhance/override the central command set.
    """
    if not mission_templates_dir or not mission_templates_dir.exists():
        return base_templates_dir

    merged_dir = base_templates_dir.parent / f".merged-{mission_templates_dir.parent.name}"
    if merged_dir.exists():
        remove_tool_owned_tree(merged_dir, owned_root=merged_dir, reason="merged command-template dir")

    shutil.copytree(base_templates_dir, merged_dir)
    for template_path in mission_templates_dir.glob("*.md"):
        destination = merged_dir / template_path.name
        base_template = base_templates_dir / template_path.name
        if not base_template.exists():
            shutil.copy2(template_path, destination)
            continue

        mission_text = template_path.read_text(encoding="utf-8-sig")
        base_text = base_template.read_text(encoding="utf-8-sig")
        mission_meta, mission_body, _ = parse_frontmatter(mission_text)
        base_meta, _, _ = parse_frontmatter(base_text)

        if not isinstance(mission_meta, dict):
            mission_meta = {}
        if not isinstance(base_meta, dict):
            base_meta = {}

        merged_meta = dict(mission_meta)
        if "scripts" not in merged_meta and isinstance(base_meta.get("scripts"), dict):
            merged_meta["scripts"] = base_meta["scripts"]
        if "agent_scripts" not in merged_meta and isinstance(base_meta.get("agent_scripts"), dict):
            merged_meta["agent_scripts"] = base_meta["agent_scripts"]

        if merged_meta:
            meta_text = yaml.safe_dump(merged_meta, sort_keys=False).strip()
            destination.write_text(f"---\n{meta_text}\n---\n\n{mission_body}", encoding="utf-8")
        else:
            destination.write_text(mission_body, encoding="utf-8")

    return merged_dir


def generate_agent_assets(command_templates_dir: Path, project_path: Path, agent_key: str, script_type: str) -> None:
    """Render every command template for the selected agent."""
    config = AGENT_COMMAND_CONFIG[agent_key]
    output_dir = project_path / config["dir"]
    if output_dir.exists():
        remove_tool_owned_tree(output_dir, owned_root=output_dir, reason="generated agent command dir")
    output_dir.mkdir(parents=True, exist_ok=True)

    if not command_templates_dir.exists():
        _raise_template_discovery_error(command_templates_dir)

    for template_path in sorted(command_templates_dir.glob("*.md")):
        rendered = render_command_template(
            template_path,
            script_type,
            agent_key,
            config["arg_format"],
            config["ext"],
            repo_root=project_path,
        )
        ext = config["ext"]
        stem = template_path.stem
        filename = f"spec-kitty.{stem}.{ext}" if ext else f"spec-kitty.{stem}"
        (output_dir / filename).write_text(rendered, encoding="utf-8")

    if agent_key == "copilot":
        vscode_settings = command_templates_dir.parent / "vscode-settings.json"
        if vscode_settings.exists():
            vscode_dest = project_path / ".vscode"
            vscode_dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(vscode_settings, vscode_dest / "settings.json")


def render_command_template(
    template_path: Path,
    script_type: str,
    agent_key: str,
    arg_format: str,
    extension: str,
    *,
    repo_root: Path | None = None,
    version: str | None = None,
) -> str:
    """Render a single command template for an agent.

    The ``repo_root`` argument, when supplied, gates the SPDD/REASONS
    conditional prompt fragment renderer (``apply_spdd_blocks_for_project``).
    When omitted, callers are treated as inactive (block content stripped),
    which preserves byte-for-byte parity with pre-WP04 output for any caller
    that has not been updated to pass ``repo_root``.

    ``version`` pins the ``spec-kitty-command-version`` marker to an explicit
    string instead of the live CLI version (mission #3447, FR-005). It lets the
    fixture-parity test and ``spec-kitty regen`` render byte-identical committed
    baselines from the shared pin without monkeypatching ``_get_cli_version``.
    When ``None`` the live CLI version is used, preserving existing behaviour.
    """
    from charter.spdd_reasons import apply_spdd_blocks_for_project  # noqa: PLC0415

    template_text = template_path.read_text(encoding="utf-8-sig").replace("\r", "")
    template_text = apply_spdd_blocks_for_project(template_text, repo_root)
    requires_script = "{SCRIPT}" in template_text

    def build_variables(metadata: dict[str, object]) -> Mapping[str, str]:
        scripts = metadata.get("scripts") or {}
        agent_scripts = metadata.get("agent_scripts") or {}
        if not isinstance(scripts, dict):
            scripts = {}
        if not isinstance(agent_scripts, dict):
            agent_scripts = {}
        script_command = scripts.get(script_type)
        if requires_script and not script_command:
            raise ValueError(f"Template {template_path} requires scripts.{script_type} but none was provided.")
        agent_script_command = agent_scripts.get(script_type)
        return {
            "{SCRIPT}": script_command or "",
            "{AGENT_SCRIPT}": agent_script_command or "",
            "{ARGS}": arg_format,
            "__AGENT__": agent_key,
        }

    metadata, rendered_body, raw_frontmatter = render_template_text(
        template_text,
        variables=build_variables,
        template_path=template_path,
    )
    description = str(metadata.get("description", "")).strip()

    frontmatter_clean = _filter_frontmatter(raw_frontmatter)
    if frontmatter_clean:
        frontmatter_clean = rewrite_paths(frontmatter_clean)

    version_marker = f"<!-- spec-kitty-command-version: {version or _get_cli_version()} -->\n"

    if agent_key in AGENT_COMMAND_CONFIG:
        rendered_body = prepend_agent_upgrade_check(rendered_body)

    if extension == "toml":
        # Convert Markdown variable syntax to TOML/Gemini variable syntax
        # Gemini CLI uses {{args}} instead of $ARGUMENTS
        # See: https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/custom-commands.md
        rendered_body = _convert_markdown_syntax_to_format(rendered_body, "toml")

        description_value = description
        if description_value.startswith('"') and description_value.endswith('"'):
            description_value = description_value[1:-1]
        description_literal = _toml_basic_string(description_value)
        body_text = rendered_body
        if not body_text.endswith("\n"):
            body_text += "\n"
        body_text = body_text.replace("\\", "\\\\").replace('"""', '""\\"')
        # For TOML files, embed the version marker as a comment in the prompt body
        return f"description = {description_literal}\n\nprompt = \"\"\"\n{version_marker}{body_text}\"\"\"\n"

    # Markdown output: preserve the template's YAML frontmatter on line 1 so
    # agents (e.g. Claude Code) can read the `description` field for their
    # slash-command picker UI.  The HTML version marker goes *after* the
    # frontmatter block — placing it before would push the `---` off line 1
    # and break YAML frontmatter parsing.  Migrations and doctor scans look
    # for the marker within the file head, not only on line 1.
    result = f"---\n{frontmatter_clean}\n---\n{version_marker}\n{rendered_body}" if frontmatter_clean else f"{version_marker}\n{rendered_body}"
    if not result.endswith("\n"):
        result += "\n"
    return result


def _convert_markdown_syntax_to_format(content: str, target_format: str) -> str:
    """Convert Markdown variable syntax to target format syntax.

    Args:
        content: Rendered template content in Markdown syntax
        target_format: Target format (e.g., "toml" for Gemini)

    Returns:
        Content with variable syntax converted to target format

    Conversion rules:
    - Markdown (Claude/Codex): $ARGUMENTS, $AGENT_SCRIPT
    - TOML (Gemini): {{args}} (per https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/custom-commands.md)
    """
    if target_format == "toml":
        # Convert Claude/Codex Markdown variable syntax to Gemini TOML syntax
        # $ARGUMENTS → {{args}}
        content = content.replace("$ARGUMENTS", "{{args}}")
        return content

    # For other formats, return unchanged
    return content


def _filter_frontmatter(frontmatter_text: str) -> str:
    filtered_lines: list[str] = []
    skipping_block = False
    for line in frontmatter_text.splitlines():
        stripped = line.strip()
        if skipping_block:
            if line.startswith((" ", "\t")):
                continue
            skipping_block = False
        if stripped in {"scripts:", "agent_scripts:"}:
            skipping_block = True
            continue
        filtered_lines.append(line)
    return "\n".join(filtered_lines)


def _raise_template_discovery_error(commands_dir: Path) -> None:  # noqa: ARG001
    """Raise an informative error about template discovery failure."""
    env_root = os.environ.get("SPEC_KITTY_TEMPLATE_ROOT")
    remote_repo = os.environ.get("SPECIFY_TEMPLATE_REPO")

    error_msg = (
        "Templates could not be found in any of the expected locations:\n\n"
        "Checked paths (in order):\n"
        "  ✗ Packaged resources (bundled with CLI)\n"
        "  ✗ Environment variable SPEC_KITTY_TEMPLATE_ROOT"
        + (f" = {env_root}" if env_root else " (not set)")
        + "\n"
        + "  ✗ Remote repository SPECIFY_TEMPLATE_REPO"
        + (f" = {remote_repo}" if remote_repo else " (not configured)")
        + "\n\n"
        "To fix this, try one of these approaches:\n\n"
        "1. Reinstall from PyPI with pipx (recommended for end users):\n"
        "   pipx install --force spec-kitty-cli\n\n"
        "2. Use --template-root flag (for development):\n"
        "   spec-kitty init . --template-root=/path/to/spec-kitty\n\n"
        "3. Set environment variable (for development):\n"
        "   export SPEC_KITTY_TEMPLATE_ROOT=/path/to/spec-kitty\n"
        "   spec-kitty init .\n\n"
        "4. Configure remote repository:\n"
        "   export SPECIFY_TEMPLATE_REPO=owner/repo\n"
        "   spec-kitty init .\n\n"
        "For development installs from source, use:\n"
        "   export SPEC_KITTY_TEMPLATE_ROOT=$(git rev-parse --show-toplevel)\n"
        "   spec-kitty init . --ai=claude"
    )

    raise FileNotFoundError(error_msg)


__all__ = [
    "generate_agent_assets",
    "prepare_command_templates",
    "render_command_template",
    "_convert_markdown_syntax_to_format",
]
