"""Unit tests for the WP06 (#2058) ``tasks_parsing_validation`` seam.

Covers the issue-matrix approval-blocker logic, the latest review-cycle verdict
extraction, the self-review fallback guard, and — critically — each of the
behaviour-preserving sub-split validators that compose
``_validate_ready_for_review`` (NFR-001). The sub-validators are exercised
directly with injected collaborators so their branches are tested in isolation,
not only through the broad command-level integration tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.cli.commands.agent.tasks_parsing_validation import (
    _VALID_VERDICTS,
    _apply_review_status_flags,
    _apply_wp_review_verdict_flag,
    _check_branch_currency,
    _check_implementation_commit_present,
    _check_kitty_specs_contamination,
    _check_uncommitted_worktree_changes,
    _check_worktree_health,
    _issue_matrix_approval_blocker,
    _resolve_planning_branch_for_lane_guard,
    _self_review_fallback_option_error,
    _validate_research_artifacts,
    _validate_worktree_state,
)
from specify_cli.status.models import Lane, ReviewResult, StatusEvent
from specify_cli.status.reducer import ReviewResultLookup

pytestmark = pytest.mark.fast

_TASKS_PARSING_VALIDATION = "specify_cli.cli.commands.agent.tasks_parsing_validation"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _write_issue_matrix(
    feature_dir: Path,
    verdict: str,
    evidence_ref: str = "tests/test_demo.py",
    issue: str = "#1582",
) -> None:
    (feature_dir / "issue-matrix.md").write_text(
        "\n".join(
            [
                "| issue | verdict | evidence_ref |",
                "| --- | --- | --- |",
                f"| {issue} | {verdict} | {evidence_ref} |",
            ]
        ),
        encoding="utf-8",
    )


def _write_issue_matrix_json(
    feature_dir: Path,
    verdict: str,
    evidence_ref: str = "tests/test_demo.py",
    issue: str = "#1582",
) -> None:
    (feature_dir / "issue-matrix.json").write_text(
        json.dumps({"rows": {issue: {"verdict": verdict, "evidence_ref": evidence_ref}}}),
        encoding="utf-8",
    )


def _write_malformed_issue_matrix(feature_dir: Path) -> None:
    """An issue-matrix.md whose mandatory ``issue`` column is misspelled.

    ``issue_id`` does not normalize to the canonical ``issue`` column (no
    ``COLUMN_ALIASES`` entry), so the validator bails out with zero parsed
    rows and an ``ISSUE_MATRIX_SCHEMA_DRIFT`` diagnostic (FR-007/#2555.5).
    """
    (feature_dir / "issue-matrix.md").write_text(
        "\n".join(
            [
                "| issue_id | verdict | evidence_ref |",
                "| --- | --- | --- |",
                "| #1582 | fixed | tests/test_demo.py |",
            ]
        ),
        encoding="utf-8",
    )




def _make_subproc(returncode: int = 0, stdout: str = "") -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    return m


@dataclass
class _FakeWorkspace:
    """Minimal stand-in: the validator only reads these two attributes."""

    resolution_kind: str
    worktree_path: Path


# ---------------------------------------------------------------------------
# Self-review fallback guard
# ---------------------------------------------------------------------------


def test_self_review_fallback_guard_full_matrix() -> None:
    assert _self_review_fallback_option_error(
        enabled=False, target_lane="approved", force=False,
        intended_reviewer="codex", failure_reason=None,
    ) == "--intended-reviewer/--reviewer-failure-reason require --self-review-fallback."

    assert _self_review_fallback_option_error(
        enabled=False, target_lane="approved", force=False,
        intended_reviewer=None, failure_reason=None,
    ) is None

    assert _self_review_fallback_option_error(
        enabled=True, target_lane="for_review", force=True,
        intended_reviewer="codex", failure_reason="exit 1",
    ) == "--self-review-fallback is only valid when approving or marking done."

    assert _self_review_fallback_option_error(
        enabled=True, target_lane="approved", force=False,
        intended_reviewer="codex", failure_reason="exit 1",
    ) == "--self-review-fallback requires --force so force_count records the independence override."

    assert _self_review_fallback_option_error(
        enabled=True, target_lane="approved", force=True,
        intended_reviewer=" ", failure_reason="exit 1",
    ) == "--self-review-fallback requires --intended-reviewer <agent>."

    assert _self_review_fallback_option_error(
        enabled=True, target_lane="approved", force=True,
        intended_reviewer="codex", failure_reason=" ",
    ) == "--self-review-fallback requires --reviewer-failure-reason <reason>."

    assert _self_review_fallback_option_error(
        enabled=True, target_lane="done", force=True,
        intended_reviewer="codex", failure_reason="exit 1",
    ) is None


# ---------------------------------------------------------------------------
# Issue-matrix approval blocker
# ---------------------------------------------------------------------------


def test_issue_matrix_approval_blocker_requires_resolved_verdicts(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("Fix Priivacy-ai/spec-kitty issue #1582.\n", encoding="utf-8")

    blocker = _issue_matrix_approval_blocker(feature_dir)
    assert blocker is not None
    assert "issue-matrix.json is required" in blocker
    assert "#1582" in blocker

    _write_issue_matrix(feature_dir, "unknown")
    blocker = _issue_matrix_approval_blocker(feature_dir)
    assert blocker is not None
    # #4330: the unknown-verdict row is surfaced with its concrete rule, not
    # reduced to a bare "Unknown: #1582" id list.
    assert "Row for issue '#1582'" in blocker
    assert "verdict 'unknown' is not in the allowed set" in blocker

    _write_issue_matrix(feature_dir, "fixed", issue="#1111")
    blocker = _issue_matrix_approval_blocker(feature_dir)
    assert blocker is not None
    assert "Missing rows: #1582" in blocker

    _write_issue_matrix(feature_dir, "fixed")
    assert _issue_matrix_approval_blocker(feature_dir) is None


def test_issue_matrix_blocker_names_actual_artifact_json_not_hardcoded_md(
    tmp_path: Path,
) -> None:
    """#4330: a JSON-format mission's blocker must name ``issue-matrix.json``.

    The old message hardcoded ``issue-matrix.md`` even though the gate reads
    the structured artifact JSON-first, so an operator was sent hunting for a
    file their mission does not use.
    """
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("Fix Priivacy-ai/spec-kitty issue #1582.\n", encoding="utf-8")

    _write_issue_matrix_json(feature_dir, "unknown")
    blocker = _issue_matrix_approval_blocker(feature_dir)
    assert blocker is not None
    assert "ERROR: issue-matrix.json has unresolved entries" in blocker
    assert "issue-matrix.md" not in blocker


def test_issue_matrix_blocker_names_legacy_md_artifact_when_md_is_the_matrix(
    tmp_path: Path,
) -> None:
    """Back-compat half of #4330: a legacy ``.md``-only mission still names ``.md``."""
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("Fix Priivacy-ai/spec-kitty issue #1582.\n", encoding="utf-8")

    _write_issue_matrix(feature_dir, "unknown")
    blocker = _issue_matrix_approval_blocker(feature_dir)
    assert blocker is not None
    assert "ERROR: issue-matrix.md has unresolved entries" in blocker


def test_issue_matrix_blocker_surfaces_deferred_without_handle_rule(
    tmp_path: Path,
) -> None:
    """#4330: the deferred-with-followup handle rule must be stated in the
    blocker, not left for the operator to find by reading the validator."""
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("Fix Priivacy-ai/spec-kitty issue #1582.\n", encoding="utf-8")

    # Prose-only evidence_ref with no '#NNN' or 'Follow-up:' substring.
    _write_issue_matrix_json(
        feature_dir, "deferred-with-followup", evidence_ref="deferred pending triage"
    )
    blocker = _issue_matrix_approval_blocker(feature_dir)
    assert blocker is not None
    assert "Row for issue '#1582'" in blocker
    assert "'deferred-with-followup'" in blocker
    assert "no follow-up handle" in blocker
    assert "'#NNN' or 'Follow-up:'" in blocker


def test_issue_matrix_missing_file_blocker_names_regenerate_command(tmp_path: Path) -> None:
    """Field report: the missing-file blocker gave no next step, so an
    operator hand-authored a matrix by copying an unrelated mission's file.
    The message must name the actual regenerate command and schema doc."""
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("Fix Priivacy-ai/spec-kitty issue #1582.\n", encoding="utf-8")

    blocker = _issue_matrix_approval_blocker(feature_dir)

    assert blocker is not None
    assert "spec-kitty agent mission finalize-tasks --mission demo" in blocker
    assert "src/specify_cli/cli/commands/review/ERROR_CODES.md" in blocker


def test_issue_matrix_in_mission_passes_approved_blocks_done(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("Fix Priivacy-ai/spec-kitty issue #1582.\n", encoding="utf-8")
    _write_issue_matrix(feature_dir, "in-mission", evidence_ref="WP14 (this mission)")

    assert _issue_matrix_approval_blocker(feature_dir, target_lane=Lane.APPROVED) is None
    assert _issue_matrix_approval_blocker(feature_dir) is None

    blocker = _issue_matrix_approval_blocker(feature_dir, target_lane=Lane.DONE)
    assert blocker is not None
    assert "in-mission" in blocker
    assert "#1582" in blocker

    _write_issue_matrix(feature_dir, "fixed", evidence_ref="commit abc123")
    assert _issue_matrix_approval_blocker(feature_dir, target_lane=Lane.DONE) is None


def test_issue_matrix_approval_blocker_no_spec_returns_none(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    # No spec.md at all → no referenced issues → nothing to block.
    assert _issue_matrix_approval_blocker(feature_dir) is None


def test_issue_matrix_approval_blocker_names_schema_drift_column(tmp_path: Path) -> None:
    """FR-007 (#2555.5), T018(a): a malformed mandatory column names the
    offending/normalized column instead of listing every referenced issue
    as an all-issues "Missing rows" — the header problem is the real cause.
    """
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("Fix Priivacy-ai/spec-kitty issue #1582.\n", encoding="utf-8")
    _write_malformed_issue_matrix(feature_dir)

    blocker = _issue_matrix_approval_blocker(feature_dir)
    assert blocker is not None
    assert "Mandatory column(s) missing: issue" in blocker
    assert "Found columns after normalization" in blocker
    assert "Missing rows" not in blocker


def test_issue_matrix_approval_blocker_keeps_missing_rows_when_parsed(tmp_path: Path) -> None:
    """FR-007 (#2555.5), T018(b) preservation branch: when the header is
    well-formed and rows actually parse, a genuinely row-incomplete matrix
    still emits "Missing rows" for the referenced issue that has no row.
    """
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("Fix Priivacy-ai/spec-kitty issue #1582.\n", encoding="utf-8")
    _write_issue_matrix(feature_dir, "fixed", issue="#1111")

    blocker = _issue_matrix_approval_blocker(feature_dir)
    assert blocker is not None
    assert "Missing rows: #1582" in blocker


def test_issue_matrix_approval_blocker_discovers_reference_only_in_wp_file(
    tmp_path: Path,
) -> None:
    """WP08/T029/T031/FR-004: a ref buried in ``tasks/WP01.md`` alone blocks
    approval exactly like a ``spec.md`` reference would — the approval
    blocker must share the same discovery definition as finalization
    (WP08's ``discover_issue_references``), not a spec.md-only re-scan.
    """
    feature_dir = tmp_path / "kitty-specs" / "demo"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("No issues mentioned here.\n", encoding="utf-8")
    (tasks_dir / "WP01.md").write_text("This WP fixes #8888.\n", encoding="utf-8")

    blocker = _issue_matrix_approval_blocker(feature_dir)

    assert blocker is not None
    assert "#8888" in blocker

    _write_issue_matrix(feature_dir, "fixed", issue="#8888")
    assert _issue_matrix_approval_blocker(feature_dir) is None


def test_issue_matrix_approval_blocker_json_only_mission_not_falsely_blocked(
    tmp_path: Path,
) -> None:
    """WP08/T043 (C-008/B-1): a JSON-only matrix no longer false-blocks approval.

    Before the reader switch, the ``.md``-only ``.exists()`` precheck made a
    greenfield JSON-only mission (B3) hard-fail approval even though
    ``issue-matrix.json`` already carried the resolved row.
    """
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("Fix Priivacy-ai/spec-kitty issue #1582.\n", encoding="utf-8")
    (feature_dir / "issue-matrix.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "rows": {
                    "#1582": {
                        "verdict": "fixed",
                        "evidence_ref": "tests/test_demo.py",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    assert _issue_matrix_approval_blocker(feature_dir) is None


def test_issue_matrix_read_is_coord_authoritative_no_primary_fallback(tmp_path: Path) -> None:
    """coord-commit-integrity SURFACE A #1c: the issue-matrix reader consults ONLY
    the coord/placement ``feature_dir``.

    Flipped from ``..._uses_primary_verdicts_when_coord_copy_stale`` (which pinned
    the now-DELETED ``_primary_issue_matrix_satisfies`` anti-pattern): a filled
    PRIMARY copy must NOT rescue a stale/unfilled COORD copy — a PRIMARY fallback
    for a COORD-partition kind was the split-brain the remediation kills. The
    primary dir is consulted only for ``spec.md`` (a genuine PRIMARY kind).
    """
    coord_dir = tmp_path / "coord" / "kitty-specs" / "demo"
    primary_dir = tmp_path / "primary" / "kitty-specs" / "demo"
    coord_dir.mkdir(parents=True)
    primary_dir.mkdir(parents=True)
    spec_text = "Fix Priivacy-ai/spec-kitty issue #1582.\n"
    (coord_dir / "spec.md").write_text(spec_text, encoding="utf-8")
    (primary_dir / "spec.md").write_text(spec_text, encoding="utf-8")
    _write_issue_matrix(coord_dir, "unknown")  # stale coord copy — authoritative
    _write_issue_matrix(primary_dir, "fixed")  # filled primary copy — MUST be ignored

    # The filled primary copy MUST NOT rescue the stale coord matrix.
    rescued = _issue_matrix_approval_blocker(coord_dir, primary_feature_dir=primary_dir)
    assert rescued is not None
    # #4330: the unknown-verdict row surfaces its concrete rule, not a bare id.
    assert "Row for issue '#1582'" in rescued
    assert "verdict 'unknown' is not in the allowed set" in rescued

    # Without any primary hint the result is identical (coord-authoritative).
    stale_blocker = _issue_matrix_approval_blocker(coord_dir)
    assert stale_blocker is not None
    assert "Row for issue '#1582'" in stale_blocker
    assert "verdict 'unknown' is not in the allowed set" in stale_blocker


# ---------------------------------------------------------------------------
# Review-cycle verdict extraction + status flags
# ---------------------------------------------------------------------------


def test_valid_verdicts_constant() -> None:
    assert set(_VALID_VERDICTS) == {
        "approved",
        "approved_after_orchestrator_fix",
        "arbiter_override",
        "rejected",
    }


# ---------------------------------------------------------------------------
# WP05 (verdict-seam-write-unification-01KZ9Q35, FR-003/FR-004) retired
# ``_get_latest_review_cycle_verdict`` -- the ``review-cycle-N.md``
# frontmatter parser ``_apply_review_status_flags`` used to call. The four
# tests below are REPOINTED, not deleted (a prior mission's NFR-001 node-id
# floor, ``tests/architectural/mission_exit_baseline.txt``, pins their
# names): each now exercises the event-sourced successor
# (``status.event_sourced_review_result``) of what it originally asserted
# about the retired frontmatter function.
# ---------------------------------------------------------------------------


def test_get_latest_review_cycle_verdict_picks_highest(tmp_path: Path) -> None:
    """WP05 repoint: the reducer resolves the MOST RECENT
    ``review_result``-carrying event -- the event-sourced successor of
    "picks the highest-numbered cycle"."""
    from specify_cli.status import event_sourced_review_result
    from specify_cli.status.store import append_event

    append_event(
        tmp_path,
        StatusEvent(
            event_id="01HXYZPICKS0000000000001",
            mission_slug=tmp_path.name,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.IN_PROGRESS,
            at="2026-01-01T00:00:00+00:00",
            actor="reviewer-renata",
            force=False,
            execution_mode="worktree",
            review_result=ReviewResult(reviewer="reviewer-renata", verdict="changes_requested", reference="x"),
        ),
    )
    append_event(
        tmp_path,
        StatusEvent(
            event_id="01HXYZPICKS0000000000002",
            mission_slug=tmp_path.name,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.APPROVED,
            at="2026-01-02T00:00:00+00:00",
            actor="reviewer-renata",
            force=False,
            execution_mode="worktree",
            review_result=ReviewResult(reviewer="reviewer-renata", verdict="approved", reference="y"),
        ),
    )

    lookup = event_sourced_review_result(tmp_path, "WP01")

    assert lookup.slot_present is True
    assert lookup.result is not None
    assert lookup.result.verdict == "approved"


def test_get_latest_review_cycle_verdict_unknown_warns(tmp_path: Path) -> None:
    """WP05 repoint: a damaged ``review_result`` slot is distinguishable
    (``slot_present=True, result=None``) from a genuinely absent one, rather
    than silently collapsing -- the event-sourced successor of "an
    unrecognized verdict value still surfaces, distinctly"."""
    from specify_cli.status import event_sourced_review_result

    with patch(
        "specify_cli.status.reducer.wp_snapshot_state",
        return_value={"lane": "in_progress", "review_result": {"reviewer": "reviewer-renata"}},
    ):
        lookup = event_sourced_review_result(tmp_path, "WP01")

    assert lookup == ReviewResultLookup(slot_present=True, result=None)


def test_get_latest_review_cycle_verdict_missing_frontmatter(tmp_path: Path) -> None:
    """WP05 repoint: ``_apply_wp_review_verdict_flag`` (this module's own
    board-flag helper) marks a damaged event-sourced record distinctly
    (``_damaged_verdict``), never silently as "no verdict" -- the
    event-sourced successor of "an artifact with no frontmatter returns a
    distinguishable damaged marker"."""
    stale_verdicts: list[dict[str, object]] = []
    wp: dict[str, object] = {"id": "WP01"}

    with patch(
        f"{_TASKS_PARSING_VALIDATION}.event_sourced_review_result",
        return_value=ReviewResultLookup(slot_present=True, result=None),
    ):
        _apply_wp_review_verdict_flag(
            wp, wp_id="WP01", feature_dir=tmp_path, stale_verdicts=stale_verdicts
        )

    assert wp["_damaged_verdict"] is True
    assert stale_verdicts and stale_verdicts[0]["damaged"] is True


def _append_review_result_event(
    feature_dir: Path,
    *,
    wp_id: str,
    verdict: str,
    event_id: str = "01HXYZREVIEW00000000000001",
) -> None:
    from specify_cli.status.store import append_event

    append_event(
        feature_dir,
        StatusEvent(
            event_id=event_id,
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.IN_PROGRESS,
            at="2026-01-01T00:00:00+00:00",
            actor="reviewer-renata",
            force=False,
            execution_mode="worktree",
            review_result=ReviewResult(
                reviewer="reviewer-renata", verdict=verdict, reference="review-cycle://demo/WP01/review-cycle-1.md"
            ),
        ),
    )


def test_apply_review_status_flags_stale_and_stalled(tmp_path: Path) -> None:
    # WP05 repoint: the board now resolves the event-sourced verdict
    # (``event_sourced_review_result``), never ``review-cycle-N.md``
    # frontmatter -- feature_dir replaces the old tasks_dir kwarg.
    feature_dir = tmp_path
    _append_review_result_event(feature_dir, wp_id="WP01", verdict="changes_requested")
    approved_wp: dict[str, object] = {"id": "WP01", "lane": Lane.APPROVED, "file": "WP01.md"}

    # In-review WP with an old event → stalled flag.
    in_review_wp: dict[str, object] = {"id": "WP02", "lane": Lane.IN_REVIEW}
    old_event = StatusEvent(
        event_id="01HXYZ",
        mission_slug="demo",
        wp_id="WP02",
        from_lane=Lane.FOR_REVIEW,
        to_lane=Lane.IN_REVIEW,
        at="2000-01-01T00:00:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
    )

    stale, stalled = _apply_review_status_flags(
        [approved_wp, in_review_wp],
        feature_dir=feature_dir,
        events=[old_event],
        stall_threshold_minutes=30,
    )

    assert stale and stale[0]["wp_id"] == "WP01"
    assert approved_wp["_stale_verdict"] is True
    assert stalled and stalled[0]["wp_id"] == "WP02"
    assert "STALLED" in str(in_review_wp["_stall_label"])


# ---------------------------------------------------------------------------
# Sub-split validator: _validate_research_artifacts
# ---------------------------------------------------------------------------


def test_validate_research_artifacts_clean_returns_none(tmp_path: Path) -> None:
    console = MagicMock()
    with patch("subprocess.run", return_value=_make_subproc(0, "")):
        result = _validate_research_artifacts(
            main_repo_root=tmp_path,
            feature_dir=tmp_path / "kitty-specs" / "demo",
            mission_slug="demo",
            wp_id="WP01",
            mission_type="research",
            target_lane="for_review",
            console=console,
        )
    assert result is None


def test_validate_research_artifacts_blocks_research_commit_format(tmp_path: Path) -> None:
    console = MagicMock()
    porcelain = " M kitty-specs/demo/data-model.md\n"
    with (
        patch("subprocess.run", return_value=_make_subproc(0, porcelain)),
        patch(
            "specify_cli.review.dirty_classifier.classify_dirty_paths",
            return_value=(["kitty-specs/demo/data-model.md"], []),
        ),
    ):
        guidance = _validate_research_artifacts(
            main_repo_root=tmp_path,
            feature_dir=tmp_path / "kitty-specs" / "demo",
            mission_slug="demo",
            wp_id="WP01",
            mission_type="research",
            target_lane="for_review",
            console=console,
        )
    assert guidance is not None
    text = "\n".join(guidance)
    assert "Blocking: 1 uncommitted file(s) owned by WP01" in text
    assert 'research(WP01)' in text
    assert "move-task WP01 --to for_review" in text


def test_validate_research_artifacts_benign_only_passes_with_note(tmp_path: Path) -> None:
    console = MagicMock()
    porcelain = " M kitty-specs/demo/other-wp.md\n"
    with (
        patch("subprocess.run", return_value=_make_subproc(0, porcelain)),
        patch(
            "specify_cli.review.dirty_classifier.classify_dirty_paths",
            return_value=([], ["kitty-specs/demo/other-wp.md"]),
        ),
    ):
        result = _validate_research_artifacts(
            main_repo_root=tmp_path,
            feature_dir=tmp_path / "kitty-specs" / "demo",
            mission_slug="demo",
            wp_id="WP01",
            mission_type="software-dev",
            target_lane="for_review",
            console=console,
        )
    assert result is None
    console.print.assert_called_once()
    assert "not owned by WP01" in console.print.call_args.args[0]


# ---------------------------------------------------------------------------
# Sub-split validator: _check_worktree_health
# ---------------------------------------------------------------------------


def test_check_worktree_health_husk_blocks(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()  # no .git marker → husk
    guidance = _check_worktree_health(worktree, "WP01", "for_review")
    assert guidance is not None
    assert guidance  # populated husk message


def test_check_worktree_health_detached_head(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: ../fake\n", encoding="utf-8")
    with (
        patch(
            "specify_cli.workspace.context.verify_workspace_toplevel",
            return_value=None,
        ),
        patch("specify_cli.core.git_ops.get_current_branch", return_value=None),
    ):
        guidance = _check_worktree_health(worktree, "WP01", "approved")
    assert guidance is not None
    assert guidance[0] == "Detached HEAD detected in worktree!"
    assert "move-task WP01 --to approved" in "\n".join(guidance)


def test_check_worktree_health_in_progress_merge(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: ../fake\n", encoding="utf-8")

    def _fake_run(cmd: list[str], **_kw: object) -> MagicMock:
        # MERGE_HEAD verify → success (rc 0); others → fail.
        if cmd[-1] == "MERGE_HEAD":
            return _make_subproc(0, "")
        return _make_subproc(1, "")

    with (
        patch(
            "specify_cli.workspace.context.verify_workspace_toplevel",
            return_value=None,
        ),
        patch("specify_cli.core.git_ops.get_current_branch", return_value="lane-a"),
        patch("subprocess.run", side_effect=_fake_run),
    ):
        guidance = _check_worktree_health(worktree, "WP01", "for_review")
    assert guidance is not None
    assert guidance[0] == "In-progress git operation detected in worktree!"
    assert "merge" in "\n".join(guidance)


def test_check_worktree_health_clean_returns_none(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: ../fake\n", encoding="utf-8")
    with (
        patch(
            "specify_cli.workspace.context.verify_workspace_toplevel",
            return_value=None,
        ),
        patch("specify_cli.core.git_ops.get_current_branch", return_value="lane-a"),
        patch("subprocess.run", return_value=_make_subproc(1, "")),
    ):
        assert _check_worktree_health(worktree, "WP01", "for_review") is None


# ---------------------------------------------------------------------------
# Sub-split validator: _check_branch_currency
# ---------------------------------------------------------------------------


def test_check_branch_currency_behind_blocks(tmp_path: Path) -> None:
    with patch("subprocess.run", return_value=_make_subproc(0, "3\n")):
        guidance = _check_branch_currency(
            worktree_path=tmp_path,
            check_branch="main",
            mission_slug="demo",
            wp_id="WP01",
            target_lane="for_review",
            behind_commits_touch_only_planning_artifacts=lambda *_a: False,
        )
    assert guidance is not None
    assert "behind main by 3 commit(s)" in "\n".join(guidance)


def test_check_branch_currency_behind_but_planning_only_passes(tmp_path: Path) -> None:
    with patch("subprocess.run", return_value=_make_subproc(0, "3\n")):
        result = _check_branch_currency(
            worktree_path=tmp_path,
            check_branch="main",
            mission_slug="demo",
            wp_id="WP01",
            target_lane="for_review",
            behind_commits_touch_only_planning_artifacts=lambda *_a: True,
        )
    assert result is None


def test_check_branch_currency_up_to_date_passes(tmp_path: Path) -> None:
    with patch("subprocess.run", return_value=_make_subproc(0, "0\n")):
        result = _check_branch_currency(
            worktree_path=tmp_path,
            check_branch="main",
            mission_slug="demo",
            wp_id="WP01",
            target_lane="for_review",
            behind_commits_touch_only_planning_artifacts=lambda *_a: False,
        )
    assert result is None


# ---------------------------------------------------------------------------
# Sub-split validator: _check_uncommitted_worktree_changes
# ---------------------------------------------------------------------------


def test_check_uncommitted_worktree_changes_staged_only(tmp_path: Path) -> None:
    with patch("subprocess.run", return_value=_make_subproc(0, "M  src/foo.py\n")):
        guidance = _check_uncommitted_worktree_changes(
            worktree_path=tmp_path,
            wp_id="WP01",
            target_lane="for_review",
            filter_runtime_state_paths=lambda s: s,
        )
    assert guidance is not None
    assert guidance[0] == "Staged but uncommitted changes in worktree!"


def test_check_uncommitted_worktree_changes_staged_and_unstaged(tmp_path: Path) -> None:
    with patch("subprocess.run", return_value=_make_subproc(0, "MM src/foo.py\n")):
        guidance = _check_uncommitted_worktree_changes(
            worktree_path=tmp_path,
            wp_id="WP01",
            target_lane="for_review",
            filter_runtime_state_paths=lambda s: s,
        )
    assert guidance is not None
    assert guidance[0] == "Staged and unstaged changes in worktree!"


def test_check_uncommitted_worktree_changes_untracked(tmp_path: Path) -> None:
    with patch("subprocess.run", return_value=_make_subproc(0, "?? new.py\n")):
        guidance = _check_uncommitted_worktree_changes(
            worktree_path=tmp_path,
            wp_id="WP01",
            target_lane="for_review",
            filter_runtime_state_paths=lambda s: s,
        )
    assert guidance is not None
    assert guidance[0] == "Uncommitted implementation changes in worktree!"


def test_check_uncommitted_worktree_changes_filtered_clean(tmp_path: Path) -> None:
    # filter strips everything (runtime-state only) → no block.
    with patch("subprocess.run", return_value=_make_subproc(0, " M .spec-kitty/lock\n")):
        result = _check_uncommitted_worktree_changes(
            worktree_path=tmp_path,
            wp_id="WP01",
            target_lane="for_review",
            filter_runtime_state_paths=lambda _s: "",
        )
    assert result is None


# ---------------------------------------------------------------------------
# Sub-split validator: _check_implementation_commit_present
# ---------------------------------------------------------------------------


def test_check_implementation_commit_present_missing_blocks(tmp_path: Path) -> None:
    with patch(
        "specify_cli.cli.commands.agent.tasks_parsing_validation.lane_has_commit_beyond_base",
        return_value=False,
    ):
        guidance = _check_implementation_commit_present(
            worktree_path=tmp_path,
            check_branch="main",
            wp_id="WP01",
            target_lane="for_review",
        )
    assert guidance is not None
    assert guidance[0] == "No implementation commits on lane branch!"


def test_check_implementation_commit_present_ok(tmp_path: Path) -> None:
    with patch(
        "specify_cli.cli.commands.agent.tasks_parsing_validation.lane_has_commit_beyond_base",
        return_value=True,
    ):
        assert _check_implementation_commit_present(
            worktree_path=tmp_path,
            check_branch="main",
            wp_id="WP01",
            target_lane="for_review",
        ) is None


# ---------------------------------------------------------------------------
# Sub-split validator: _check_kitty_specs_contamination
# ---------------------------------------------------------------------------


def test_check_kitty_specs_contamination_blocks_with_planning_branch(tmp_path: Path) -> None:
    with patch(
        "specify_cli.mission_metadata.load_meta",
        return_value={"planning_base_branch": "kitty/plan"},
    ):
        guidance = _check_kitty_specs_contamination(
            worktree_path=tmp_path,
            check_branch="main",
            feature_dir=tmp_path,
            wp_id="WP01",
            target_lane="for_review",
            list_wp_branch_specs_changes_for_guard=lambda **_k: ["kitty-specs/demo/spec.md"],
        )
    assert guidance is not None
    text = "\n".join(guidance)
    assert "Committed kitty-specs files on this lane branch:" in text
    assert "Planning artifacts must live on: kitty/plan" in text
    assert "git show kitty/plan:kitty-specs/demo/spec.md" in text


def test_check_kitty_specs_contamination_unknown_planning_branch(tmp_path: Path) -> None:
    with patch("specify_cli.mission_metadata.load_meta", return_value=None):
        guidance = _check_kitty_specs_contamination(
            worktree_path=tmp_path,
            check_branch="main",
            feature_dir=tmp_path,
            wp_id="WP01",
            target_lane="for_review",
            list_wp_branch_specs_changes_for_guard=lambda **_k: ["kitty-specs/demo/spec.md"],
        )
    assert guidance is not None
    assert "planning branch unknown" in "\n".join(guidance)


def test_check_kitty_specs_contamination_clean_returns_none(tmp_path: Path) -> None:
    result = _check_kitty_specs_contamination(
        worktree_path=tmp_path,
        check_branch="main",
        feature_dir=tmp_path,
        wp_id="WP01",
        target_lane="for_review",
        list_wp_branch_specs_changes_for_guard=lambda **_k: [],
    )
    assert result is None


def test_check_kitty_specs_contamination_diffs_against_planning_branch(tmp_path: Path) -> None:
    """#3271 red-first: the lane-hygiene delta must be measured against the
    PLANNING branch, not the lane's coordination/mission base ref.

    Pre-fix the guard passed ``check_branch`` (the coord/mission branch) to the
    lister, so a lane that legitimately inherited kitty-specs from the base — or
    got this mission's planning artifacts via the #2993 recorded-planning-commit
    merge — false-positived on every transition. The captured ``base_branch``
    must now be the planning branch resolved from meta.json.
    """
    captured: dict[str, object] = {}

    def _spy(**kwargs: object) -> list[str]:
        captured["base_branch"] = kwargs["base_branch"]
        return []  # clean delta against the planning branch → guard passes

    with patch(
        "specify_cli.mission_metadata.load_meta",
        return_value={"planning_base_branch": "kitty/plan"},
    ):
        result = _check_kitty_specs_contamination(
            worktree_path=tmp_path,
            check_branch="kitty/mission-coord-01ABC",
            feature_dir=tmp_path,
            wp_id="WP01",
            target_lane="for_review",
            list_wp_branch_specs_changes_for_guard=_spy,
        )

    assert result is None
    # RED pre-fix: was "kitty/mission-coord-01ABC" (the coordination base ref).
    assert captured["base_branch"] == "kitty/plan"


def test_check_kitty_specs_contamination_falls_back_to_check_branch_without_meta(
    tmp_path: Path,
) -> None:
    """Legacy/flat missions without meta.json keep the lane base ref (#3271).

    When no planning branch can be resolved the delta base must fall back to
    ``check_branch`` exactly as before — the flat/legacy topology forks from the
    mission branch, which is the correct base there.
    """
    captured: dict[str, object] = {}

    def _spy(**kwargs: object) -> list[str]:
        captured["base_branch"] = kwargs["base_branch"]
        return []

    with patch("specify_cli.mission_metadata.load_meta", return_value=None):
        _check_kitty_specs_contamination(
            worktree_path=tmp_path,
            check_branch="kitty/mission-legacy",
            feature_dir=tmp_path,
            wp_id="WP01",
            target_lane="for_review",
            list_wp_branch_specs_changes_for_guard=_spy,
        )

    assert captured["base_branch"] == "kitty/mission-legacy"


# ---------------------------------------------------------------------------
# Sub-split helper: _resolve_planning_branch_for_lane_guard (#3271)
# ---------------------------------------------------------------------------


def test_resolve_planning_branch_prefers_planning_base_branch(tmp_path: Path) -> None:
    with patch(
        "specify_cli.mission_metadata.load_meta",
        return_value={"planning_base_branch": "kitty/plan", "target_branch": "docs/x"},
    ):
        assert _resolve_planning_branch_for_lane_guard(tmp_path) == "kitty/plan"


def test_resolve_planning_branch_falls_back_to_target_branch(tmp_path: Path) -> None:
    with (
        patch(
            "specify_cli.mission_metadata.load_meta",
            return_value={"target_branch": "docs/3253-docs-gaps"},
        ),
        patch(
            "specify_cli.core.paths.read_target_branch_from_meta",
            return_value="docs/3253-docs-gaps",
        ),
    ):
        assert _resolve_planning_branch_for_lane_guard(tmp_path) == "docs/3253-docs-gaps"


def test_resolve_planning_branch_returns_none_without_meta(tmp_path: Path) -> None:
    with patch("specify_cli.mission_metadata.load_meta", return_value=None):
        assert _resolve_planning_branch_for_lane_guard(tmp_path) is None


# ---------------------------------------------------------------------------
# Orchestrator: _validate_worktree_state composition
# ---------------------------------------------------------------------------


def test_validate_worktree_state_repo_root_short_circuits(tmp_path: Path) -> None:
    ws = _FakeWorkspace(resolution_kind="repo_root", worktree_path=tmp_path)
    result = _validate_worktree_state(
        repo_root=tmp_path,
        main_repo_root=tmp_path,
        feature_dir=tmp_path,
        mission_slug="demo",
        wp_id="WP01",
        target_lane="for_review",
        resolve_workspace_for_wp=lambda *_a: ws,
        get_feature_target_branch=lambda *_a: "main",
        review_currency_check_branch=lambda **_k: "main",
        behind_commits_touch_only_planning_artifacts=lambda *_a: False,
        filter_runtime_state_paths=lambda s: s,
        list_wp_branch_specs_changes_for_guard=lambda **_k: [],
    )
    assert result == (True, [])


def test_validate_worktree_state_missing_worktree_falls_through(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    ws = _FakeWorkspace(resolution_kind="lane_workspace", worktree_path=missing)
    result = _validate_worktree_state(
        repo_root=tmp_path,
        main_repo_root=tmp_path,
        feature_dir=tmp_path,
        mission_slug="demo",
        wp_id="WP01",
        target_lane="for_review",
        resolve_workspace_for_wp=lambda *_a: ws,
        get_feature_target_branch=lambda *_a: "main",
        review_currency_check_branch=lambda **_k: "main",
        behind_commits_touch_only_planning_artifacts=lambda *_a: False,
        filter_runtime_state_paths=lambda s: s,
        list_wp_branch_specs_changes_for_guard=lambda **_k: [],
    )
    assert result is None


# ---------------------------------------------------------------------------
# Sub-split validator: _check_branch_currency — #3940 source-divergence report
# ---------------------------------------------------------------------------


def test_check_branch_currency_reports_non_ledger_count(tmp_path: Path) -> None:
    """#3940: the block message reports source divergence (commits touching
    files outside the ledger trees), not the raw behind count that is
    dominated by orchestrator ledger commits."""
    responses = [
        _make_subproc(0, "88\n"),  # raw behind count
        _make_subproc(0, "2\n"),   # non-ledger count (pathspec-excluded)
    ]
    with patch("subprocess.run", side_effect=responses):
        guidance = _check_branch_currency(
            worktree_path=tmp_path,
            check_branch="missions/family",
            mission_slug="demo",
            wp_id="WP01",
            target_lane="for_review",
            behind_commits_touch_only_planning_artifacts=lambda *_a: False,
        )
    assert guidance is not None
    joined = "\n".join(guidance)
    assert "behind missions/family by 88 commit(s)" in joined
    assert "2 non-ledger commit(s) touching files outside kitty-specs/ and .kittify/" in joined


def test_check_branch_currency_count_failure_falls_back_to_raw_count(tmp_path: Path) -> None:
    """#3940: when the non-ledger count cannot be determined, the message
    stays conservative and reports the raw behind count."""
    responses = [
        _make_subproc(0, "88\n"),   # raw behind count
        _make_subproc(128, ""),     # non-ledger count fails
    ]
    with patch("subprocess.run", side_effect=responses):
        guidance = _check_branch_currency(
            worktree_path=tmp_path,
            check_branch="main",
            mission_slug="demo",
            wp_id="WP01",
            target_lane="for_review",
            behind_commits_touch_only_planning_artifacts=lambda *_a: False,
        )
    assert guidance is not None
    joined = "\n".join(guidance)
    assert "behind main by 88 commit(s)" in joined
    assert "88 non-ledger commit(s)" in joined
