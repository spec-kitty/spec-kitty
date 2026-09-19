"""Validation engine for the canonical status model.

Provides schema validation, transition legality checks, done-evidence
completeness verification, materialization drift detection, and
derived-view drift comparison. Each function returns a list of
human-readable finding strings that reference specific event_ids.

This module is a library -- it reports problems but never modifies data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from kernel.clock import parse_iso
from kernel.errors import GuardedReadError
from kernel.guarded_read import read_guarded
from spec_kitty_events import normalize_event_id

from .models import Lane
from .transitions import CANONICAL_LANES, resolve_lane_alias
from .wp_state import wp_state_for


class StatusValidationReadError(GuardedReadError, RuntimeError):
    """Raised when ``status.json`` exists but cannot be decoded while
    checking materialization drift.

    Mission cli-error-surface-seam WP07/#4746: pre-fix,
    :func:`validate_materialization_drift`'s ``status_path.read_text()`` +
    ``json.loads()`` pair was fully unguarded, so non-UTF-8 bytes or
    malformed JSON surfaced as a raw traceback through
    ``spec-kitty agent status validate``. Only reached once
    :func:`_validate_materialization_files` has confirmed BOTH
    ``status.json`` and ``status.events.jsonl`` exist (D5 -- the
    missing-file findings above stay outside this guard).
    """



def _edge_is_legal(from_lane: str, to_lane: str) -> bool:
    """Decide edge legality via the FSM — the sole edge authority (I1).

    ``genesis`` (the created-but-unseeded seed source) is a full state in the
    FSM, so it routes through ``wp_state_for(from).may_transition_to(to)`` like
    every other lane. No ``(from, to)`` table or derived edge set is consulted
    as a gate — including for genesis (#1775 review M1: the previous
    ``_GENESIS_OUTBOUND`` literal was a parallel authority that could drift from
    ``GenesisState.allowed_targets()``).
    """
    resolved_from = resolve_lane_alias(from_lane)
    resolved_to = resolve_lane_alias(to_lane)
    try:
        source = wp_state_for(Lane(resolved_from))
        target = Lane(resolved_to)
    except ValueError:
        return False
    return source.may_transition_to(target)


@dataclass
class ValidationResult:
    """Aggregate result of all validation checks."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    phase_source: str = ""

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0


def validate_event_schema(event: dict) -> list[str]:
    """Validate a single event dict against the StatusEvent schema.

    Checks:
    - All required fields present: event_id, mission_slug, wp_id,
      from_lane, to_lane, at, actor, force, execution_mode
    - event_id is valid event ID (ULID Crockford base32, or UUID)
    - from_lane and to_lane are canonical lane values (never aliases)
    - at is valid ISO 8601 timestamp
    - force is boolean
    - execution_mode is "worktree" or "direct_repo"
    - If force=True, reason must be non-empty string
    - If from_lane=for_review and to_lane=in_progress, review_ref must be present

    Extra unknown fields are NOT flagged (forward-compatible).
    """
    findings: list[str] = []
    required_fields = [
        "event_id",
        "wp_id",
        "from_lane",
        "to_lane",
        "at",
        "actor",
        "force",
        "execution_mode",
    ]
    for f in required_fields:
        if f not in event:
            findings.append(f"Missing required field: {f}")

    # mission_slug (canonical) or feature_slug (legacy) must be present
    if "mission_slug" not in event and "feature_slug" not in event:
        findings.append("Missing required field: mission_slug (or legacy mission_slug)")

    # ULID format check
    event_id = event.get("event_id", "")
    if event_id and not _is_valid_event_id(str(event_id)):
        findings.append(f"Invalid event ID format: {event_id}")

    # Canonical lane check (aliases like "doing" are NOT canonical).
    # FR-015: ``genesis`` is a valid ``from_lane`` (the non-display seed source)
    # but is NEVER a valid ``to_lane`` and never a current/display lane.
    canonical_set = set(CANONICAL_LANES)
    from_val = event.get("from_lane")
    if from_val is not None and from_val not in canonical_set and from_val != Lane.GENESIS.value:
        findings.append(f"from_lane is not canonical: {from_val}")
    to_val = event.get("to_lane")
    if to_val is not None and to_val not in canonical_set:
        # genesis is explicitly non-canonical as a to_lane (no special-casing).
        findings.append(f"to_lane is not canonical: {to_val}")

    # ISO 8601 timestamp check
    at_val = event.get("at")
    if at_val is not None and not _is_valid_iso8601(str(at_val)):
        findings.append(f"Event {event_id}: invalid ISO 8601 timestamp: {at_val}")

    # force must be boolean
    force_val = event.get("force")
    if force_val is not None and not isinstance(force_val, bool):
        findings.append(f"Event {event_id}: force must be boolean, got {type(force_val).__name__}")

    # execution_mode check
    exec_mode = event.get("execution_mode")
    if exec_mode is not None and exec_mode not in ("worktree", "direct_repo"):
        findings.append(f"Event {event_id}: execution_mode must be 'worktree' or 'direct_repo', got '{exec_mode}'")

    # Force audit check: force=true requires reason
    if event.get("force") is True and not event.get("reason"):
        findings.append(f"Event {event_id}: force=true without reason")

    # Review ref check: for_review -> in_progress requires review_ref
    if event.get("from_lane") == Lane.FOR_REVIEW and event.get("to_lane") == Lane.IN_PROGRESS and not event.get("review_ref"):
        findings.append(f"Event {event_id}: for_review->in_progress without review_ref")

    return findings


