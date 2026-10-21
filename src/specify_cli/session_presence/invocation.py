"""Per-harness ``specify`` invocation shown in the orientation block (#6475, #6470).

Slash-command agents run ``/spec-kitty.specify``; command-skill agents run the
``spec-kitty-specify`` skill with their own sigil (``$`` in Codex, ``/skill:`` in
Pi, ``/`` elsewhere), as ``command_skill_names.skill_invocation_token`` says.

``AGENTS.md`` is shared by several writers (Codex, OpenCode, Antigravity, Pi,
Vibe, Letta). Its block names every form, grouped by token, and is the same
whichever writer renders it, so the writers never disagree about its bytes.
"""

from __future__ import annotations

from collections.abc import Iterable

__all__ = ["LEGACY_SPECIFY_INVOCATION", "invocation_for_writer"]

#: The only form the orientation block carried before #6475 (every harness).
LEGACY_SPECIFY_INVOCATION = "`/spec-kitty.specify`"
#: The one rules file several writers share.
SHARED_RULES_PATH = "AGENTS.md"
_SPECIFY = "specify"


def _token(agent_key: str) -> str:
    from specify_cli.skills._agent_roster import SUPPORTED_AGENTS
    from specify_cli.skills.command_skill_names import skill_invocation_token

    token: str = skill_invocation_token(agent_key, _SPECIFY, is_skill_agent=agent_key in SUPPORTED_AGENTS)
    return token


def shared_invocation(agent_keys: Iterable[str]) -> str:
    """Name each distinct token once, followed by the agents that use it."""
    groups: dict[str, list[str]] = {}
    for key in sorted(set(agent_keys)):
        groups.setdefault(_token(key), []).append(key)
    parts = [f"`{token}` ({', '.join(keys)})" for token, keys in sorted(groups.items())]
    if not parts:
        return LEGACY_SPECIFY_INVOCATION
    if len(parts) == 1:
        return parts[0]
    return f"{', '.join(parts[:-1])} or {parts[-1]}"


def _shared_rules_agents() -> list[str]:
    from .writers.registry import WRITER_REGISTRY

    return [key for key, writer in WRITER_REGISTRY.items() if getattr(writer, "rules_path", None) == SHARED_RULES_PATH]


def invocation_for_writer(harness_key: str, rules_path: str) -> str:
    """The invocation text a writer renders: shared for ``AGENTS.md``, its own token otherwise."""
    if rules_path == SHARED_RULES_PATH:
        return shared_invocation(_shared_rules_agents())
    return f"`{_token(harness_key)}`"
