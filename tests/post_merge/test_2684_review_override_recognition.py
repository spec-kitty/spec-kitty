"""#2684 / FR-009, WP09: event-sourced review-artifact override
recognition — both halves as a matched pair.

Formerly a red-first ``@pytest.mark.regression`` reproduction; relocated here
and un-marked (landing fold: make ``@pytest.mark.regression`` mean exactly
one thing) once the fix landed and this module started passing. #2684 is
fixed — this is now a permanent guard for the override-recognition
correctness property, not a red-first pin.

The ``review_artifact_override_*`` review-cycle state is evicted from artifact
frontmatter into the event log's ``review`` snapshot slot as a *matched
write+read pair*. The correctness property this regression pins: an
event-sourced complete approval override on a rejected latest review must NOT
falsely block merge — the terminal-lane consistency gate honors the
event-sourced override exactly as it honored the legacy frontmatter one (#1924
preserved) — while a genuinely-unresolved rejection (no override) and an
*incomplete* override (missing any of ``at``/``actor``/``wp_id``/``reason``)
still block.

Two-sided proof-of-drive:
  * complete event-sourced override → gate does NOT fire (merge not blocked),
    and the resolution comes from the ``review`` snapshot slot, NOT an
    artifact-frontmatter read (the artifact carries no override frontmatter);
  * no override anywhere → gate DOES fire (merge blocked);
  * incomplete override → gate DOES fire (partial override never honored).

Also asserts the write half (T033): ``_persist_review_artifact_override`` emits
the override as an event and leaves the artifact file byte-unchanged (no
``review_artifact_override_*`` frontmatter written, no coord mirror).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.cli.commands.agent.tasks_materialization import (
    _persist_review_artifact_override,
)
from specify_cli.post_merge.review_artifact_consistency import (
    REJECTED_REVIEW_ARTIFACT_CONFLICT,
    find_rejected_review_artifact_conflicts,
    review_artifact_finding_diagnostic,
)
from specify_cli.review.artifacts import ReviewCycleArtifact
from specify_cli.status import materialize
from specify_cli.status.emit import emit_inner_state_changed
from specify_cli.status.models import Lane, ReviewOverride, ReviewResult, StatusEvent, WPInnerStateDelta
from specify_cli.status.store import append_event

pytestmark = [pytest.mark.integration]

_MISSION_SLUG = "wp-runtime-state-eviction-01KXWN13"
_MISSION_ID = "01KXWN13EVICTION00000000000"
_WP_ID = "WP01"
_WP_SLUG = "WP01-regression-harness"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_feature_dir(root: Path) -> Path:
    """Create a minimal mission feature_dir named after the mission slug.

    ``_persist_review_artifact_override`` derives the emit's feature_dir and
    mission_slug from the artifact path (stored topology, never ``Path.cwd()``),
    so the directory name MUST equal the mission slug.
    """
    feature_dir = root / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta = {"mission_id": _MISSION_ID, "mission_slug": _MISSION_SLUG}
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return feature_dir


def _append_approved_event(
    feature_dir: Path, event_id: str, *, review_result: ReviewResult | None = None
) -> None:
    """Put ``_WP_ID`` in the terminal ``approved`` lane via a transition event.

    ``review_result`` (WP05, verdict-seam-write-unification-01KZ9Q35,
    additive/backward-compatible): the merge gate
    (``find_rejected_review_artifact_conflicts``) is now pure-event (FR-013)
    -- callers that need the gate to see a CURRENT rejection (so an
    override/negative-control scenario has something genuine to
    clear/block) must seed it here, not merely write the on-disk artifact.
    """
    event = StatusEvent(
        event_id=event_id,
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        wp_id=_WP_ID,
        from_lane=Lane.FOR_REVIEW,
        to_lane=Lane.APPROVED,
        at="2026-07-19T12:00:00Z",
        actor="operator",
        force=False,
        execution_mode="worktree",
        reason="approved for merge",
        review_result=review_result,
    )
    append_event(feature_dir, event)


def _write_rejected_artifact(feature_dir: Path) -> Path:
    """Write a ``verdict: rejected`` artifact with NO override frontmatter."""
    artifact = ReviewCycleArtifact(
        cycle_number=1,
        wp_id=_WP_ID,
        mission_slug=_MISSION_SLUG,
        reviewer_agent="reviewer-renata",
        reviewed_at="2026-07-19T11:00:00+00:00",
        body="# Review\n\nVerdict: rejected — changes needed.\n",
    )
    artifact_dir = feature_dir / "tasks" / _WP_SLUG
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / "review-cycle-1.md"
    artifact.write(path)
    return path


# ---------------------------------------------------------------------------
# Positive: event-sourced complete override → gate does NOT block
# ---------------------------------------------------------------------------


def test_event_sourced_complete_override_does_not_block_merge(tmp_path: Path) -> None:
    """A complete override in the ``review`` snapshot slot clears the merge gate.

    The rejected artifact carries NO override frontmatter, so if the gate clears
    the recognition MUST have come from the reduced snapshot slot — proving the
    read half resolves the event-sourced override, not the frontmatter parse.
    """
    feature_dir = _make_feature_dir(tmp_path)
    _append_approved_event(
        feature_dir, "01KXWN13WP09REGRESSION0001",
        review_result=ReviewResult(
            reviewer="reviewer-renata", verdict="changes_requested", reference="x"
        ),
    )
    artifact_path = _write_rejected_artifact(feature_dir)

    before_bytes = artifact_path.read_bytes()

    # Write half (T033): event-source the override.
    _persist_review_artifact_override(
        artifact_path,
        repo_root=tmp_path,
        wp_id=_WP_ID,
        actor="operator",
        reason="Arbiter override: changes accepted despite review rejection.",
    )

    # (a) Artifact file is byte-unchanged — no frontmatter stamp, no coord mirror.
    assert artifact_path.read_bytes() == before_bytes, (
        "The write half must NOT stamp review_artifact_override_* frontmatter"
    )
    assert ReviewCycleArtifact.from_file(artifact_path).override_actor is None, (
        "Artifact frontmatter must carry no override — recognition is snapshot-only"
    )

    # (b) The reduced ``review`` snapshot slot carries the override.
    snapshot = materialize(feature_dir)
    review_slot = snapshot.work_packages[_WP_ID].get("review")
    assert review_slot is not None, "review snapshot slot must carry the override"
    assert ReviewOverride.from_dict(review_slot).complete

    # (c) Read half + merge gate: the override is honored — gate does NOT fire.
    findings = find_rejected_review_artifact_conflicts(feature_dir, [_WP_ID])
    assert findings == [], (
        f"Event-sourced complete override must clear the gate, got: {findings}"
    )


# ---------------------------------------------------------------------------
# Negative control: no override → gate DOES block
# ---------------------------------------------------------------------------


def test_rejected_without_override_still_blocks_merge(tmp_path: Path) -> None:
    """A genuinely-unresolved rejection (no override) still blocks merge."""
    feature_dir = _make_feature_dir(tmp_path)
    _append_approved_event(
        feature_dir, "01KXWN13WP09REGRESSION0002",
        review_result=ReviewResult(
            reviewer="reviewer-renata", verdict="changes_requested", reference="x"
        ),
    )
    _write_rejected_artifact(feature_dir)  # no override emitted anywhere

    findings = find_rejected_review_artifact_conflicts(feature_dir, [_WP_ID])

    assert findings, "Genuine rejection with no override must block merge"
    assert findings[0].wp_id == _WP_ID
    # WP05 (verdict-seam-write-unification-01KZ9Q35, FR-013): the pure-event
    # gate reports the event-domain verdict value, not the artifact-domain
    # one -- "changes_requested", never "rejected".
    assert getattr(findings[0], "verdict", None) == "changes_requested"
    diagnostic = review_artifact_finding_diagnostic(findings[0])
    assert diagnostic["diagnostic_code"] == REJECTED_REVIEW_ARTIFACT_CONFLICT


# ---------------------------------------------------------------------------
# Incomplete override → gate DOES block (partial never honored)
# ---------------------------------------------------------------------------


def test_incomplete_event_sourced_override_still_blocks_merge(tmp_path: Path) -> None:
    """An override missing any of the four fields is never honored (still blocks).

    ``ReviewOverride.complete`` is all-four-present, mirroring the legacy
    ``has_complete_override`` predicate.
    """
    feature_dir = _make_feature_dir(tmp_path)
    _append_approved_event(
        feature_dir, "01KXWN13WP09REGRESSION0003",
        review_result=ReviewResult(
            reviewer="reviewer-renata", verdict="changes_requested", reference="x"
        ),
    )
    _write_rejected_artifact(feature_dir)

    # Emit an override with a blank ``reason`` — incomplete.
    emit_inner_state_changed(
        feature_dir,
        _WP_ID,
        WPInnerStateDelta(
            review=ReviewOverride(
                at="2026-07-19T12:05:00Z",
                actor="operator",
                wp_id=_WP_ID,
                reason="",
            )
        ),
        actor="operator",
        mission_slug=_MISSION_SLUG,
        repo_root=tmp_path,
    )

    review_slot = materialize(feature_dir).work_packages[_WP_ID].get("review")
    assert review_slot is not None
    assert not ReviewOverride.from_dict(review_slot).complete, (
        "Override with a blank field must be incomplete"
    )

    findings = find_rejected_review_artifact_conflicts(feature_dir, [_WP_ID])
    assert findings, "Incomplete override must NOT be honored — merge still blocked"
    assert findings[0].wp_id == _WP_ID