def validate_transition_legality(events: list[dict]) -> list[str]:
    """Replay events in order and check each transition is legal.

    Edge legality is decided by the FSM (``wp_state_for(from).may_transition_to``)
    via :func:`_edge_is_legal` — the sole edge authority (I1). ``genesis`` is
    accepted as a seed ``from_lane`` (FR-015).
    Force transitions are always legal (skipped).
    Events are sorted by (at, event_id) before checking.

    Missing from_lane or to_lane is skipped (caught by schema validator).
    """
    findings: list[str] = []

    # Sort by (at, event_id) to ensure correct replay order
    sorted_events = sorted(events, key=lambda e: (e.get("at", ""), e.get("event_id", "")))

    for event in sorted_events:
        from_lane = event.get("from_lane")
        to_lane = event.get("to_lane")
        event_id = event.get("event_id", "unknown")
        force = event.get("force", False)

        # Skip events with missing lane fields (schema validator catches these)
        if from_lane is None or to_lane is None:
            continue

        if force:
            # Forced transitions are legal but noteworthy
            continue

        if not _edge_is_legal(str(from_lane), str(to_lane)):
            findings.append(f"Event {event_id}: illegal transition {from_lane} -> {to_lane}")

    return findings


def validate_done_evidence(events: list[dict]) -> list[str]:
    """Check all done-transitions have evidence or force flag.

    Events not transitioning to done are skipped.
    Force-flagged done transitions bypass the evidence requirement.
    """
    findings: list[str] = []

    for event in events:
        if event.get("to_lane") != Lane.DONE:
            continue

        event_id = event.get("event_id", "unknown")
        force = event.get("force", False)

        if force:
            continue  # Forced done transitions bypass evidence requirement

        evidence = event.get("evidence")
        if not evidence:
            findings.append(f"Event {event_id}: done without evidence (not forced)")
            continue

        # Check evidence structure
        if not isinstance(evidence, dict):
            findings.append(f"Event {event_id}: done evidence is not a dict")
            continue

        review = evidence.get("review")
        if not review:
            findings.append(f"Event {event_id}: done evidence missing review section")
        elif not isinstance(review, dict):
            findings.append(f"Event {event_id}: done evidence review is not a dict")
        else:
            if not review.get("reviewer"):
                findings.append(f"Event {event_id}: done evidence missing reviewer identity")
            if not review.get("verdict"):
                findings.append(f"Event {event_id}: done evidence missing verdict")
            if not review.get("reference"):
                findings.append(f"Event {event_id}: done evidence missing approval reference")

    return findings


