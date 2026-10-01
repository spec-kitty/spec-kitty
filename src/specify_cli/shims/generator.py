"""Generate thin command markdown files for all configured agents.

Each generated Markdown file contains exactly:
  1. A YAML frontmatter block declaring a human-readable ``description``
     (used by slash-command pickers such as Claude Code's UI).
  2. A version marker HTML comment (``<!-- spec-kitty-command-version: X.Y.Z -->``).
     The marker lives *inside* the file body, immediately after the closing
     ``---``; migrations and doctor checks scan the file head for it.
  3. An invariant instruction line.
  4. A prohibition line.
  5. A mission hint line.
  6. A direct canonical CLI call that passes all arguments through.

No workflow logic is embedded in command files.  Each file calls the
canonical ``spec-kitty`` CLI command directly -- there is no intermediate
shim dispatch layer.
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.agent_utils.directories import (
    AGENT_DIR_TO_KEY,
    get_agent_dirs_for_project,
)
from specify_cli.shims.registry import CLI_DRIVEN_COMMANDS

# Human-readable one-line descriptions shown by agent slash-command pickers
# (e.g. Claude Code's UI populates its description column from frontmatter).
# Keys must match entries in :data:`CLI_DRIVEN_COMMANDS`.
SHIM_DESCRIPTIONS: dict[str, str] = {
    "implement": "Execute a work package implementation",
    "review": "Review a work package implementation",
    "accept": "Validate an approved mission before merge",
    "consolidate": "Consolidate an accepted mission",
    "status": "Show mission and work package status",
    "tasks-finalize": "Finalize a mission's work packages",
}


def _get_cli_version() -> str:
    """Return the current CLI version string."""
    try:
        from importlib.metadata import version

        return version("spec-kitty-cli")
    except Exception:
        from specify_cli import __version__

        return __version__

# Agent-specific argument placeholders.
# Claude Code passes slash-command arguments as $ARGUMENTS.
# Codex passes the prompt text as $PROMPT.
# All other agents default to $ARGUMENTS.
AGENT_ARG_PLACEHOLDERS: dict[str, str] = {
    "claude": "$ARGUMENTS",
    "codex": "$PROMPT",
}

_DEFAULT_ARG_PLACEHOLDER = "$ARGUMENTS"


def _canonical_command(command: str, agent_name: str, arg_placeholder: str) -> str:
    """Map a CLI-driven command verb to its canonical ``spec-kitty`` invocation.

    Args:
        command:         Skill verb, e.g. ``"implement"``.
        agent_name:      Agent key, e.g. ``"claude"``.
        arg_placeholder: Runtime variable name, e.g. ``"$ARGUMENTS"``.

    Returns:
        A single-line canonical CLI command string.
    """
    _COMMAND_MAP: dict[str, str] = {
        "implement": "spec-kitty agent action implement {args} --agent {agent}",
        "review": "spec-kitty agent action review {args} --agent {agent}",
        "accept": "spec-kitty agent mission accept {args}",
        "status": "spec-kitty agent tasks status {args}",
        "consolidate": "spec-kitty consolidate {args}",
        "tasks-finalize": "spec-kitty agent mission finalize-tasks {args}",
    }
    template = _COMMAND_MAP.get(command)
    if template is None:
        raise ValueError(
            f"Unknown CLI-driven command '{command}'. "
            f"Expected one of: {', '.join(sorted(_COMMAND_MAP))}."
        )
    return template.format(args=arg_placeholder, agent=agent_name)


def generate_shim_content(command: str, agent_name: str, arg_placeholder: str) -> str:
    """Return the command markdown body with frontmatter and version marker.

    Each generated file calls a canonical ``spec-kitty`` CLI command
    directly -- there is no intermediate shim dispatch layer.  The file
    opens with YAML frontmatter (``---`` on line 1) that carries a
    ``description`` key; slash-command pickers such as Claude Code read
    this to populate their UI.  Immediately after the closing ``---``,
    a ``<!-- spec-kitty-command-version: X.Y.Z -->`` comment lets
    migrations and doctor checks detect spec-kitty-authored files.

    Args:
        command:         Skill verb, e.g. ``"implement"``.
        agent_name:      Agent key, e.g. ``"claude"``.
        arg_placeholder: Runtime variable name, e.g. ``"$ARGUMENTS"``.

    Returns:
        A multi-line string ready to write as a ``.md`` file.
    """
    version = _get_cli_version()
    cli_call = _canonical_command(command, agent_name, arg_placeholder)
    description = SHIM_DESCRIPTIONS.get(command, f"spec-kitty {command}")
    body = (
        "Run this exact command and treat its output as authoritative.\n"
        "Do not rediscover context from branches, files, prompt contents, or separate charter loads.\n"
        "When mission selection is required, pass --mission <handle> (mission_id, mid8, or mission_slug).\n"
        "\n"
        f"`{cli_call}`\n"
    )
    return (
        "---\n"
        f"description: {description}\n"
        "---\n"
        f"<!-- spec-kitty-command-version: {version} -->\n"
        f"{body}"
    )


def generate_shim_content_toml(
    command: str, agent_name: str, arg_placeholder: str
) -> str:
    """Return a TOML shim for agents that require TOML format (Gemini, Qwen).

    Uses the flat ``description``/``prompt`` schema matching the regression
    baselines in ``tests/specify_cli/regression/_twelve_agent_baseline/``.

    Args:
        command:         Skill verb, e.g. ``"implement"``.
        agent_name:      Agent key, e.g. ``"gemini"``.
        arg_placeholder: Runtime variable name, e.g. ``"{{args}}"``.

    Returns:
        A multi-line string ready to write as a ``.toml`` file.
    """
    version = _get_cli_version()
    cli_call = _canonical_command(command, agent_name, arg_placeholder)
    description = SHIM_DESCRIPTIONS.get(command, f"spec-kitty {command}")
    body = (
        f"<!-- spec-kitty-command-version: {version} -->\n"
        "Run this exact command and treat its output as authoritative.\n"
        "Do not rediscover context from branches, files, prompt contents, or separate charter loads.\n"
        "When mission selection is required, pass --mission <handle> (mission_id, mid8, or mission_slug).\n"
        "\n"
        f"`{cli_call}`\n"
    )
    body_escaped = body.replace('"""', '""\\"')
    return (
        f'description = "{description}"\n'
        "\n"
        f'prompt = """\n{body_escaped}"""\n'
    )


