"""Capability-gated typed WorkObservation validation (spec-kitty#4268).

The shared ``WorkObservation`` contract (``spec_kitty_events.work_observation``)
landed in events 10.1.0 (events#55/#56). The CLI now pins
``spec-kitty-events>=10.4.0,<11`` (the post-launch adoption off the 9.1.6
launch train, spec-kitty#4990), so the contract is present and every
emission is model-validated: :func:`codec_state` reports ``"typed"``.
Events' own COMPATIBILITY.md 10.1.0 entry mandated the capability gate
implemented here — "Producers MUST capability-gate ``WorkObservation``
emission until each intended consumer … can validate it" — and the gate is
retained as defensive, first-class capability-matrix state (never a silent
green) so a degraded install that somehow lacks the contract is reported as
``"pending-events-10"`` rather than crashing.

So the CLI's capture layer emits live frames through the content-agnostic
``event.publish`` wire using the contract's exact ``work.<kind>.v1`` payload
IDs, and validates its records against the typed contract whenever the
installed events package provides it.

This module owns no vocabulary of its own: the kind strings and field
rules live in :mod:`live_work.kinds` / :mod:`live_work.models`, pinned
against the shared contract by test.
"""

from __future__ import annotations

import re
from importlib import import_module
from types import ModuleType

from .models import Observation

__all__ = [
    "codec_state",
    "validate_typed",
]

#: Characters not permitted in the shared contract's ``repository_id``
#: (``^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$``).
_REPO_ID_DISALLOWED = re.compile(r"[^A-Za-z0-9._-]")


def _conforming_repository_id(slug: str) -> str:
    """Derive a deterministic, pattern-conforming ``repository_id`` from the
    ``owner/name`` display slug.

    **Interim, pending the server-vetted id (saas#1814).** The shared
    ``WorkObservation`` contract splits repository identity into a stable
    ``repository_id`` (``^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`` — no slashes;
    canonically the provider's numeric repository id, which is *server*-owned)
    and the mutable ``display_slug`` (``owner/name``). A pure producer like the
    CLI does not hold the server-vetted numeric id, so until saas#1814 threads
    it through we emit a deterministic sanitized derivation of the slug that
    satisfies the contract pattern; ``display_slug`` carries the true
    ``owner/name`` unchanged. Stable for a given slug (a slug change is a rename
    the server reconciles), and never a silent wire drop.
    """
    sanitized = _REPO_ID_DISALLOWED.sub("-", slug).lstrip("._-")
    if not sanitized:
        return "repository"
    if not sanitized[0].isalnum():
        sanitized = f"r{sanitized}"
    return sanitized[:64]


def _load_work_observation() -> ModuleType | None:
    """Import the shared typed contract, or ``None`` when not installed."""
    try:
        module = import_module("spec_kitty_events.work_observation")
    except ImportError:
        return None
    if not hasattr(module, "WorkObservationPayload"):
        return None
    return module


def codec_state() -> str:
    """The typed-codec gate state for the capability matrix.

    ``"typed"`` — the installed events package carries ``work_observation``
    and every emission is validated against the shared models. This is the
    expected state now that the CLI pins ``spec-kitty-events>=10.4.0,<11``.
    ``"pending-events-10"`` — a degraded install whose events package lacks
    the WorkObservation contract; emissions carry the contract's payload IDs
    and bounded field rules but are not yet model-validated. Either state is
    *visible*; a silent green is what this function exists to prevent.
    """
    return "typed" if _load_work_observation() is not None else "pending-events-10"


def validate_typed(observation: Observation) -> str | None:
    """Validate one observation against the shared typed contract.

    Returns ``None`` when validation passed (or when the typed codec is not
    installed — the gate above); returns a human-readable validation error
    when the shared models reject the record, so the caller drops the frame
    and records a coverage gap rather than publishing an invalid payload.
    """
    module = _load_work_observation()
    if module is None:
        return None
    try:
        _build_shared_payload(module, observation)
    except Exception as exc:  # a projection/validation failure IS the result
        return f"shared WorkObservation contract rejected the record: {exc}"
    return None


