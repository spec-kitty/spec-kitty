"""WP06 review artifact consistency gate tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from specify_cli.cli.commands.consolidate import _enforce_review_artifact_consistency
from specify_cli.post_merge.review_artifact_consistency import (
    _event_sourced_gate_verdict,
    find_rejected_review_artifact_conflicts,
    format_review_artifact_conflict,
    review_artifact_conflict_diagnostic,
)
from specify_cli.review.artifacts import ReviewCycleArtifact
from specify_cli.status.models import Lane, ReviewResult, StatusEvent
from specify_cli.status.store import append_event
from tests.reliability.fixtures import (
    WorkPackageSpec,
    append_status_event,
    create_mission_fixture,
    write_work_package,
)

pytestmark = pytest.mark.fast


def _write_review_artifact(
    artifact_dir: Path,
    *,
    cycle_number: int,
    verdict: str,
) -> Path:
    artifact = ReviewCycleArtifact(
        cycle_number=cycle_number,
        wp_id="WP01",
        mission_slug="release-320-workflow-reliability-01KQKV85",
        reviewer_agent="reviewer-renata",
        reviewed_at="2026-05-03T12:00:00+00:00",
        body=f"# Review\n\nVerdict: {verdict}\n",
    )
    path = artifact_dir / f"review-cycle-{cycle_number}.md"
    artifact.write(path)
    return path


def _write_malformed_review_artifact(
    artifact_dir: Path,
    *,
    cycle_number: int = 1,
) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / f"review-cycle-{cycle_number}.md"
    path.write_text(
        "---\n"
        "affected_files:\n"
        "  - src/foo.py\n"
        "cycle_number: 1\n"
        "mission_slug: release-320-workflow-reliability-01KQKV85\n"
        "reviewed_at: '2026-05-03T12:00:00+00:00'\n"
        "reviewer_agent: reviewer-renata\n"
        "verdict: approved\n"
        "wp_id: WP01\n"
        "---\n"
        "\n"
        "# Review\n",
        encoding="utf-8",
    )
    return path


def test_latest_rejected_review_artifact_conflicts_with_approved_wp(
    tmp_path: Path,
) -> None:
    """WP05 (verdict-seam-write-unification-01KZ9Q35, FR-013) pure-event
    repoint: the gate now consults ONLY the event-sourced ``review_result``
    slot -- the on-disk artifact below is written only as realistic
    surrounding state, never read by this gate for its verdict."""
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_status_event(
        mission,
        from_lane=Lane.FOR_REVIEW,
        to_lane=Lane.APPROVED,
        event_id="01KQKV85APPROVED000000001",
        review_result=ReviewResult(
            reviewer="reviewer-renata",
            verdict="changes_requested",
            reference="review-cycle://release-320-workflow-reliability-01KQKV85/WP01/review-cycle-2.md",
        ),
    )
    artifact_dir = mission.tasks_dir / "WP01-regression-harness"
    _write_review_artifact(artifact_dir, cycle_number=2, verdict="rejected")

    findings = find_rejected_review_artifact_conflicts(mission.mission_dir)

    assert len(findings) == 1
    assert findings[0].wp_id == "WP01"
    assert findings[0].lane == "approved"
    assert findings[0].artifact_path is None
    diagnostic = review_artifact_conflict_diagnostic(
        findings[0],
        repo_root=mission.repo_root,
    )
    assert diagnostic["diagnostic_code"] == "REJECTED_REVIEW_ARTIFACT_CONFLICT"
    assert diagnostic["branch_or_work_package"] == "WP01"
    assert (
        diagnostic["violated_invariant"]
        == "terminal_wp_latest_review_artifact_must_not_be_rejected"
    )
    assert diagnostic["latest_review_cycle_path"] is None
    assert diagnostic["latest_review_cycle_verdict"] == "changes_requested"
    assert diagnostic["remediation"]


def test_find_conflicts_does_not_materialize_status_json(
    tmp_path: Path,
) -> None:
    """#2934: the merge-readiness check must not write ``status.json``.

    ``find_rejected_review_artifact_conflicts`` is a gate — it reads state to
    decide whether a rejected review blocks merge; it must not persist anything.
    It previously reduced via ``materialize`` (which writes ``status.json`` as a
    side effect). On a mission whose event log is empty/absent that orphaned a
    derived ``status.json`` with no backing ``status.events.jsonl`` — the invalid
    state ``validate`` flags — which the merge then committed alone. Reducing via
    the read-only ``materialize_snapshot`` removes the write while returning the
    identical snapshot.
    """
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_status_event(
        mission,
        from_lane=Lane.FOR_REVIEW,
        to_lane=Lane.APPROVED,
        event_id="01KQKV85APPROVED000000001",
    )
    # Precondition: the fixture wrote only the event log, never status.json.
    assert not mission.status_snapshot_path.exists()

    findings = find_rejected_review_artifact_conflicts(mission.mission_dir)

    # Correctness preserved: no rejected review artifact → no findings.
    assert findings == []
    # The gate reads; it does not persist. No orphan status.json.
    assert not mission.status_snapshot_path.exists(), (
        "find_rejected_review_artifact_conflicts must not materialize "
        "status.json — a merge-readiness check reads, it does not persist (#2934)."
    )


def test_find_conflicts_does_not_orphan_snapshot_when_event_log_absent(
    tmp_path: Path,
) -> None:
    """#2934: an absent event log must remain absent without an orphan snapshot."""
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="planned"))

    assert not mission.status_events_path.exists()
    assert not mission.status_snapshot_path.exists()

    findings = find_rejected_review_artifact_conflicts(mission.mission_dir)

    assert findings == []
    assert not mission.status_events_path.exists()
    assert not mission.status_snapshot_path.exists(), (
        "an absent event log must not gain an orphan status.json during readiness checks"
    )


