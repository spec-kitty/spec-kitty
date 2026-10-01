"""Arbiter checklist and rationale model for false-positive review rejections.

When an arbiter overrides a rejection (detected as a forced ``planned`` →
``approved``/``done`` move after a rejection event; forced rework is not one, #5196), the system presents a 5-question checklist,
derives a category, and records the decision as a durable, event-sourced
``ReviewOverride`` (FR-009/FR-010/FR-011, mission
``review-cycle-verdict-seam-rebuild-01KZ2W7W`` WP12, "arbiter-override-retirement")
— the SAME event-sourced mechanism ``--skip-review-artifact-check``'s override
path already uses (:func:`specify_cli.cli.commands.agent.tasks_materialization.
_persist_review_artifact_override`, ADR 2026-07-19-1). Two prior, non-durable,
never-committed representations are retired (data-model.md's "Arbiter override"
entity, representations #2/#3): an ``arbiter_override`` block stamped onto
``review-cycle-N.md``'s frontmatter, and a standalone ``arbiter-override-N.json``
sidecar.

The ``review_ref`` in the emitted event points to the existing ``review-cycle://``
artifact — no new pointer scheme is introduced.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kernel.clock import now_utc_iso
from specify_cli.review.artifacts import ReviewCycleArtifact, _review_cycle_filename
from specify_cli.review.cycle import _review_cycle_wp_dir
from specify_cli.status import Lane, read_events

if TYPE_CHECKING:
    from specify_cli.status.models import StatusEvent


# ---------------------------------------------------------------------------
# Category enum
# ---------------------------------------------------------------------------


class ArbiterCategory(StrEnum):
    """Structured categories for arbiter override rationales."""

    PRE_EXISTING_FAILURE = "pre_existing_failure"
    WRONG_CONTEXT = "wrong_context"
    CROSS_SCOPE = "cross_scope"
    INFRA_ENVIRONMENTAL = "infra_environmental"
    CUSTOM = "custom"


# Default explanation templates keyed by category
_CATEGORY_DEFAULTS: dict[ArbiterCategory, str] = {
    ArbiterCategory.PRE_EXISTING_FAILURE: "Failure is pre-existing on the base branch and unrelated to this WP.",
    ArbiterCategory.WRONG_CONTEXT: "Reviewer is discussing the wrong feature or WP.",
    ArbiterCategory.CROSS_SCOPE: "Finding is outside this WP's defined scope.",
    ArbiterCategory.INFRA_ENVIRONMENTAL: "Failure is environmental or infrastructure-related, not a code defect.",
    ArbiterCategory.CUSTOM: "",  # CUSTOM requires mandatory non-empty explanation
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArbiterChecklist:
    """Five-question checklist that drives arbiter category derivation."""

    is_pre_existing: bool  # Q1: Is the failure pre-existing on the base branch?
    is_correct_context: bool  # Q2: Is the reviewer talking about the correct feature/WP?
    is_in_scope: bool  # Q3: Is the finding within this WP's scope?
    is_environmental: bool  # Q4: Is the failure environmental/infra?
    should_follow_on: bool  # Q5: Should this become a follow-on issue instead?

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_pre_existing": self.is_pre_existing,
            "is_correct_context": self.is_correct_context,
            "is_in_scope": self.is_in_scope,
            "is_environmental": self.is_environmental,
            "should_follow_on": self.should_follow_on,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArbiterChecklist:
        return cls(
            is_pre_existing=bool(data["is_pre_existing"]),
            is_correct_context=bool(data["is_correct_context"]),
            is_in_scope=bool(data["is_in_scope"]),
            is_environmental=bool(data["is_environmental"]),
            should_follow_on=bool(data["should_follow_on"]),
        )


@dataclass(frozen=True)
class ArbiterDecision:
    """Structured arbiter override decision with rationale."""

    arbiter: str  # who made the decision
    category: ArbiterCategory
    explanation: str  # mandatory for all categories, especially CUSTOM
    checklist: ArbiterChecklist
    decided_at: str  # ISO 8601 UTC

    def to_dict(self) -> dict[str, Any]:
        return {
            "arbiter": self.arbiter,
            "category": str(self.category),
            "explanation": self.explanation,
            "checklist": self.checklist.to_dict(),
            "decided_at": self.decided_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArbiterDecision:
        return cls(
            arbiter=data["arbiter"],
            category=ArbiterCategory(data["category"]),
            explanation=data["explanation"],
            checklist=ArbiterChecklist.from_dict(data["checklist"]),
            decided_at=data["decided_at"],
        )


# ---------------------------------------------------------------------------
# Category derivation
# ---------------------------------------------------------------------------


def _derive_category(checklist: ArbiterChecklist) -> ArbiterCategory:
    """Derive the arbiter category from checklist answers.

    Priority order mirrors the most common override scenarios:
    1. Pre-existing failure (strongest signal)
    2. Wrong context (reviewer confusion)
    3. Out of scope (scoping disagreement)
    4. Environmental (infra flakiness)
    5. Custom (everything else)
    """
    if checklist.is_pre_existing:
        return ArbiterCategory.PRE_EXISTING_FAILURE
    if not checklist.is_correct_context:
        return ArbiterCategory.WRONG_CONTEXT
    if not checklist.is_in_scope:
        return ArbiterCategory.CROSS_SCOPE
    if checklist.is_environmental:
        return ArbiterCategory.INFRA_ENVIRONMENTAL
    return ArbiterCategory.CUSTOM


# ---------------------------------------------------------------------------
# Note parsing
# ---------------------------------------------------------------------------

_NOTE_CATEGORY_RE = re.compile(r"^\s*\[([a-z_]+)\]\s*(.*)", re.DOTALL)


def parse_category_from_note(note: str | None) -> tuple[ArbiterCategory, str]:
    """Parse structured note format ``"[category] explanation"``.

    Returns a ``(category, explanation)`` tuple.  If the note does not contain
    a recognised category prefix the category defaults to ``CUSTOM`` and the
    full note text becomes the explanation.

    Examples::

        "[pre_existing_failure] Test was already failing" → (PRE_EXISTING_FAILURE, "Test was ...")
        "Some freeform note" → (CUSTOM, "Some freeform note")
    """
    if not note:
        return ArbiterCategory.CUSTOM, "Override without explanation"

    m = _NOTE_CATEGORY_RE.match(note)
    if m:
        raw_cat = m.group(1).strip()
        explanation = m.group(2).strip()
        try:
            category = ArbiterCategory(raw_cat)
        except ValueError:
            category = ArbiterCategory.CUSTOM
            explanation = note.strip()
        # If explanation is empty after bracket parsing, fall back to default
        if not explanation:
            explanation = _CATEGORY_DEFAULTS.get(category) or f"Override: {category}"
        return category, explanation

    return ArbiterCategory.CUSTOM, note.strip()


# ---------------------------------------------------------------------------
# Non-interactive factory
# ---------------------------------------------------------------------------


def create_arbiter_decision(
    arbiter_name: str,
    category: str | ArbiterCategory,
    explanation: str,
    checklist: ArbiterChecklist | None = None,
) -> ArbiterDecision:
    """Non-interactive arbiter decision creation for CI / agent contexts.

    Args:
        arbiter_name: Name of the arbiter (e.g., "operator", "claude").
        category: Category string or ``ArbiterCategory`` enum value.
        explanation: Mandatory rationale text.
        checklist: Optional checklist; if ``None`` a synthetic one is derived
            from the category to preserve round-trip fidelity.

    Returns:
        A populated :class:`ArbiterDecision`.
    """
    if isinstance(category, str):
        try:
            cat = ArbiterCategory(category)
        except ValueError:
            cat = ArbiterCategory.CUSTOM
    else:
        cat = category

    if not explanation:
        explanation = _CATEGORY_DEFAULTS.get(cat) or f"Override: {cat}"

    if checklist is None:
        checklist = _synthetic_checklist(cat)

    return ArbiterDecision(
        arbiter=arbiter_name or "operator",
        category=cat,
        explanation=explanation,
        checklist=checklist,
        decided_at=now_utc_iso(),
    )


def _synthetic_checklist(category: ArbiterCategory) -> ArbiterChecklist:
    """Build a synthetic checklist consistent with the given category."""
    return ArbiterChecklist(
        is_pre_existing=(category == ArbiterCategory.PRE_EXISTING_FAILURE),
        is_correct_context=(category != ArbiterCategory.WRONG_CONTEXT),
        is_in_scope=(category != ArbiterCategory.CROSS_SCOPE),
        is_environmental=(category == ArbiterCategory.INFRA_ENVIRONMENTAL),
        should_follow_on=False,
    )


# ---------------------------------------------------------------------------
# Override detection
# ---------------------------------------------------------------------------


_ARBITER_DECISION_TARGETS = frozenset({Lane.APPROVED, Lane.DONE})
_REJECTION_SOURCES = frozenset({Lane.FOR_REVIEW, Lane.IN_REVIEW})


def _is_rejection_event(event: StatusEvent) -> bool:
    """True iff ``event`` is a review rejection (back to ``planned`` with a ``review_ref``).

    Sibling predicate — keep in lockstep: ``review_roles._is_reviewer_rework_verdict``
    encodes the same "a reviewer verdict happened" concept for a different purpose
    (the latest-implementer projection) and so uses a deliberately WIDER lane set
    (it also admits ``approved`` as a source and any target lane). A future change
    to "what counts as a reviewer verdict" must be weighed against both. (#5196)
    The retrospective and hollow-review signal reads a third, widest variant:
    ``review.rejection_signal.is_documented_review_rejection`` (#2267).
    """
    return event.to_lane == Lane.PLANNED and event.from_lane in _REJECTION_SOURCES and event.review_ref is not None


def is_arbiter_override_history(
    events: Sequence[StatusEvent],
    wp_id: str,
    old_lane: str,
    target_lane: str,
    force: bool,
) -> bool:
    """Pure override predicate over an already-read event history.

    An arbiter override requires ALL of these to be true:
    1. ``--force`` flag is set.
    2. Current lane is ``planned``.
    3. Target lane is a decision lane: ``approved`` or ``done``. Forced rework
       to ``claimed``/``in_progress``/``for_review`` is NOT an override (#5196).
    4. The latest event for this WP is a rejection: a transition to ``planned``
       from ``for_review`` or ``in_review`` with a non-``None`` ``review_ref``.
       ``approved`` → ``planned`` (a reopen) is deliberately excluded.

    Normative truth table: ``contracts/arbiter-override-classification.md``
    (decision moment ``01M3MQXYAFEYE62RA5513KKNX6``).
    """
    if not force:
        return False
    if Lane(old_lane) != Lane.PLANNED:
        return False
    if Lane(target_lane) not in _ARBITER_DECISION_TARGETS:
        return False

    wp_events = [e for e in events if e.wp_id == wp_id]
    if not wp_events:
        return False

    return _is_rejection_event(wp_events[-1])


def _is_arbiter_override(
    feature_dir: Path,
    wp_id: str,
    old_lane: str,
    target_lane: str,
    force: bool,
) -> bool:
    """Detect if this force move is an arbiter override of a rejection.

    Thin shell: reads the event log once and delegates to
    :func:`is_arbiter_override_history`.
    """
    if not force:
        return False
    return is_arbiter_override_history(read_events(feature_dir), wp_id, old_lane, target_lane, force)


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def persist_arbiter_decision(
    feature_dir: Path,
    wp_id: str,
    review_ref: str | None,
    decision: ArbiterDecision,
    repo_root: Path,
) -> Path:
    """Persist an ArbiterDecision as a durable, event-sourced ``ReviewOverride``.

    FR-009/FR-010/FR-011 (WP12, arbiter-override-retirement): retires the two
    non-authoritative representations this function used to dispatch between
    — a frontmatter ``arbiter_override`` block and a standalone
    ``arbiter-override-N.json`` sidecar, NEITHER ever durably committed
    (data-model.md's "Arbiter override" entity, representations #2/#3). Both
    retire INTO representation #1: the already-durable, already-merge-gate-
    consumed event-sourced ``ReviewOverride``
    (:func:`specify_cli.cli.commands.agent.tasks_materialization.
    _persist_review_artifact_override` — the SAME mechanism
    ``--skip-review-artifact-check``'s override path already uses, ADR
    2026-07-19-1). Exactly ONE path now: resolve the review-cycle artifact
    this override annotates via the SAME slug-aware owner-function resolver
    the writer uses (``_resolve_wp_slug`` + ``_review_cycle_wp_dir`` — WP13/
    FR-007: ADR 2026-08-03-1 designates review-cycle artifacts COORD-partition
    under a coordination topology, PRIMARY otherwise, but ``_review_cycle_
    wp_dir`` deliberately still resolves PRIMARY only — see that function's
    own docstring for the disclosed safety finding blocking the full flip;
    this call inherits whichever behaviour that owner function has, unchanged
    by anything in this file — T053: the retired resolver bare-``wp_id``-joined
    a directory that
    almost never existed, and picked the lexicographically- rather than
    numerically-highest cycle once a WP reached ten review cycles), then
    emit the override event unconditionally — no branch on whether an
    artifact happens to already exist on disk
    (``_persist_review_artifact_override`` only needs the artifact PATH's
    shape to derive its emit target, never the file's existence; see that
    function's own docstring).

    ``ArbiterCategory``/``ArbiterChecklist`` have no home in
    ``ReviewOverride``'s frozen four-field shape (``at``/``actor``/``wp_id``/
    ``reason`` — ``specify_cli.status.models.ReviewOverride``'s docstring
    forbids a fifth field): the category is folded into ``reason`` as
    ``"[category] explanation"`` prose, the same format
    :func:`parse_category_from_note` already parses back out elsewhere (see
    :func:`get_arbiter_overrides_for_wp`, below) — never dropped, never a new
    field.

    ``review_ref`` is accepted for call-site/signature compatibility but is
    NOT consulted for resolution (T053's slug/cycle-number resolution
    supersedes it) — this mirrors PRE-EXISTING behaviour: the retired
    ``_find_review_cycle_artifact`` never actually used its own
    ``review_ref`` parameter either (measured dead even before this WP).

    ``repo_root`` is the CALLER-RESOLVED ``main_repo_root`` (FR-016, WP07,
    arbiter-root-threading) and resolves the emitted event's status-lock
    (``emit_inner_state_changed``'s own docstring). It is now a REQUIRED
    parameter — this function never self-infers it. The retired fallback
    was ``feature_dir.parent.parent``, which happened to coincide with the
    correct root only for a SINGLE_BRANCH/LANES-topology mission (every
    fixture the old code exercised): under a coordination topology, callers
    pass an already-topology-resolved ``feature_dir`` (e.g. the coord-husk
    mission dir), so ``feature_dir.parent.parent`` yields the COORD
    WORKTREE root — not the real ``main_repo_root`` this function and its
    callees need to correctly resolve the coord partition — a wrong-partition
    bug the self-inference could not detect. Every caller (``_run_arbiter_
    override`` in ``tasks_move_task.py``, via ``persist_arbiter_override_
    decision`` in ``tasks_verdict_persistence.py``, both outside this WP's
    ``owned_files``) now threads its own already-resolved ``main_repo_root``
    through explicitly instead.

    Returns:
        The (possibly not-yet-existing-on-disk) review-cycle artifact path
        this override annotates.
    """
    from specify_cli.cli.commands.agent.tasks_materialization import (
        _persist_review_artifact_override,
        _resolve_wp_slug,
    )

    main_repo_root = repo_root
    mission_slug = feature_dir.name
    # ``str()``/``Path`` coercions below are DELIBERATE (not decorative): both
    # ``_resolve_wp_slug`` and ``_review_cycle_wp_dir`` resolve as ``Any`` at
    # this module's ``follow_imports=skip`` boundary (the same narrowing
    # ``_review_cycle_wp_dir``'s own docstring and ``_resolve_wp_slug``'s own
    # comment describe) — bind explicitly so this function's declared
    # ``-> Path`` return stays real, not a laundered ``Any``.
    wp_slug: str = str(_resolve_wp_slug(main_repo_root, mission_slug, wp_id))
    wp_subdir: Path = Path(_review_cycle_wp_dir(main_repo_root, mission_slug, wp_slug))
    # Filename-only resolution (#3244, T017): a damaged review-cycle artifact
    # left by a prior fail-open merge-driver downgrade (git conflict markers,
    # no valid YAML frontmatter) must not crash override persistence.
    # ``latest_cycle_number`` derives the number from filenames alone -- it
    # never parses a candidate's body -- unlike ``.latest(...).cycle_number``,
    # which fully parses the highest-numbered file's frontmatter via
    # ``from_file`` and would raise on such a file. ``.latest``/``from_file``
    # themselves are left untouched (C-004): a second consumer
    # (``cli/commands/agent/workflow_executor.py:1134``) needs the full
    # parsed body and is out of this WP's scope -- flagged as a same-shape
    # follow-up, not fixed here.
    cycle_number = ReviewCycleArtifact.latest_cycle_number(wp_subdir) if wp_subdir.exists() else 0
    artifact_path: Path = wp_subdir / _review_cycle_filename(cycle_number)

    reason = f"[{decision.category}] {decision.explanation}"
    _persist_review_artifact_override(
        artifact_path,
        repo_root=main_repo_root,
        wp_id=wp_id,
        actor=decision.arbiter,
        reason=reason,
    )
    return artifact_path


# ---------------------------------------------------------------------------
# Arbiter override history query (for kanban display)
# ---------------------------------------------------------------------------


def get_arbiter_overrides_for_wp(
    feature_dir: Path,
    wp_id: str,
) -> list[dict[str, Any]]:
    """Return the current durable override for a WP, event-sourced (FR-009).

    Retired (T051/T052): this used to scan ``arbiter-override-*.json``
    sidecars and ``review-cycle-*.md`` frontmatter under a bare-``wp_id``-
    joined directory — both non-authoritative, never-durably-committed
    representations, and (per spec.md User Story 4) an uncaught-crash-prone
    manual YAML parse inconsistent with every other reader's declared
    failure polarity. The event-sourced ``ReviewOverride`` on the reduced
    ``review`` snapshot slot (the SAME record
    ``_persist_review_artifact_override`` writes) is now the single source,
    read via :func:`specify_cli.status.wp_snapshot_state` — the shared
    spelling of ``read_event_stream`` -> ``reduce`` ->
    ``work_packages.get(wp_id)`` (IC-08 / #2093), not a hand-rolled
    re-derivation.

    Returns AT MOST one entry: the event-sourced override is a single
    reduced CURRENT state, not the per-cycle accumulation the retired
    frontmatter/JSON scan used to build up. Kept list-shaped so
    ``agent tasks status``'s existing
    ``for override in get_arbiter_overrides_for_wp(...)`` call site
    (``tasks_status_cmd.py``, outside this WP's ``owned_files``) keeps
    working unmodified. An incomplete override (missing any of
    ``at``/``actor``/``wp_id``/``reason``) is never surfaced, mirroring
    ``ReviewOverride.complete``'s predicate everywhere else it is honoured.
    """
    from specify_cli.status import ReviewOverride, wp_snapshot_state

    state = wp_snapshot_state(feature_dir, wp_id)
    review_raw = state.get("review") if state is not None else None
    if not isinstance(review_raw, Mapping):
        return []
    try:
        override = ReviewOverride.from_dict(review_raw)
    except (KeyError, TypeError, ValueError):
        return []
    if not override.complete:
        return []
    category, explanation = parse_category_from_note(override.reason)
    return [
        {
            "arbiter": override.actor,
            "category": str(category),
            "explanation": explanation,
            "decided_at": override.at,
        }
    ]