def _build_shared_payload(module: ModuleType, observation: Observation) -> None:
    """Construct the shared ``WorkObservationPayload`` for one record.

    Kept deliberately literal: every field maps one-to-one so a mismatch
    between the CLI-side record and the shared contract surfaces as a
    construction/validation error here (pydantic validates on construct),
    not as a silently divergent wire payload. The constructed payload is
    discarded — validation is the point.

    ``module`` is dynamically imported (the contract postdates the pinned
    events version), so attribute access is intentionally untyped: the
    shared models' own validation is the authority this function defers to.
    """
    from .kinds import WorkEmissionKind
    from .models import ActorBinding

    kind_map = {
        WorkEmissionKind.SESSION_STARTED: module.WorkKind.SESSION_STARTED,
        WorkEmissionKind.SESSION_ENDED: module.WorkKind.SESSION_ENDED,
        WorkEmissionKind.DELEGATION_STARTED: module.WorkKind.DELEGATION_STARTED,
        WorkEmissionKind.DELEGATION_ENDED: module.WorkKind.DELEGATION_ENDED,
        WorkEmissionKind.TOOL_INVOKED: module.WorkKind.TOOL_INVOKED,
        WorkEmissionKind.FILE_EDITED: module.WorkKind.FILE_EDITED,
        WorkEmissionKind.TEST_EXECUTED: module.WorkKind.TEST_EXECUTED,
        WorkEmissionKind.RETROSPECTIVE_CAPTURED: module.WorkKind.RETROSPECTIVE_CAPTURED,
        WorkEmissionKind.RETROSPECTIVE_FAILED: module.WorkKind.RETROSPECTIVE_FAILED,
        WorkEmissionKind.RETROSPECTIVE_SKIPPED: module.WorkKind.RETROSPECTIVE_SKIPPED,
        WorkEmissionKind.COVERAGE_GAP: module.WorkKind.COVERAGE_GAP,
    }

    action = observation.action
    shared_action = _build_shared_action(module, action) if action is not None else None
    coverage = observation.coverage
    shared_coverage = module.CoverageGap(area=coverage.area, reason=coverage.reason) if coverage is not None else None
    actor = observation.actor
    if isinstance(actor, ActorBinding):
        shared_actor = module.ActorIdentity(
            principal_kind="agent",
            principal_id=actor.harness,
            agent_profile=module.AgentProfileRef(harness=actor.harness),
        )
    else:
        shared_actor = module.ActorIdentity(
            principal_kind="agent",
            principal_id="unknown",
            agent_profile=module.AgentProfileRef(harness="unknown"),
        )
    mission = observation.mission
    repository = observation.repository
    activity = observation.activity
    module.WorkObservationPayload(
        kind=kind_map[observation.kind],
        producer=module.ProducerIdentity(
            producer_id="spec-kitty-cli",
            instance_id=observation.session.session_id,
            sequence=0,
        ),
        session=module.SessionIdentity(
            session_id=observation.session.session_id,
            delegated_from=observation.session.parent_session_id,
        ),
        actor=shared_actor,
        repository=module.RepositoryIdentity(
            provider=repository.provider,
            repository_id=_conforming_repository_id(repository.slug),
            display_slug=repository.slug,
        ),
        provenance=module.SourceProvenance(
            source=observation.provenance.source,
            capability=observation.provenance.capability,
            limitation=observation.provenance.limitation,
        ),
        mission=(module.MissionIdentity(mission_id=mission.mission_id, display_label=mission.display_label) if mission is not None else None),
        activity=(
            module.ActivityRef(
                activity_id=activity.activity_id,
                parent_activity_id=activity.parent_activity_id,
            )
            if activity is not None
            else None
        ),
        action=shared_action,
        coverage=shared_coverage,
        text=observation.text,
    )


def _build_shared_action(module: ModuleType, action: object) -> object:
    """Project one typed action detail onto the shared contract's model."""
    from .models import FileDetail, TestRunDetail, ToolDetail

    if isinstance(action, ToolDetail):
        return module.ToolAction(
            tool=action.tool,
            state=module.ActionState(action.state.value),
            outcome=(module.ActionOutcome(action.outcome.value) if action.outcome is not None else None),
            duration_ms=action.duration_ms,
        )
    if isinstance(action, FileDetail):
        return module.FileAction(
            operation=module.FileOperation(action.operation.value),
            path=action.path,
            destination_path=action.destination_path,
            bytes_added=action.bytes_added,
            bytes_removed=action.bytes_removed,
        )
    if isinstance(action, TestRunDetail):
        return module.TestAction(
            selector=action.selector,
            state=module.ActionState(action.state.value),
            passed=action.passed,
            failed=action.failed,
            skipped=action.skipped,
            outcome=(module.ActionOutcome(action.outcome.value) if action.outcome is not None else None),
        )
    msg = f"unknown action detail type {type(action).__name__}"
    raise ValueError(msg)
