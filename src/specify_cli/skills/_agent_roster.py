"""Single-source authority for the skill-only agent roster (#1941).

Historically the tuple of command-skill agents (``codex``, ``vibe``, ``pi``,
``letta``; ``antigravity`` since #6470) was duplicated as three byte-identical literals:

* ``skills/command_installer.py``  ``SUPPORTED_AGENTS``
* ``skills/command_renderer.py``   ``SUPPORTED_AGENTS``
* ``cli/commands/agent/config.py`` ``SKILL_ONLY_AGENTS``

That triplicate literal is a textbook **connascence of value** smell: the three
copies are equal *only by convention*, with nothing forcing them to stay in
sync. This module collapses them onto one authority.

It is a deliberately **dependency-free leaf**: it imports nothing from
``specify_cli.skills`` (or anywhere else in the package), so every other module
can import *from* it without risking an import cycle. In particular
``command_installer`` already imports ``command_renderer`` at module load, so
the authority must live below both of them — here.
"""

from __future__ import annotations

#: Canonical, ordered roster of shared-root command-skill agents.
#:
#: This is the *single* source of truth. ``command_installer.SUPPORTED_AGENTS``,
#: ``command_renderer.SUPPORTED_AGENTS`` and
#: ``cli.commands.agent.config.SKILL_ONLY_AGENTS`` are all derived from it; do
#: not reintroduce an independent literal anywhere else.
#:
#: ``antigravity`` joined in #6470: Google Antigravity stopped reading its legacy
#: ``.agent/workflows`` slash-command files on 2026-10-19 and reads command
#: skills from the shared ``.agents/skills/`` root, so it is a command-skill agent
#: and no longer has an ``AGENT_COMMAND_CONFIG`` row.
SUPPORTED_AGENTS: tuple[str, ...] = ("codex", "vibe", "pi", "letta", "antigravity")

__all__ = ["SUPPORTED_AGENTS"]
