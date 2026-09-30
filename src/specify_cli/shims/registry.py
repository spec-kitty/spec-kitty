"""Skill allowlist — consumer-facing vs internal-only skills.

Only skills in ``CONSUMER_SKILLS`` are written to agent shim directories
during ``generate_all_shims()``.  Skills in ``INTERNAL_SKILLS`` are
reserved for operator/developer use and must never appear in generated
command directories.

Consumer skills are further sub-classified as either *prompt-driven* or
*CLI-driven*:

- **Prompt-driven** commands (``PROMPT_DRIVEN_COMMANDS``) are handled
  entirely by their full prompt template files.  No thin shim files are
  generated for them.
- **CLI-driven** commands (``CLI_DRIVEN_COMMANDS``) are dispatched through
  canonical ``spec-kitty`` CLI commands and receive thin command files.

The two sets are disjoint and their union equals ``CONSUMER_SKILLS``.
"""

from __future__ import annotations

# Skills that project teams interact with directly via their AI agent's
# slash-command interface.
CONSUMER_SKILLS: frozenset[str] = frozenset(
    {
        "specify",
        "plan",
        "tasks",
        "tasks-outline",
        "tasks-packages",
        "tasks-finalize",
        "implement",
        "review",
        "accept",
        "consolidate",
        "status",
        "dashboard",
        "analyze",
        "research",
        "charter",
    }
)

# Skills reserved for spec-kitty operators and developers.
# These are NEVER written to consumer agent directories.
INTERNAL_SKILLS: frozenset[str] = frozenset(
    {
        "doctor",
        "materialize",
        "debug",
    }
)

# Consumer skills whose workflow is driven entirely by a full prompt
# template file.  No thin shim files are generated for these commands;
# the agent invokes their prompt directly.
PROMPT_DRIVEN_COMMANDS: frozenset[str] = frozenset(
    {
        "specify",
        "plan",
        "tasks",
        "tasks-outline",
        "tasks-packages",
        "analyze",
        "research",
        "charter",
    }
)

# Consumer skills whose workflow is driven by the spec-kitty CLI via a
# thin shim file.  Exactly one shim file is generated per agent for each
# of these commands.
CLI_DRIVEN_COMMANDS: frozenset[str] = frozenset(
    {
        "implement",
        "review",
        "accept",
        "consolidate",
        "status",
        "dashboard",
        "tasks-finalize",
    }
)

# Invariant: the two classification sets must cover all consumer skills
# exactly (no gaps, no overlaps).
assert PROMPT_DRIVEN_COMMANDS | CLI_DRIVEN_COMMANDS == CONSUMER_SKILLS, (
    "Command classification sets must cover all consumer skills exactly"
)
assert frozenset() == PROMPT_DRIVEN_COMMANDS & CLI_DRIVEN_COMMANDS, (
    "PROMPT_DRIVEN_COMMANDS and CLI_DRIVEN_COMMANDS must be disjoint"
)


def is_prompt_driven(skill_name: str) -> bool:
    """Return True if *skill_name* is handled by a full prompt template.

    Prompt-driven commands do not receive thin shim files.  Their
    complete workflow logic is embedded in the prompt template itself.

    Args:
        skill_name: Skill identifier (e.g. ``"specify"``).

    Returns:
        True when the skill appears in :data:`PROMPT_DRIVEN_COMMANDS`.
    """
    return skill_name in PROMPT_DRIVEN_COMMANDS


def is_cli_driven(skill_name: str) -> bool:
    """Return True if *skill_name* is dispatched through the CLI shim path.

    CLI-driven commands receive thin 3-line shim files and are dispatched
    via direct canonical ``spec-kitty`` CLI commands.

    Args:
        skill_name: Skill identifier (e.g. ``"implement"``).

    Returns:
        True when the skill appears in :data:`CLI_DRIVEN_COMMANDS`.
    """
    return skill_name in CLI_DRIVEN_COMMANDS


def get_all_skills() -> frozenset[str]:
    """Return the union of consumer and internal skill names."""
    return CONSUMER_SKILLS | INTERNAL_SKILLS