def test_latest_rejected_review_artifact_conflicts_with_done_wp(
    tmp_path: Path,
) -> None:
    """WP05 pure-event repoint: the event-sourced verdict blocks a ``done``
    WP too (cycle_number always 0 -- no artifact is resolved by this gate
    anymore); the on-disk artifacts are realistic surrounding state only."""
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="done"))
    append_status_event(
        mission,
        from_lane=Lane.APPROVED,
        to_lane=Lane.DONE,
        event_id="01KQKV85DONE00000000001",
        review_result=ReviewResult(reviewer="reviewer-renata", verdict="changes_requested", reference="x"),
    )
    artifact_dir = mission.tasks_dir / "WP01-regression-harness"
    _write_review_artifact(artifact_dir, cycle_number=1, verdict="approved")
    _write_review_artifact(artifact_dir, cycle_number=2, verdict="rejected")

    findings = find_rejected_review_artifact_conflicts(mission.mission_dir)

    assert len(findings) == 1
    assert findings[0].lane == "done"
    assert findings[0].verdict == "changes_requested"


def test_later_approved_review_artifact_clears_rejected_conflict(
    tmp_path: Path,
) -> None:
    """WP05 pure-event repoint: an event-sourced ``approved`` verdict clears
    the gate even though a stray ``.md`` still reads ``rejected``."""
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="done"))
    append_status_event(
        mission,
        from_lane=Lane.APPROVED,
        to_lane=Lane.DONE,
        event_id="01KQKV85DONE00000000001",
        review_result=ReviewResult(reviewer="reviewer-renata", verdict="approved", reference="x"),
    )
    artifact_dir = mission.tasks_dir / "WP01-regression-harness"
    _write_review_artifact(artifact_dir, cycle_number=1, verdict="rejected")
    _write_review_artifact(artifact_dir, cycle_number=2, verdict="approved")

    assert find_rejected_review_artifact_conflicts(mission.mission_dir) == []


def test_shipped_writer_approval_after_rejection_clears_merge_gate(
    tmp_path: Path,
) -> None:
    """WP01 T007: integration test through the REAL shipped writer.

    Reject a WP (cycle 1) then approve it (cycle 2, ``verdict: approved``)
    using ``create_rejected_review_cycle`` itself — not the ``_write_review_artifact``
    test helper — then confirm the merge gate reports no conflict for that WP.
    Closes the loop from writer (WP01) to gate (this WP06 module), per
    spec.md User Story 1 Acceptance Scenario 2.
    """
    from specify_cli.review.cycle import create_rejected_review_cycle

    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="done"))
    append_status_event(
        mission,
        from_lane=Lane.APPROVED,
        to_lane=Lane.DONE,
        event_id="01KQKV85DONE00000000001",
    )

    rejection_feedback = tmp_path / "rejection-feedback.md"
    rejection_feedback.write_text("**Issue**: Missing regression test.\n", encoding="utf-8")
    rejected = create_rejected_review_cycle(
        main_repo_root=mission.repo_root,
        mission_slug=mission.mission_slug,
        wp_id="WP01",
        wp_slug="WP01-regression-harness",
        feedback_source=rejection_feedback,
        reviewer_agent="reviewer-renata",
    )
    assert rejected.review_result.verdict == "changes_requested"

    approval_feedback = tmp_path / "approval-feedback.md"
    approval_feedback.write_text(
        "Approved by reviewer-renata: the missing test was added.\n", encoding="utf-8"
    )
    approved = create_rejected_review_cycle(
        main_repo_root=mission.repo_root,
        mission_slug=mission.mission_slug,
        wp_id="WP01",
        wp_slug="WP01-regression-harness",
        feedback_source=approval_feedback,
        reviewer_agent="reviewer-renata",
        verdict="approved",
    )
    assert approved.review_result.verdict == "approved"
    assert approved.artifact.cycle_number == 2

    assert find_rejected_review_artifact_conflicts(mission.mission_dir) == []