def generate_shim_content_for_agent(command: str, agent_key: str) -> str:
    """Return shim content for *command* targeting *agent_key*.

    Reads ``AGENT_COMMAND_CONFIG`` for the format (ext) and arg placeholder,
    then dispatches to :func:`generate_shim_content` (Markdown) or
    :func:`generate_shim_content_toml` (TOML).
    Falls back to Markdown / ``$ARGUMENTS`` for unknown agents.

    Args:
        command:   Skill verb, e.g. ``"implement"``.
        agent_key: Agent configuration key, e.g. ``"gemini"``.

    Returns:
        A multi-line string ready to write as the agent's native command file.
    """
    from specify_cli.core.config import AGENT_COMMAND_CONFIG

    config = AGENT_COMMAND_CONFIG.get(agent_key, {})
    arg_placeholder: str = config.get("arg_format", _DEFAULT_ARG_PLACEHOLDER)
    ext: str = config.get("ext", "md")

    if ext == "toml":
        return generate_shim_content_toml(command, agent_key, arg_placeholder)
    return generate_shim_content(command, agent_key, arg_placeholder)


def generate_all_shims(repo_root: Path) -> list[Path]:
    """Generate shim files for all configured agents and CLI-driven skills.

    Uses :func:`~specify_cli.agent_utils.directories.get_agent_dirs_for_project`
    to honour the project's agent configuration.  Only skills in
    :data:`~specify_cli.shims.registry.CLI_DRIVEN_COMMANDS` are written —
    prompt-driven commands are intentionally skipped because their full
    prompt template files handle the workflow directly.

    Existing shim files are overwritten; directories that do not exist are
    created.

    Args:
        repo_root: Absolute path to the project root.

    Returns:
        Sorted list of paths written.
    """
    cli_skills = sorted(CLI_DRIVEN_COMMANDS)
    agent_dirs = get_agent_dirs_for_project(repo_root)
    written: list[Path] = []

    for agent_root, command_subdir in agent_dirs:
        agent_key = AGENT_DIR_TO_KEY.get(agent_root, agent_root.lstrip("."))

        target_dir = repo_root / agent_root / command_subdir
        target_dir.mkdir(parents=True, exist_ok=True)

        for skill in cli_skills:
            from specify_cli.core.config import AGENT_COMMAND_CONFIG as _ACC
            _agent_cfg = _ACC.get(agent_key, {})
            _ext = _agent_cfg.get("ext", "md")
            filename = f"spec-kitty.{skill}.{_ext}"
            content = generate_shim_content_for_agent(skill, agent_key)
            out_path = target_dir / filename
            out_path.write_text(content, encoding="utf-8")
            written.append(out_path)

    return sorted(written)
