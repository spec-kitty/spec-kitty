"""Harness capability matrix for native agent profile projection.

This module declares, for every configured harness (keys of
:data:`~specify_cli.core.config.AI_CHOICES`), whether that harness exposes a
*native named-agent primitive* — a first-class mechanism for injecting a
persona that the tool presents in an agent picker or equivalent UI.

The matrix drives two behaviours:

1. **Provider findings** — :class:`~.providers.agent_profiles.AgentProfilesProvider`
   consults :data:`HARNESS_CAPABILITY_MATRIX` to decide whether to emit a
   ``not_applicable`` info finding (no native primitive) or proceed with
   filesystem inspection (native primitive supported).
2. **Doctor completeness** — every configured harness must have a record here,
   even if its status is ``not_applicable``.  A missing record signals an
   unassessed harness (``research_gap``); this WP drives every assessed harness
   to a definitive verdict.

Design note: harnesses marked ``has_native_agent_primitive=False`` are NOT
broken; they surface Spec Kitty personas through other mechanisms (skills,
workflow surfaces, command surfaces).  The doctor should remain ``ok: true``
even when all configured harnesses fall into this category.
"""

from __future__ import annotations

from dataclasses import dataclass

from specify_cli.core.config import AI_CHOICES


@dataclass(frozen=True)
class HarnessCapabilityRecord:
    """Capability declaration for one configured harness.

    Attributes:
        harness_key: The tool key as it appears in :data:`AI_CHOICES`.
        has_native_agent_primitive: ``True`` when the tool exposes a first-class
            mechanism for named agent projection (e.g. ``.claude/agents/``).
        reason: Human-readable rationale, included in doctor findings.
            Must not contain machine-specific paths or user-identifying data.
    """

    harness_key: str
    has_native_agent_primitive: bool
    reason: str


# ---------------------------------------------------------------------------
# Capability records — keep in sync with AI_CHOICES in config.py.
# ---------------------------------------------------------------------------
# Supported harnesses (native named-agent primitives confirmed):
_SUPPORTED = [
    HarnessCapabilityRecord(
        "claude",
        True,
        "Native: .claude/agents/<id>.md",
    ),
    HarnessCapabilityRecord(
        "copilot",
        True,
        "Native: .github/agents/<id>.agent.md",
    ),
    HarnessCapabilityRecord(
        "codex",
        True,
        "Native: .codex/agents/<id>.toml",
    ),
    HarnessCapabilityRecord(
        "auggie",
        True,
        "Native: .augment/agents/<id>.md",
    ),
    HarnessCapabilityRecord(
        "q",
        True,
        "User-global: ~/.aws/amazonq/cli-agents/<id>.json",
    ),
]

# Not-applicable harnesses — no confirmed native agent primitive as of research
# date.  Skills/command/workflow surfaces are the supported fallback.
_NOT_APPLICABLE_REASONS: dict[str, str] = {
    "windsurf": "No native agent primitive; use workflow/rule surfaces",
    "cursor": "No native agent primitive; use rule surfaces",
    "kiro": "No native agent primitive; use prompt surfaces",
    "gemini": "No native agent primitive; use command surfaces",
    "llxprt": "No native agent primitive; use command surfaces",
    "qwen": "No native agent primitive; use command surfaces",
    "opencode": "No native agent primitive; use command surfaces",
    "kilocode": "No native agent primitive; use workflow surfaces",
    "antigravity": "No native agent primitive; use workflow surfaces",
    "vibe": "No native agent primitive; use skill surfaces",
    "pi": "No native agent primitive; use skill surfaces",
    "letta": "No native agent primitive; use skill surfaces",
}


def _build_matrix() -> dict[str, HarnessCapabilityRecord]:
    """Build the matrix, ensuring every key in AI_CHOICES is covered."""
    matrix: dict[str, HarnessCapabilityRecord] = {}

    # Populate explicitly researched supported harnesses first.
    for record in _SUPPORTED:
        matrix[record.harness_key] = record

    # Populate explicitly researched not-applicable harnesses.
    for key, reason in _NOT_APPLICABLE_REASONS.items():
        matrix[key] = HarnessCapabilityRecord(key, False, reason)

    # Emit a research-gap record for any AI_CHOICES key not yet assessed.
    # This acts as a completeness guard: if a new harness is added to
    # AI_CHOICES without a corresponding entry above, it surfaces as a
    # research_gap rather than silently being omitted.
    for key in AI_CHOICES:
        if key not in matrix:
            matrix[key] = HarnessCapabilityRecord(
                key,
                False,
                "Not yet assessed for native agent primitive support (research gap).",
            )

    return matrix


#: Immutable mapping from harness key to its capability record.
#: Every key from :data:`~specify_cli.core.config.AI_CHOICES` is guaranteed
#: to be present (assessed or research-gap sentinel).
HARNESS_CAPABILITY_MATRIX: dict[str, HarnessCapabilityRecord] = _build_matrix()


def is_research_gap(key: str) -> bool:
    """Return ``True`` when *key* has not been formally assessed.

    A record is a research gap when it was auto-generated by
    :func:`_build_matrix` from an unassessed ``AI_CHOICES`` key rather than
    explicitly declared above.  Use this predicate in doctor output to
    distinguish ``not_applicable`` (researched and confirmed) from
    ``research_gap`` (not yet assessed).
    """
    record = HARNESS_CAPABILITY_MATRIX.get(key)
    if record is None:
        return True
    assessed_keys = {r.harness_key for r in _SUPPORTED} | set(_NOT_APPLICABLE_REASONS)
    return key not in assessed_keys