def test_shipped_writer_genuine_rejection_still_blocks_merge_gate(
    tmp_path: Path,
) -> None:
    """Negative control for the test above: no regression to the existing,
    correct blocking behavior when the CURRENT event-sourced verdict genuinely
    IS a rejection (WP05 pure-event repoint: the real writer's ``.md`` alone
    no longer blocks -- the event-sourced ``review_result`` this WP's
    production caller, ``tasks_verdict_persistence.py``, threads onto the
    SAME status-transition event is what the gate now reads)."""
    from specify_cli.review.cycle import create_rejected_review_cycle

    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="done"))

    rejection_feedback = tmp_path / "rejection-feedback.md"
    rejection_feedback.write_text("**Issue**: Missing regression test.\n", encoding="utf-8")
    rejected = create_rejected_review_cycle(
        main_repo_root=mission.repo_root,
        mission_slug=mission.mission_slug,
        wp_id="WP01",
        wp_slug="WP01-regression-harness",
        feedback_source=rejection_feedback,
        reviewer_agent="reviewer-renata",
    )
    append_status_event(
        mission,
        from_lane=Lane.APPROVED,
        to_lane=Lane.DONE,
        event_id="01KQKV85DONE00000000001",
        review_result=ReviewResult(
            reviewer="reviewer-renata", verdict="changes_requested", reference=rejected.pointer
        ),
    )

    findings = find_rejected_review_artifact_conflicts(mission.mission_dir)

    assert len(findings) == 1
    assert findings[0].wp_id == "WP01"
    assert findings[0].verdict == "changes_requested"


def test_merge_review_artifact_consistency_gate_blocks_done_signoff(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="done"))
    append_status_event(
        mission,
        from_lane=Lane.APPROVED,
        to_lane=Lane.DONE,
        event_id="01KQKV85DONE00000000001",
        review_result=ReviewResult(reviewer="reviewer-renata", verdict="changes_requested", reference="x"),
    )
    artifact_dir = mission.tasks_dir / "WP01-regression-harness"
    _write_review_artifact(artifact_dir, cycle_number=1, verdict="rejected")

    with pytest.raises(typer.Exit) as exc_info:
        _enforce_review_artifact_consistency(
            repo_root=mission.repo_root,
            feature_dir=mission.mission_dir,
            mission_slug=mission.mission_slug,
            wp_ids=["WP01"],
        )

    assert exc_info.value.exit_code == 1
    output = capsys.readouterr().out
    assert "diagnostic_code: REJECTED_REVIEW_ARTIFACT_CONFLICT" in output
    assert "branch_or_work_package: WP01" in output
    assert (
        "violated_invariant: "
        "terminal_wp_latest_review_artifact_must_not_be_rejected"
    ) in output
    assert "latest_review_cycle_verdict: changes_requested" in output
    assert "remediation:" in output


def test_malformed_review_artifact_frontmatter_becomes_schema_diagnostic(
    tmp_path: Path,
) -> None:
    """WP05 (verdict-seam-write-unification-01KZ9Q35, FR-013) pure-event
    repoint: the gate no longer parses ``review-cycle-N.md`` frontmatter AT
    ALL, so a malformed on-disk artifact is now SILENTLY IRRELEVANT to it --
    zero findings, even though the artifact itself is garbage and the WP is
    in a terminal lane. The former ``REVIEW_ARTIFACT_SCHEMA_INVALID`` leg
    this test originally exercised is retired (SC-002: no artifact-frontmatter
    reads survive on this reader path)."""
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_status_event(
        mission,
        from_lane=Lane.FOR_REVIEW,
        to_lane=Lane.APPROVED,
        event_id="01KQKV85APPROVED000000002",
    )
    artifact_dir = mission.tasks_dir / "WP01-regression-harness"
    _write_malformed_review_artifact(artifact_dir)

    findings = find_rejected_review_artifact_conflicts(
        mission.mission_dir,
        wp_ids=["WP01"],
    )

    assert findings == [], (
        "a malformed on-disk review-cycle artifact must not produce any "
        "finding post-repoint -- this gate no longer reads it at all"
    )


