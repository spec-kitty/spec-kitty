"""Shipped default-profile bindings for built-in mission steps (#4115).

Leaf module: stdlib-only imports, so the operator surfaces that only need
the binding tables (``charter deactivate``'s warning, ``charter preflight``'s
advisory warnings — both on hot or interactive paths) do not pay the
``mission_step_contracts.executor`` import chain (``specify_cli.invocation``,
glossary chokepoint, ~1s cold).

``StepContractExecutor`` re-exports everything here, so the pre-existing
import sites (``runtime_bridge_composition``, the composition tests) that
read ``_ACTION_PROFILE_DEFAULTS`` off the executor module keep working
unchanged.
"""

from __future__ import annotations

from typing import Final

__all__ = ["mission_default_profile_warning"]


# FR-008 / Phase 6 #505: this table is for built-in missions ONLY.
# Custom missions MUST resolve profile_hint via PromptStep.agent_profile;
# expanding this table for arbitrary custom missions is forbidden.
# See kitty-specs/local-custom-mission-loader-01KQ2VNJ/research.md §R-003.
_ACTION_PROFILE_DEFAULTS: Final[dict[tuple[str, str], str]] = {
    ("software-dev", "specify"): "researcher-robbie",
    ("software-dev", "plan"): "architect-alphonso",
    ("software-dev", "tasks"): "architect-alphonso",
    ("software-dev", "implement"): "implementer-ivan",
    ("software-dev", "review"): "reviewer-renata",
    ("research", "scoping"): "researcher-robbie",
    ("research", "methodology"): "researcher-robbie",
    ("research", "gathering"): "researcher-robbie",
    ("research", "synthesis"): "researcher-robbie",
    ("research", "output"): "reviewer-renata",
    ("documentation", "discover"): "researcher-robbie",
    ("documentation", "audit"): "researcher-robbie",
    ("documentation", "design"): "architect-alphonso",
    ("documentation", "generate"): "implementer-ivan",
    ("documentation", "validate"): "reviewer-renata",
    ("documentation", "publish"): "reviewer-renata",
    ("documentation", "accept"): "reviewer-renata",
    ("plan", "specify"): "researcher-robbie",
    ("plan", "research"): "researcher-robbie",
    ("plan", "plan"): "architect-alphonso",
    ("plan", "review"): "reviewer-renata",
}

#: Primary role of each shipped default profile above (mirrors each
#: profile's first ``roles:`` entry in ``packs/built-in/agent_profiles/``;
#: ``tests/specify_cli/mission_step_contracts/test_profile_fallback.py``
#: guards both directions of that mirror against pack drift). Used ONLY by
#: the role-based fallback in
#: ``StepContractExecutor._resolve_profile_hint`` (#4115): when a table
#: default is deactivated it is absent from the invocation catalog, so its
#: role cannot be read from the catalog and must be pinned here.
_DEFAULT_PROFILE_ROLES: Final[dict[str, str]] = {
    "researcher-robbie": "researcher",
    "architect-alphonso": "architect",
    "implementer-ivan": "implementer",
    "reviewer-renata": "reviewer",
}


def mission_default_profile_warning(profile_id: str) -> str | None:
    """Advisory warning text when *profile_id* is a shipped mission-step
    default profile; ``None`` for any other profile id.

    Shared by the two operator surfaces #4115 asks to warn on — ``charter
    deactivate agent-profile <id>`` and ``charter preflight`` — so the
    wording can never drift between them. Pure and table-driven: no repo
    access, so the CLI surfaces decide when to call it (deactivate: for the
    artifact(s) it just removed; preflight: for each table default absent
    from the activated set).
    """
    bound = [f"{mission}/{action}" for (mission, action), profile in sorted(_ACTION_PROFILE_DEFAULTS.items()) if profile == profile_id]
    if not bound:
        return None
    role = _DEFAULT_PROFILE_ROLES.get(profile_id)
    role_note = f"'{role}'-role" if role is not None else "same-role"
    return (
        f"agent profile '{profile_id}' is the built-in default profile for the "
        f"mission steps: {', '.join(bound)}. With it deactivated, those steps "
        f"dispatch through the next available {role_note} profile, or block when "
        "no available profile carries that role — activate a profile with that "
        "role to keep them running."
    )
