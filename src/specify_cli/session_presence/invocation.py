"""The ``specify`` invocation the orientation block names (#6475, #6470).

Slash-command agents run ``/spec-kitty.specify``; command-skill agents run the
``spec-kitty-specify`` skill with their own sigil (``$`` in Codex, ``/skill:`` in
Pi, ``/`` elsewhere), as ``command_skill_names.skill_invocation_token`` says.

The block names every form, grouped by token. One text for every harness keeps
the block harness-independent: ``AGENTS.md`` is shared by six writers, and the
frozen orientation-refresh migration (``m_3_2_0rc39``) compares each installed
block with one ``SessionPresenceContent.render()``.
"""

from __future__ import annotations

__all__ = ["LEGACY_SPECIFY_INVOCATION", "orientation_invocation"]

#: The only form the orientation block carried before #6475 (every harness).
LEGACY_SPECIFY_INVOCATION = "`/spec-kitty.specify`"
_SPECIFY = "specify"
_SLASH_LABEL = "slash-command agents"


def orientation_invocation() -> str:
    """Every way to start a full Mission: the slash form, then each skill token with its agents."""
    from specify_cli.skills._agent_roster import SUPPORTED_AGENTS
    from specify_cli.skills.command_skill_names import skill_invocation_token

    groups: dict[str, list[str]] = {}
    for agent in sorted(SUPPORTED_AGENTS):
        token: str = skill_invocation_token(agent, _SPECIFY, is_skill_agent=True)
        groups.setdefault(token, []).append(agent)
    slash: str = skill_invocation_token("claude", _SPECIFY, is_skill_agent=False)
    parts = [f"`{slash}` ({_SLASH_LABEL})", *(f"`{token}` ({', '.join(agents)})" for token, agents in sorted(groups.items()))]
    return f"{', '.join(parts[:-1])} or {parts[-1]}"