def test_invalid_top_level_review_artifact_field_becomes_schema_diagnostic(
    tmp_path: Path,
) -> None:
    """WP05 pure-event repoint, G2 fail-closed proof: a DAMAGED event-sourced
    ``review_result`` record (present but missing required fields) does not
    fabricate a blocking finding either -- the former on-disk
    ``REVIEW_ARTIFACT_SCHEMA_INVALID`` diagnostic this test originally
    exercised is retired; this is the event-authority successor using the
    same "malformed input must not crash or falsely block" intent."""
    from specify_cli.status.models import StatusSnapshot

    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    damaged_snapshot = StatusSnapshot(
        mission_slug=mission.mission_slug,
        materialized_at="2026-05-03T12:00:00+00:00",
        event_count=1,
        last_event_id="01KQKV85APPROVED000000003",
        work_packages={
            "WP01": {
                "lane": "approved",
                # Present (a Mapping) but missing required ReviewResult
                # fields -- the genuine "damaged" shape.
                "review_result": {"reviewer": "reviewer-renata"},
            }
        },
        summary={},
    )

    with patch(
        "specify_cli.post_merge.review_artifact_consistency.materialize_snapshot",
        return_value=damaged_snapshot,
    ):
        findings = find_rejected_review_artifact_conflicts(
            mission.mission_dir,
            wp_ids=["WP01"],
        )

    assert findings == [], (
        "a damaged event-sourced review_result record must not fabricate a "
        "blocking finding (G2 fail-closed, never a crash either)"
    )


def test_merge_review_artifact_consistency_gate_blocks_malformed_artifact(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """WP05 pure-event repoint: a malformed on-disk artifact with NO
    event-sourced opinion does not block ``done`` signoff at all (the
    former schema-diagnostic block is retired; the CLI-level enforce
    function proceeds cleanly through the real ``merge`` surface)."""
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="done"))
    append_status_event(
        mission,
        from_lane=Lane.APPROVED,
        to_lane=Lane.DONE,
        event_id="01KQKV85DONE00000000002",
    )
    artifact_dir = mission.tasks_dir / "WP01-regression-harness"
    _write_malformed_review_artifact(artifact_dir)

    _enforce_review_artifact_consistency(
        repo_root=mission.repo_root,
        feature_dir=mission.mission_dir,
        mission_slug=mission.mission_slug,
        wp_ids=["WP01"],
    )

    output = capsys.readouterr().out
    assert "diagnostic_code" not in output


def test_terminal_wp_event_sourced_changes_requested_blocks_without_artifact(
    tmp_path: Path,
) -> None:
    """Fail-open gap: a terminal WP with NO on-disk review artifact at all must
    still be blocked when the event-sourced ``review_result`` verdict is
    ``changes_requested``.

    Before the fix, ``find_rejected_review_artifact_conflicts`` returned early
    (``if latest_path is None: continue``) the moment no ``review-cycle-*.md``
    file existed for a WP — never consulting ``_event_sourced_gate_verdict`` at
    all. A terminal-lane WP whose event log records a rejection (e.g. a
    ``--force`` exit from ``in_review`` that never wrote frontmatter) therefore
    passed the merge gate for free. This reproduces exactly that shape: WP01 is
    in the terminal ``approved`` lane, no ``review-cycle-*.md`` file exists
    anywhere under its tasks dir, and the reduced snapshot's ``review_result``
    slot carries ``verdict="changes_requested"``.
    """
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_event(
        mission.mission_dir,
        StatusEvent(
            event_id="01KQKV85APPROVEDNOARTIFACT1",
            mission_slug=mission.mission_slug,
            mission_id=mission.mission_id,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.APPROVED,
            at="2026-05-03T12:00:00+00:00",
            actor="operator",
            force=True,
            execution_mode="worktree",
            reason="force-approved despite rejection",
            review_result=ReviewResult(
                reviewer="reviewer-renata",
                verdict="changes_requested",
                reference="feedback://release-320-workflow-reliability-01KQKV85/WP01/1",
            ),
        ),
    )
    artifact_dir = mission.tasks_dir / "WP01-regression-harness"
    assert not artifact_dir.exists() or not list(
        artifact_dir.glob("review-cycle-*.md")
    ), "precondition: no on-disk review artifact must exist for this WP"

    findings = find_rejected_review_artifact_conflicts(mission.mission_dir)

    assert len(findings) == 1, (
        "a terminal WP with an event-sourced changes_requested verdict must "
        f"block merge even with no on-disk artifact, got: {findings}"
    )
    assert findings[0].wp_id == "WP01"
    assert findings[0].lane == "approved"
    assert findings[0].verdict == "changes_requested"
    assert findings[0].artifact_path is None

    message = format_review_artifact_conflict(findings[0], repo_root=mission.repo_root)
    assert "WP01" in message
    assert "changes_requested" in message

    diagnostic = review_artifact_conflict_diagnostic(
        findings[0], repo_root=mission.repo_root
    )
    assert diagnostic["diagnostic_code"] == "REJECTED_REVIEW_ARTIFACT_CONFLICT"
    assert diagnostic["latest_review_cycle_verdict"] == "changes_requested"
    assert diagnostic["latest_review_cycle_path"] is None