def _validate_materialization_files(status_path: Path, events_path: Path) -> list[str] | None:
    """Return early materialization file findings, or None when both files exist."""
    if not events_path.exists():
        if status_path.exists():
            return ["status.json exists but status.events.jsonl is missing"]
        return []

    if not status_path.exists():
        return ["status.events.jsonl exists but status.json is missing (run 'spec-kitty agent status materialize' to generate)"]

    return None


def validate_materialization_drift(feature_dir: Path) -> list[str]:
    """Compare status.json on disk vs reducer output from the event log.

    Returns findings describing any drift detected. An empty list means
    no drift.
    """
    from .reducer import SNAPSHOT_FILENAME, materialize_snapshot
    from .store import EVENTS_FILENAME

    findings: list[str] = []

    status_path = feature_dir / SNAPSHOT_FILENAME
    events_path = feature_dir / EVENTS_FILENAME

    file_findings = _validate_materialization_files(status_path, events_path)
    if file_findings is not None:
        return file_findings

    # Read on-disk snapshot
    disk_data = read_guarded(
        status_path,
        json.loads,
        errors=(json.JSONDecodeError,),
        error_cls=StatusValidationReadError,
    )

    # Compute expected snapshot from all compatible event families.
    expected_snapshot = materialize_snapshot(feature_dir)
    expected_data = expected_snapshot.to_dict()

    # Compare work_packages and summary (skip materialized_at which is timestamp)
    disk_wps = disk_data.get("work_packages", {})
    expected_wps = expected_snapshot.work_packages

    if disk_wps != expected_wps:
        # Find specific differences
        all_wp_ids = set(disk_wps.keys()) | set(expected_wps.keys())
        for wp_id in sorted(all_wp_ids):
            disk_wp = disk_wps.get(wp_id)
            expected_wp = expected_wps.get(wp_id)

            if disk_wp is None:
                findings.append(f"Materialization drift: {wp_id} missing from status.json (expected lane={expected_wp.get('lane', '?')})")
            elif expected_wp is None:
                findings.append(f"Materialization drift: {wp_id} in status.json but not in reducer output")
            elif disk_wp.get("lane") != expected_wp.get("lane"):
                findings.append(f"Materialization drift: {wp_id} lane={disk_wp.get('lane')} in status.json but reducer says lane={expected_wp.get('lane')}")
            elif disk_wp != expected_wp:
                findings.append(f"Materialization drift: {wp_id} state differs between status.json and reducer output")

    if disk_data.get("retrospective") != expected_data.get("retrospective"):
        findings.append("Materialization drift: retrospective snapshot differs between status.json and reducer output")

    # Also check event count and last_event_id
    if disk_data.get("event_count") != expected_snapshot.event_count:
        findings.append(f"Materialization drift: event_count={disk_data.get('event_count')} in status.json but reducer counted {expected_snapshot.event_count}")

    if disk_data.get("last_event_id") != expected_snapshot.last_event_id:
        findings.append("Materialization drift: last_event_id mismatch between status.json and reducer output")

    return findings


def validate_derived_views(
    feature_dir: Path,
    snapshot_wps: dict,
    phase: int,
) -> list[str]:
    """No-op stub: frontmatter lane drift validation has been removed.

    The event log is now the sole authority for WP lane state. Frontmatter
    no longer carries mutable lane fields, so there is nothing to compare
    against the canonical snapshot.

    Args:
        feature_dir: Path to the feature directory (unused).
        snapshot_wps: The work_packages dict from the StatusSnapshot (unused).
        phase: Current status phase (unused).

    Returns:
        Always returns an empty list (no drift findings possible).
    """
    return []


def _is_valid_event_id(value: str) -> bool:
    """Check if a string is a valid event ID (ULID or UUID)."""
    try:
        normalize_event_id(value)
        return True
    except (ValueError, TypeError):
        return False


def _is_valid_iso8601(value: str) -> bool:
    """Check if a string looks like a valid ISO 8601 timestamp.

    Accepts common formats: YYYY-MM-DDTHH:MM:SSZ, YYYY-MM-DDTHH:MM:SS+00:00,
    and the output of datetime.isoformat().
    """
    try:
        # Python 3.11+ datetime.fromisoformat handles Z suffix
        parse_iso(value.replace("Z", "+00:00"))
        return True
    except (ValueError, AttributeError):
        return False
