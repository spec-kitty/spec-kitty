"""Writer registry — maps harness keys to Writer instances.

Phase 1 / WP02: ``claude`` is wired to ``ClaudeCodeWriter()``.
Phase 2 / WP05: all remaining harness entries are populated.

Registry shape (see data-model.md):

+-----------+-----------------------+-------------------------------------------+
| Pattern   | Writer class          | Harness keys                              |
+-----------+-----------------------+-------------------------------------------+
| A         | ClaudeCodeWriter      | claude                                    |
| B         | MarkdownRulesWriter   | cursor, windsurf, copilot, kiro, gemini,  |
|           | (parameterised)       | llxprt (roo removed 2026-05-15, C-007)    |
| C         | AgentsMdWriter        | codex, opencode, antigravity              |
| D         | SkillsPreambleWriter  | pi, vibe, letta                           |
| E (stub)  | NullWriter            | qwen, kilocode, auggie, q                 |
+-----------+-----------------------+-------------------------------------------+
"""

from __future__ import annotations

from .agents_md import AgentsMdWriter
from .base import Writer
from .claude_code import ClaudeCodeWriter
from .markdown_rules import MarkdownRulesWriter
from .null_writer import NullWriter
from .skills_preamble import SkillsPreambleWriter

__all__ = ["WRITER_REGISTRY", "get_writer"]

WRITER_REGISTRY: dict[str, Writer] = {
    # Pattern A — Claude Code (hook + CLAUDE.md section)
    "claude": ClaudeCodeWriter(),
    # Pattern B — MarkdownRulesWriter (parameterised per harness)
    # check_dir allows can_write() to check the harness root rather than the
    # potentially non-existent rules subdirectory.
    "cursor":   MarkdownRulesWriter("cursor",   ".cursor/rules/spec-kitty.mdc",    append_mode=False, check_dir=".cursor"),
    "windsurf": MarkdownRulesWriter("windsurf", ".windsurf/rules/spec-kitty.md",   append_mode=False, check_dir=".windsurf"),
    "copilot":  MarkdownRulesWriter("copilot",  ".github/copilot-instructions.md", append_mode=True,  check_dir=".github"),
    # "roo" removed — Roo Code shut down on 2026-05-15 (C-007)
    "kiro":     MarkdownRulesWriter("kiro",     ".kiro/steering/spec-kitty.md",    append_mode=False, check_dir=".kiro"),
    "gemini":   MarkdownRulesWriter("gemini",   "GEMINI.md",                       append_mode=True,  check_dir=".gemini"),
    "llxprt":   MarkdownRulesWriter("llxprt",   "LLXPRT.md",                       append_mode=True,  check_dir=".llxprt"),
    # Pattern C — AgentsMdWriter (AGENTS.md at project root; always writable)
    "codex":       AgentsMdWriter("codex"),
    "opencode":    AgentsMdWriter("opencode"),
    "antigravity": AgentsMdWriter("antigravity"),
    # Pattern D — SkillsPreambleWriter (defaults to AGENTS.md; upgradeable per-harness)
    "pi":    SkillsPreambleWriter("pi"),
    "vibe":  SkillsPreambleWriter("vibe"),
    "letta": SkillsPreambleWriter("letta"),
    # Pattern E — NullWriter (no known orientation mechanism; no error raised)
    # See docs/plans/research/session-presence-harness-gaps.md for research status.
    "qwen":     NullWriter("qwen"),
    "kilocode": NullWriter("kilocode"),
    "auggie":   NullWriter("auggie"),
    "q":        NullWriter("q"),
}


def get_writer(agent_key: str) -> Writer:
    """Return the Writer for the given agent key, or NullWriter if unregistered."""
    return WRITER_REGISTRY.get(agent_key, NullWriter(agent_key))