def test_terminal_wp_no_artifact_no_event_opinion_is_not_blocked(
    tmp_path: Path,
) -> None:
    """Guard against over-blocking: a terminal WP with NO on-disk artifact and
    NO event-sourced ``review_result`` opinion must NOT be flagged.

    This is the pre-existing, correct behaviour (an un-migrated mission, or a
    WP that never exited ``in_review``) — the fix above must not regress it.
    """
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_status_event(
        mission,
        from_lane=Lane.FOR_REVIEW,
        to_lane=Lane.APPROVED,
        event_id="01KQKV85APPROVEDNOOPINION01",
    )
    artifact_dir = mission.tasks_dir / "WP01-regression-harness"
    assert not artifact_dir.exists() or not list(
        artifact_dir.glob("review-cycle-*.md")
    ), "precondition: no on-disk review artifact must exist for this WP"

    findings = find_rejected_review_artifact_conflicts(mission.mission_dir)

    assert findings == [], (
        "no on-disk artifact and no event-sourced opinion must not block merge, "
        f"got: {findings}"
    )


# ---------------------------------------------------------------------------
# WP02 (verdict-seam-boundary-hardening-01KZG179, T008/T010, NFR-001):
# _event_sourced_gate_verdict now delegates to the facade's
# review_result_from_state instead of re-inlining a ReviewResult.from_dict
# decode. These 5 tests exercise the retired decode's exact case matrix
# DIRECTLY against the function (not only indirectly through
# find_rejected_review_artifact_conflicts above) to prove behavior parity
# with the dedup.
# ---------------------------------------------------------------------------


def test_event_sourced_gate_verdict_absent_slot_returns_none() -> None:
    """Case 1/5: no ``review_result`` key in the reduced state at all."""
    assert _event_sourced_gate_verdict({}) is None


def test_event_sourced_gate_verdict_raw_none_returns_none() -> None:
    """Case 2/5: the slot is present but explicitly ``None`` (a ``--force``
    exit from ``in_review`` that supplied no ``ReviewResult``)."""
    assert _event_sourced_gate_verdict({"review_result": None}) is None


def test_event_sourced_gate_verdict_non_mapping_returns_none() -> None:
    """Case 3/5: the slot is present but not a ``Mapping`` (damaged data)."""
    assert _event_sourced_gate_verdict({"review_result": "not-a-mapping"}) is None


def test_event_sourced_gate_verdict_from_dict_raises_returns_none() -> None:
    """Case 4/5: the slot is a ``Mapping`` missing required ``ReviewResult``
    fields, so the delegated decode fails closed (never a crash)."""
    assert _event_sourced_gate_verdict({"review_result": {"reviewer": "renata"}}) is None


def test_event_sourced_gate_verdict_valid_slot_returns_verdict_string() -> None:
    """Case 5/5: a valid slot yields the recorded verdict as ``str``."""
    state = {
        "review_result": {
            "reviewer": "reviewer-renata",
            "verdict": "changes_requested",
            "reference": "feedback://mission/WP01/1",
        }
    }
    assert _event_sourced_gate_verdict(state) == "changes_requested"
