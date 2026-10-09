"""Bridges dispatch action/role verbs to routing-catalog ``task_type`` ids (FR-002).

The governed dispatch seam (``ProfileInvocationExecutor.invoke()``)
resolves a single canonical action verb per invocation -- drawn from
``DEFAULT_ROLE_CAPABILITIES[role].canonical_verbs``
(``charter.offering.agent_profiles.capabilities``) via
``_derive_action_from_request`` / ``ActionRouter``. This module is the
one explicit, maintained bridge from that verb namespace to the
``model-to-task_type`` catalog's ``task_type`` vocabulary
(``charter.offering.model_task_routing.models.TASK_TYPE_PATTERN``).

Design note -- flat verb map, not a (role, verb) pair: a few verbs are
shared across roles (e.g. ``"audit"`` for both reviewer and architect,
``"plan"`` for both architect and planner) and resolve to a single
task_type each. That mirrors the dispatch seam's action model, which
carries only the resolved verb, not the pair -- a deliberate
simplification, not an oversight.

**Live maintenance seam**: every canonical verb declared in
``DEFAULT_ROLE_CAPABILITIES`` MUST have an entry here. Adding a role or
verb to ``capabilities.py`` without updating ``_VERB_TO_TASK_TYPE`` is
caught by
``tests/charter_offering/test_task_class_map.py::test_map_covers_every_canonical_verb``.
"""

from __future__ import annotations

# Maps each DEFAULT_ROLE_CAPABILITIES canonical verb to a catalog
# task_type id. Values are provisional (WP05 ships the populated catalog
# instance) but must stay schema-legal (TASK_TYPE_PATTERN) and stable, as
# they are the maintained vocabulary bridge, not throwaway labels.
_VERB_TO_TASK_TYPE: dict[str, str] = {
    # Role.IMPLEMENTER
    "generate": "code-generation",
    "refine": "code-refinement",
    "implement": "code-implementation",
    # Role.REVIEWER
    "audit": "quality-audit",
    "assess": "quality-assessment",
    "review": "code-review",
    # Role.ARCHITECT (audit/plan shared with reviewer/planner above)
    "synthesize": "synthesis",
    # Role.DESIGNER (synthesize shared with architect above)
    "draft": "drafting",
    "design": "design",
    # Role.PLANNER (plan shared with architect below)
    "plan": "planning",
    "decompose": "task-decomposition",
    "prioritize": "prioritization",
    # Role.RESEARCHER
    "analyze": "analysis",
    "investigate": "investigation",
    "summarize": "summarization",
    # Role.CURATOR
    "classify": "classification",
    "curate": "curation",
    "validate": "validation",
    # Role.MANAGER
    "coordinate": "coordination",
    "delegate": "delegation",
    "monitor": "monitoring",
}


def task_type_for_verb(verb: str) -> str | None:
    """Map a dispatch action/role verb to a catalog ``task_type`` id.

    Returns ``None`` for verbs outside the maintained namespace (e.g. a
    custom role's verb, or an unrecognized action) -- advisory,
    non-fatal per FR-002; callers must not treat an absent mapping as an
    error.
    """
    return _VERB_TO_TASK_TYPE.get(verb)


def known_verbs() -> frozenset[str]:
    """Return the verbs this map currently covers.

    Exposed for parity checks against
    ``DEFAULT_ROLE_CAPABILITIES`` canonical verbs.
    """
    return frozenset(_VERB_TO_TASK_TYPE)
