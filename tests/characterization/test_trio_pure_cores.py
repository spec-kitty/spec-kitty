"""Direct in->out characterization of the coord-authority trio's pure cores.

WP01 (coord-authority-trio-degod-01KX7094) -- the squad's LAND-BLOCKER: the
functions targeted for SPLIT by WP02/WP03/WP04 must be pinned DIRECTLY, with
a branch-coverage matrix, against the untouched pre-refactor code. The
CLI-envelope (T003) and reducer (T004) layers only prove the scenarios they
happen to exercise -- an internal branch never hit by a chosen end-to-end
scenario can silently change behaviour during a refactor and the suite would
still go green (a false-green). Direct pure-core pinning with an exhaustive
branch matrix is the strong net.

Targets (CC19-37, all currently pure/deterministic given controlled inputs):

* ``acceptance._build_recommended_fix_order``  (pure, no I/O)
* ``acceptance._check_lane_gates``              (CC19; I/O collaborators mocked)
* ``acceptance.collect_feature_summary``        (CC25; wiring, collaborators mocked)
* ``workflow._resolve_review_context``          (CC37; subprocess/git mocked)
* ``workflow._resolve_review_feedback_context`` / ``_has_prior_rejection``
  (the rejection/rewind/resume paths feeding review-context)

Marker: unit only (no subprocess, no real git -- filesystem use is confined
to ``tmp_path``, per the ``unit`` marker's contract in ``pytest.ini``).
"""

from __future__ import annotations

from kernel.clock import now_utc_iso
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from specify_cli import acceptance as acceptance_module
from specify_cli.acceptance import AcceptanceCheckDiagnostic, collect_feature_summary
from specify_cli.cli.commands.agent import workflow as workflow_module
from specify_cli.cli.commands.agent.workflow import (
    _has_prior_rejection,
    _resolve_review_context,
    _resolve_review_feedback_context,
)
from specify_cli.review.cycle import create_rejected_review_cycle
from specify_cli.status import Lane, StatusEvent
from specify_cli.status._unsafe import append_event
from specify_cli.task_utils import WorkPackage
from specify_cli.workspace.context import ResolvedWorkspace, WorkspaceContext

pytestmark = [pytest.mark.unit]


# ===========================================================================
# Section A -- ``_build_recommended_fix_order`` (pure, no mocking needed)
# ===========================================================================


def _base_fix_order_kwargs() -> dict[str, Any]:
    """All-clear inputs: nothing should recommend anything."""
    return {
        "lanes": {"approved": ["WP01"], "done": ["WP02"]},
        "metadata_issues": [],
        "activity_issues": [],
        "unchecked_tasks": [],
        "needs_clarification": [],
        "missing_artifacts": [],
        "git_dirty": [],
        "path_violations": [],
        "blocked_checks": [],
    }


class TestBuildRecommendedFixOrder:
    """Branch matrix: each independent trigger contributes exactly one line."""

    def test_no_issues_yields_empty_recommendations(self) -> None:
        # Arrange
        kwargs = _base_fix_order_kwargs()

        # Assumption check
        assert not any(v for k, v in kwargs.items() if k != "lanes")

        # Act
        result = acceptance_module._build_recommended_fix_order(**kwargs)

        # Assert
        assert result == []

    def test_git_dirty_recommends_commit_or_discard(self) -> None:
        kwargs = _base_fix_order_kwargs()
        kwargs["git_dirty"] = ["kitty-specs/x/spec.md"]

        result = acceptance_module._build_recommended_fix_order(**kwargs)

        assert result == ["Commit, stash, or discard working tree changes before acceptance."]

    def test_mission_branch_blocked_check_recommends_branch_switch(self) -> None:
        kwargs = _base_fix_order_kwargs()
        kwargs["blocked_checks"] = [AcceptanceCheckDiagnostic(check="mission_branch", detail="x")]

        result = acceptance_module._build_recommended_fix_order(**kwargs)

        assert result == ["Switch to the mission branch or configured target branch named in the branch failure."]

    def test_missing_artifacts_recommends_restore(self) -> None:
        kwargs = _base_fix_order_kwargs()
        kwargs["missing_artifacts"] = ["spec.md"]

        result = acceptance_module._build_recommended_fix_order(**kwargs)

        assert result == ["Restore required mission artifacts before acceptance."]

    def test_metadata_issues_recommends_fix_metadata(self) -> None:
        kwargs = _base_fix_order_kwargs()
        kwargs["metadata_issues"] = ["WP01: missing agent"]

        result = acceptance_module._build_recommended_fix_order(**kwargs)

        assert result == ["Fix work-package metadata issues."]

    def test_non_terminal_lane_recommends_move_to_approved_or_done(self) -> None:
        kwargs = _base_fix_order_kwargs()
        kwargs["lanes"] = {"approved": [], "done": [], "in_review": ["WP01"]}

        result = acceptance_module._build_recommended_fix_order(**kwargs)

        assert result == ["Move all work packages to approved or done."]

    def test_terminal_only_lanes_do_not_recommend_move(self) -> None:
        kwargs = _base_fix_order_kwargs()
        kwargs["lanes"] = {"approved": ["WP01"], "done": ["WP02"], "in_review": []}

        result = acceptance_module._build_recommended_fix_order(**kwargs)

        assert result == []

    def test_unchecked_tasks_recommends_completion(self) -> None:
        kwargs = _base_fix_order_kwargs()
        kwargs["unchecked_tasks"] = ["- [ ] do the thing"]

        result = acceptance_module._build_recommended_fix_order(**kwargs)

        assert result == ["Complete unchecked items in tasks.md."]

    def test_needs_clarification_recommends_resolution(self) -> None:
        kwargs = _base_fix_order_kwargs()
        kwargs["needs_clarification"] = ["spec.md: NEEDS CLARIFICATION"]

        result = acceptance_module._build_recommended_fix_order(**kwargs)

        assert result == ["Resolve open NEEDS CLARIFICATION markers."]

    def test_missing_acceptance_matrix_blocked_check_recommends_restore(self) -> None:
        kwargs = _base_fix_order_kwargs()
        kwargs["blocked_checks"] = [AcceptanceCheckDiagnostic(check="acceptance_matrix", detail="x")]

        result = acceptance_module._build_recommended_fix_order(**kwargs)

        assert result == ["Create or restore kitty-specs/<mission>/acceptance-matrix.json."]

    def test_missing_lanes_manifest_blocked_check_recommends_restore(self) -> None:
        kwargs = _base_fix_order_kwargs()
        kwargs["blocked_checks"] = [AcceptanceCheckDiagnostic(check="lanes_manifest", detail="x")]

        result = acceptance_module._build_recommended_fix_order(**kwargs)

        assert result == ["Restore or regenerate kitty-specs/<mission>/lanes.json."]

    def test_evidence_activity_issue_recommends_fill_evidence(self) -> None:
        kwargs = _base_fix_order_kwargs()
        kwargs["activity_issues"] = ["Evidence: WP01 criterion 1 missing artifact_ref"]

        result = acceptance_module._build_recommended_fix_order(**kwargs)

        assert result == ["Fill missing acceptance matrix evidence fields."]

    def test_verdict_activity_issue_recommends_resolve_verdict(self) -> None:
        kwargs = _base_fix_order_kwargs()
        kwargs["activity_issues"] = ["Acceptance matrix verdict is 'fail' — negative invariants or criteria not satisfied"]

        result = acceptance_module._build_recommended_fix_order(**kwargs)

        assert result == ["Resolve pending or failing acceptance matrix criteria and negative invariants."]

    def test_workflow_evidence_activity_issue_recommends_run_evidence(self) -> None:
        kwargs = _base_fix_order_kwargs()
        kwargs["activity_issues"] = ["Workflow run evidence required: this mission changes .github/workflows/ci.yml."]

        result = acceptance_module._build_recommended_fix_order(**kwargs)

        assert result == ["Add successful GitHub Actions run evidence for workflow changes."]

    def test_path_violations_recommends_fix_path_conventions(self) -> None:
        kwargs = _base_fix_order_kwargs()
        kwargs["path_violations"] = ["Path conventions not satisfied."]

        result = acceptance_module._build_recommended_fix_order(**kwargs)

        assert result == ["Fix mission path convention violations."]

    def test_every_trigger_together_preserves_fixed_source_order(self) -> None:
        """Recommendations are emitted in the FIXED order the source checks them in,
        regardless of which dict keys the caller happened to populate first --
        this ordering is itself part of current, pinned behaviour."""
        kwargs: dict[str, Any] = {
            "lanes": {"approved": [], "done": [], "for_review": ["WP01"]},
            "metadata_issues": ["WP01: missing agent"],
            "activity_issues": [
                "Evidence: WP01 missing artifact_ref",
                "Acceptance matrix verdict is 'pending' — criteria or invariants have not been verified",
                "Workflow run evidence required: changes .github/workflows/ci.yml.",
            ],
            "unchecked_tasks": ["- [ ] todo"],
            "needs_clarification": ["spec.md: NEEDS CLARIFICATION"],
            "missing_artifacts": ["spec.md"],
            "git_dirty": ["spec.md"],
            "path_violations": ["Path conventions not satisfied."],
            "blocked_checks": [
                AcceptanceCheckDiagnostic(check="mission_branch", detail="x"),
                AcceptanceCheckDiagnostic(check="acceptance_matrix", detail="x"),
                AcceptanceCheckDiagnostic(check="lanes_manifest", detail="x"),
            ],
        }

        result = acceptance_module._build_recommended_fix_order(**kwargs)

        assert result == [
            "Commit, stash, or discard working tree changes before acceptance.",
            "Switch to the mission branch or configured target branch named in the branch failure.",
            "Restore required mission artifacts before acceptance.",
            "Fix work-package metadata issues.",
            "Move all work packages to approved or done.",
            "Complete unchecked items in tasks.md.",
            "Resolve open NEEDS CLARIFICATION markers.",
            "Create or restore kitty-specs/<mission>/acceptance-matrix.json.",
            "Restore or regenerate kitty-specs/<mission>/lanes.json.",
            "Fill missing acceptance matrix evidence fields.",
            "Resolve pending or failing acceptance matrix criteria and negative invariants.",
            "Add successful GitHub Actions run evidence for workflow changes.",
            "Fix mission path convention violations.",
        ]


# ===========================================================================
# Section B -- ``_check_lane_gates`` (CC19) -- I/O collaborators mocked
# ===========================================================================


def _matrix(negative_invariants: list[Any] | None = None, overall_verdict: str = "pass") -> SimpleNamespace:
    return SimpleNamespace(negative_invariants=negative_invariants or [], overall_verdict=overall_verdict)


class TestCheckLaneGates:
    """Branch matrix over lanes.json / target-branch / matrix state."""

    def test_corrupt_lanes_json_blocks_and_skips_all_checks(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        from specify_cli.lanes.persistence import CorruptLanesError

        def _raise(_feature_dir: Path) -> Any:
            raise CorruptLanesError("lanes.json: invalid JSON at line 3")

        monkeypatch.setattr("specify_cli.lanes.persistence.read_lanes_json", _raise)
        activity_issues: list[str] = []
        skipped: list[AcceptanceCheckDiagnostic] = []
        blocked: list[AcceptanceCheckDiagnostic] = []

        # Assumption check
        assert activity_issues == [] and skipped == [] and blocked == []

        # Act
        acceptance_module._check_lane_gates(tmp_path, tmp_path, "main", activity_issues, skipped, blocked)

        # Assert
        assert {item.check for item in blocked} == {"lanes_manifest"}
        assert activity_issues and "invalid JSON" in activity_issues[0]
        assert {item.check for item in skipped} == {
            "acceptance_matrix_presence",
            "acceptance_matrix_evidence",
            "negative_invariants",
            "acceptance_matrix_verdict",
        }

    def test_missing_lanes_manifest_blocks_and_skips_all_checks(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """#4891: a genuinely absent lanes.json must fail closed, not silently no-op."""
        monkeypatch.setattr("specify_cli.lanes.persistence.read_lanes_json", lambda _fd: None)
        activity_issues: list[str] = []
        skipped: list[AcceptanceCheckDiagnostic] = []
        blocked: list[AcceptanceCheckDiagnostic] = []

        acceptance_module._check_lane_gates(tmp_path, tmp_path, "main", activity_issues, skipped, blocked)

        assert {item.check for item in blocked} == {"lanes_manifest"}
        assert activity_issues != []
        assert {item.check for item in skipped} == {
            "acceptance_matrix_presence",
            "acceptance_matrix_evidence",
            "negative_invariants",
            "acceptance_matrix_verdict",
        }

    def test_target_branch_mismatch_between_meta_and_lanes_blocks(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "specify_cli.lanes.persistence.read_lanes_json",
            lambda _fd: SimpleNamespace(target_branch="feat/target", mission_branch="kitty/mission-x"),
        )
        monkeypatch.setattr(acceptance_module, "read_target_branch_from_meta", lambda _fd: "main")
        activity_issues: list[str] = []
        skipped: list[AcceptanceCheckDiagnostic] = []
        blocked: list[AcceptanceCheckDiagnostic] = []

        acceptance_module._check_lane_gates(tmp_path, tmp_path, "feat/target", activity_issues, skipped, blocked)

        assert {item.check for item in blocked} == {"mission_branch"}
        assert "target branch mismatch" in activity_issues[0]
        assert {item.check for item in skipped} == {  # include_matrix_presence=True
            "acceptance_matrix_presence",
            "acceptance_matrix_evidence",
            "negative_invariants",
            "acceptance_matrix_verdict",
        }

    def test_branch_outside_allowed_set_blocks(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "specify_cli.lanes.persistence.read_lanes_json",
            lambda _fd: SimpleNamespace(target_branch="feat/target", mission_branch="kitty/mission-x"),
        )
        monkeypatch.setattr(acceptance_module, "read_target_branch_from_meta", lambda _fd: None)
        monkeypatch.setattr("specify_cli.lanes.compute.is_planning_artifact_only", lambda _m: False)
        activity_issues: list[str] = []
        skipped: list[AcceptanceCheckDiagnostic] = []
        blocked: list[AcceptanceCheckDiagnostic] = []

        acceptance_module._check_lane_gates(tmp_path, tmp_path, "some-other-branch", activity_issues, skipped, blocked)

        assert {item.check for item in blocked} == {"mission_branch"}
        assert "must run on mission or target branch" in activity_issues[0]

    def test_detached_head_reports_detached_head_label(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "specify_cli.lanes.persistence.read_lanes_json",
            lambda _fd: SimpleNamespace(target_branch="feat/target", mission_branch="kitty/mission-x"),
        )
        monkeypatch.setattr(acceptance_module, "read_target_branch_from_meta", lambda _fd: None)
        monkeypatch.setattr("specify_cli.lanes.compute.is_planning_artifact_only", lambda _m: False)
        activity_issues: list[str] = []

        acceptance_module._check_lane_gates(tmp_path, tmp_path, None, activity_issues, [], [])

        assert "detached HEAD" in activity_issues[0]

    def test_planning_artifact_only_mission_skips_matrix_entirely(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "specify_cli.lanes.persistence.read_lanes_json",
            lambda _fd: SimpleNamespace(target_branch="feat/target", mission_branch="kitty/mission-x"),
        )
        monkeypatch.setattr(acceptance_module, "read_target_branch_from_meta", lambda _fd: None)
        monkeypatch.setattr("specify_cli.lanes.compute.is_planning_artifact_only", lambda _m: True)

        def _fail_if_called(_fd: Path) -> Any:
            raise AssertionError("read_acceptance_matrix must not be called for planning-artifact-only missions")

        monkeypatch.setattr("specify_cli.acceptance.matrix.read_acceptance_matrix", _fail_if_called)
        activity_issues: list[str] = []
        skipped: list[AcceptanceCheckDiagnostic] = []
        blocked: list[AcceptanceCheckDiagnostic] = []

        acceptance_module._check_lane_gates(tmp_path, tmp_path, "feat/target", activity_issues, skipped, blocked)

        assert activity_issues == [] and blocked == []
        assert {item.check for item in skipped} == {  # include_matrix_presence=True
            "acceptance_matrix_presence",
            "acceptance_matrix_evidence",
            "negative_invariants",
            "acceptance_matrix_verdict",
        }

    def test_missing_acceptance_matrix_blocks(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "specify_cli.lanes.persistence.read_lanes_json",
            lambda _fd: SimpleNamespace(target_branch="feat/target", mission_branch="kitty/mission-x"),
        )
        monkeypatch.setattr(acceptance_module, "read_target_branch_from_meta", lambda _fd: None)
        monkeypatch.setattr("specify_cli.lanes.compute.is_planning_artifact_only", lambda _m: False)
        monkeypatch.setattr("specify_cli.acceptance.matrix.read_acceptance_matrix", lambda _fd: None)
        activity_issues: list[str] = []
        skipped: list[AcceptanceCheckDiagnostic] = []
        blocked: list[AcceptanceCheckDiagnostic] = []

        acceptance_module._check_lane_gates(tmp_path, tmp_path, "kitty/mission-x", activity_issues, skipped, blocked)

        assert {item.check for item in blocked} == {"acceptance_matrix"}
        assert {item.check for item in skipped} == {  # include_matrix_presence=False (default)
            "acceptance_matrix_evidence",
            "negative_invariants",
            "acceptance_matrix_verdict",
        }

    def _patch_matrix_reads(self, monkeypatch: pytest.MonkeyPatch, matrix: SimpleNamespace, *, evidence_errors: list[str] | None = None) -> None:
        monkeypatch.setattr(
            "specify_cli.lanes.persistence.read_lanes_json",
            lambda _fd: SimpleNamespace(target_branch="feat/target", mission_branch="kitty/mission-x"),
        )
        monkeypatch.setattr(acceptance_module, "read_target_branch_from_meta", lambda _fd: None)
        monkeypatch.setattr("specify_cli.lanes.compute.is_planning_artifact_only", lambda _m: False)
        monkeypatch.setattr("specify_cli.acceptance.matrix.read_acceptance_matrix", lambda _fd: matrix)
        monkeypatch.setattr("specify_cli.acceptance.matrix.validate_matrix_evidence", lambda _m: evidence_errors or [])
        # WP04 / T016 (#2318): the gate now persists the recomputed verdict
        # unconditionally when mutate_matrix=True, not only inside the
        # negative-invariants arm. ``_matrix()`` here is a bare SimpleNamespace
        # (no ``to_dict``), so the real writer is stubbed to a no-op by
        # default; tests that specifically exercise the write override this
        # with their own monkeypatch call afterwards (setattr is last-wins).
        monkeypatch.setattr("specify_cli.acceptance.matrix.write_acceptance_matrix", lambda _fd, _m: None)

    def test_negative_invariants_enforced_and_matrix_written_when_mutate_true(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        matrix = _matrix(negative_invariants=[SimpleNamespace(name="no-secrets")])
        self._patch_matrix_reads(monkeypatch, matrix)
        enforce_calls: list[Any] = []
        write_calls: list[Any] = []

        def _fake_enforce(_repo: Path, invariants: list[Any], *, context: Any = None) -> list[Any]:
            enforce_calls.append(invariants)
            return invariants

        def _fake_write(_fd: Path, m: Any) -> None:
            write_calls.append(m)

        monkeypatch.setattr("specify_cli.acceptance.matrix.enforce_negative_invariants", _fake_enforce)
        monkeypatch.setattr("specify_cli.acceptance.matrix.write_acceptance_matrix", _fake_write)
        activity_issues: list[str] = []
        skipped: list[AcceptanceCheckDiagnostic] = []

        acceptance_module._check_lane_gates(tmp_path, tmp_path, "kitty/mission-x", activity_issues, skipped, [], mutate_matrix=True)

        assert enforce_calls and write_calls
        assert not any(item.check == "negative_invariants" for item in skipped)

    def test_negative_invariants_skipped_when_mutate_false_diagnose_mode(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        matrix = _matrix(negative_invariants=[SimpleNamespace(name="no-secrets")])
        self._patch_matrix_reads(monkeypatch, matrix)

        def _fail_if_called(*_a: Any, **_k: Any) -> Any:
            raise AssertionError("enforce_negative_invariants must not run in diagnose (mutate_matrix=False) mode")

        monkeypatch.setattr("specify_cli.acceptance.matrix.enforce_negative_invariants", _fail_if_called)
        monkeypatch.setattr("specify_cli.acceptance.matrix.write_acceptance_matrix", _fail_if_called)
        skipped: list[AcceptanceCheckDiagnostic] = []

        acceptance_module._check_lane_gates(tmp_path, tmp_path, "kitty/mission-x", [], skipped, [], mutate_matrix=False)

        assert any(item.check == "negative_invariants" and "diagnose mode is read-only" in item.detail for item in skipped)

    def test_evidence_errors_become_activity_issues(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        matrix = _matrix()
        self._patch_matrix_reads(monkeypatch, matrix, evidence_errors=["WP01 criterion 1: missing artifact_ref"])
        activity_issues: list[str] = []

        acceptance_module._check_lane_gates(tmp_path, tmp_path, "kitty/mission-x", activity_issues, [], [])

        assert activity_issues == ["Evidence: WP01 criterion 1: missing artifact_ref"]

    def test_verdict_fail_becomes_activity_issue(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        matrix = _matrix(overall_verdict="fail")
        self._patch_matrix_reads(monkeypatch, matrix)
        activity_issues: list[str] = []

        acceptance_module._check_lane_gates(tmp_path, tmp_path, "kitty/mission-x", activity_issues, [], [])

        assert any("verdict is 'fail'" in issue for issue in activity_issues)

    def test_verdict_pending_becomes_activity_issue(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        matrix = _matrix(overall_verdict="pending")
        self._patch_matrix_reads(monkeypatch, matrix)
        activity_issues: list[str] = []

        acceptance_module._check_lane_gates(tmp_path, tmp_path, "kitty/mission-x", activity_issues, [], [])

        assert any("verdict is 'pending'" in issue for issue in activity_issues)

    def test_verdict_pass_is_silent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        matrix = _matrix(overall_verdict="pass")
        self._patch_matrix_reads(monkeypatch, matrix)
        activity_issues: list[str] = []
        blocked: list[AcceptanceCheckDiagnostic] = []
        skipped: list[AcceptanceCheckDiagnostic] = []

        acceptance_module._check_lane_gates(tmp_path, tmp_path, "kitty/mission-x", activity_issues, skipped, blocked)

        assert activity_issues == [] and blocked == [] and skipped == []


# ===========================================================================
# Section C -- ``_resolve_review_context`` (CC37) -- subprocess/git mocked
# ===========================================================================


def _cp(returncode: int, stdout: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")


def _lane_workspace(*, wp_id: str, branch_name: str | None, context: WorkspaceContext | None = None) -> ResolvedWorkspace:
    return ResolvedWorkspace(
        mission_slug="trio-mission",
        wp_id=wp_id,
        execution_mode="code_change",
        mode_source="frontmatter",
        resolution_kind="lane_workspace",
        workspace_name=f"trio-mission-lane-{wp_id.lower()}",
        worktree_path=Path("/does-not-matter"),
        branch_name=branch_name,
        lane_id="lane-a",
        lane_wp_ids=[wp_id],
        context=context,
    )


def _repo_root_workspace(*, wp_id: str) -> ResolvedWorkspace:
    return ResolvedWorkspace(
        mission_slug="trio-mission",
        wp_id=wp_id,
        execution_mode="planning_artifact",
        mode_source="frontmatter",
        resolution_kind="repo_root",
        workspace_name="trio-mission-repo-root",
        worktree_path=Path("/does-not-matter"),
        branch_name=None,
        lane_id=None,
        lane_wp_ids=[],
        context=None,
    )


def _seam_stub(read_dir: Path) -> SimpleNamespace:
    """A :class:`PlacementSeam` double whose ``.read_dir(kind)`` returns *read_dir*.

    2026-07-27 re-pin: ``_resolve_review_context`` used to resolve the mission
    dir through the kind-blind ``workflow.resolve_planning_read_dir``; the
    read-surface migration routed every workflow.py read onto
    ``_workflow_placement_seam(...).read_dir(<MissionArtifactKind>)``. Stubbing
    the seam *constructor* (rather than the per-read wrapper) keeps the tests
    exercising the production ``_resolve_workflow_read_dir`` kind routing while
    isolating them from real filesystem/topology resolution — the same
    isolation the old ``resolve_planning_read_dir`` stub provided.
    """
    return SimpleNamespace(read_dir=lambda _kind: read_dir)


class TestResolveReviewContext:
    """Branch matrix over workspace existence / resolution_kind / base-ref discovery."""

    def test_nonexistent_workspace_returns_default_context(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope"

        ctx = _resolve_review_context(missing, tmp_path, "trio-mission", "WP01", "")

        assert ctx == {
            "branch_name": "unknown",
            "base_branch": "unknown",
            "mission_branch": "unknown",
            "lane_branch": "unknown",
            "base_ref": "unknown",
            "commit_count": 0,
        }

    def test_repo_root_kind_with_claim_commit_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        monkeypatch.setattr(workflow_module, "resolve_workspace_for_wp", lambda *_a, **_k: _repo_root_workspace(wp_id="WP01"))
        monkeypatch.setattr(workflow_module, "_workflow_placement_seam", lambda *_a, **_k: _seam_stub(tmp_path / "kitty-specs" / "trio-mission"))
        monkeypatch.setattr("specify_cli.lanes.persistence.read_lanes_json", lambda _fd: None)

        def _fake_run(args: list[str], **_kw: Any) -> SimpleNamespace:
            if args[1] == "log":
                return _cp(0, "abc1234def\x00Move WP01 to in_progress\n")
            if args[1] == "rev-list":
                return _cp(0, "3")
            raise AssertionError(f"unexpected git invocation: {args}")

        monkeypatch.setattr(workflow_module.subprocess, "run", _fake_run)

        ctx = _resolve_review_context(workspace_path, tmp_path, "trio-mission", "WP01", "")

        assert ctx["branch_name"] == "HEAD"
        assert ctx["base_branch"] == "abc1234def"
        assert ctx["lane_branch"] == "HEAD"
        assert ctx["base_ref"] == "abc1234def"
        assert ctx["commit_count"] == 3

    def test_repo_root_kind_claim_commit_not_found_returns_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        monkeypatch.setattr(workflow_module, "resolve_workspace_for_wp", lambda *_a, **_k: _repo_root_workspace(wp_id="WP01"))
        monkeypatch.setattr(workflow_module, "_workflow_placement_seam", lambda *_a, **_k: _seam_stub(tmp_path / "kitty-specs" / "trio-mission"))
        monkeypatch.setattr("specify_cli.lanes.persistence.read_lanes_json", lambda _fd: None)
        monkeypatch.setattr(workflow_module.subprocess, "run", lambda *_a, **_k: _cp(0, ""))

        ctx = _resolve_review_context(workspace_path, tmp_path, "trio-mission", "WP01", "")

        assert ctx["branch_name"] == "unknown"
        assert ctx["commit_count"] == 0

    def test_repo_root_kind_rev_list_failure_defaults_commit_count_to_one(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        monkeypatch.setattr(workflow_module, "resolve_workspace_for_wp", lambda *_a, **_k: _repo_root_workspace(wp_id="WP01"))
        monkeypatch.setattr(workflow_module, "_workflow_placement_seam", lambda *_a, **_k: _seam_stub(tmp_path / "kitty-specs" / "trio-mission"))
        monkeypatch.setattr("specify_cli.lanes.persistence.read_lanes_json", lambda _fd: None)

        def _fake_run(args: list[str], **_kw: Any) -> SimpleNamespace:
            if args[1] == "log":
                return _cp(0, "abc1234def\x00Start WP01 implementation\n")
            return _cp(1, "")

        monkeypatch.setattr(workflow_module.subprocess, "run", _fake_run)

        ctx = _resolve_review_context(workspace_path, tmp_path, "trio-mission", "WP01", "")

        assert ctx["commit_count"] == 1

    def test_lane_workspace_current_branch_missing_returns_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        monkeypatch.setattr(workflow_module, "resolve_workspace_for_wp", lambda *_a, **_k: _lane_workspace(wp_id="WP02", branch_name="kitty/mission-x-lane-a"))
        monkeypatch.setattr(workflow_module, "_workflow_placement_seam", lambda *_a, **_k: _seam_stub(tmp_path / "kitty-specs" / "trio-mission"))
        monkeypatch.setattr("specify_cli.lanes.persistence.read_lanes_json", lambda _fd: None)
        monkeypatch.setattr("specify_cli.core.git_ops.get_current_branch", lambda _wp: None)

        ctx = _resolve_review_context(workspace_path, tmp_path, "trio-mission", "WP02", "")

        assert ctx["branch_name"] == "unknown"
        assert ctx["mission_branch"] == "unknown"

    def test_base_ref_resolved_from_lanes_manifest_mission_branch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        monkeypatch.setattr(workflow_module, "resolve_workspace_for_wp", lambda *_a, **_k: _lane_workspace(wp_id="WP02", branch_name="kitty/mission-x-lane-a"))
        monkeypatch.setattr(workflow_module, "_workflow_placement_seam", lambda *_a, **_k: _seam_stub(tmp_path / "kitty-specs" / "trio-mission"))
        monkeypatch.setattr(
            "specify_cli.lanes.persistence.read_lanes_json",
            lambda _fd: SimpleNamespace(mission_branch="kitty/mission-x"),
        )
        monkeypatch.setattr("specify_cli.core.git_ops.get_current_branch", lambda _wp: "kitty/mission-x-lane-a")
        monkeypatch.setattr(workflow_module.subprocess, "run", lambda *_a, **_k: _cp(0, "5"))

        ctx = _resolve_review_context(workspace_path, tmp_path, "trio-mission", "WP02", "")

        assert ctx["mission_branch"] == "kitty/mission-x"
        assert ctx["base_branch"] == "kitty/mission-x"
        assert ctx["base_ref"] == "kitty/mission-x"
        assert ctx["commit_count"] == 5

    def test_base_ref_resolved_from_workspace_context_base_branch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        wctx = WorkspaceContext(
            wp_id="WP02",
            mission_slug="trio-mission",
            worktree_path=".worktrees/trio-mission-lane-a",
            branch_name="kitty/mission-x-lane-a",
            base_branch="main",
            base_commit=None,
            dependencies=[],
            created_at="2026-01-01T00:00:00Z",
            created_by="implement-command",
            vcs_backend="git",
            lane_id="lane-a",
            lane_wp_ids=["WP02"],
        )
        monkeypatch.setattr(
            workflow_module, "resolve_workspace_for_wp", lambda *_a, **_k: _lane_workspace(wp_id="WP02", branch_name="kitty/mission-x-lane-a", context=wctx)
        )
        monkeypatch.setattr(workflow_module, "_workflow_placement_seam", lambda *_a, **_k: _seam_stub(tmp_path / "kitty-specs" / "trio-mission"))
        monkeypatch.setattr("specify_cli.lanes.persistence.read_lanes_json", lambda _fd: None)
        monkeypatch.setattr("specify_cli.core.git_ops.get_current_branch", lambda _wp: "kitty/mission-x-lane-a")
        monkeypatch.setattr(workflow_module.subprocess, "run", lambda *_a, **_k: _cp(0, "2"))

        ctx = _resolve_review_context(workspace_path, tmp_path, "trio-mission", "WP02", "")

        assert ctx["base_branch"] == "main"
        assert ctx["commit_count"] == 2

    def test_unknown_base_ref_discovers_candidate_via_dependency(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        current = _lane_workspace(wp_id="WP02", branch_name="kitty/mission-x-lane-b")
        dependency = _lane_workspace(wp_id="WP01", branch_name="kitty/mission-x-lane-a")

        def _fake_resolve(_repo_root: Path, _slug: str, wp_id: str) -> ResolvedWorkspace:
            return current if wp_id == "WP02" else dependency

        monkeypatch.setattr(workflow_module, "resolve_workspace_for_wp", _fake_resolve)
        monkeypatch.setattr(workflow_module, "_workflow_placement_seam", lambda *_a, **_k: _seam_stub(tmp_path / "kitty-specs" / "trio-mission"))
        monkeypatch.setattr("specify_cli.lanes.persistence.read_lanes_json", lambda _fd: None)
        monkeypatch.setattr("specify_cli.core.git_ops.get_current_branch", lambda _wp: "kitty/mission-x-lane-b")

        def _fake_run(args: list[str], **_kw: Any) -> SimpleNamespace:
            if args[1] == "merge-base":
                candidate = args[3]
                if candidate == "kitty/mission-x-lane-a":
                    return _cp(0, "cafe123")
                return _cp(1, "")
            if args[1] == "rev-list":
                return _cp(0, "1")
            raise AssertionError(f"unexpected git invocation: {args}")

        monkeypatch.setattr(workflow_module.subprocess, "run", _fake_run)

        ctx = _resolve_review_context(workspace_path, tmp_path, "trio-mission", "WP02", 'dependencies: ["WP01"]')

        assert ctx["base_branch"] == "kitty/mission-x-lane-a"
        assert ctx["commit_count"] == 1

    def test_unknown_base_ref_falls_back_to_well_known_branch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        monkeypatch.setattr(workflow_module, "resolve_workspace_for_wp", lambda *_a, **_k: _lane_workspace(wp_id="WP02", branch_name="kitty/mission-x-lane-a"))
        monkeypatch.setattr(workflow_module, "_workflow_placement_seam", lambda *_a, **_k: _seam_stub(tmp_path / "kitty-specs" / "trio-mission"))
        monkeypatch.setattr("specify_cli.lanes.persistence.read_lanes_json", lambda _fd: None)
        monkeypatch.setattr("specify_cli.core.git_ops.get_current_branch", lambda _wp: "kitty/mission-x-lane-a")

        def _fake_run(args: list[str], **_kw: Any) -> SimpleNamespace:
            if args[1] == "merge-base":
                return _cp(0, "cafe123") if args[3] == "main" else _cp(1, "")
            if args[1] == "rev-list":
                return _cp(0, "7")
            raise AssertionError(f"unexpected git invocation: {args}")

        monkeypatch.setattr(workflow_module.subprocess, "run", _fake_run)

        ctx = _resolve_review_context(workspace_path, tmp_path, "trio-mission", "WP02", "")

        assert ctx["base_branch"] == "main"
        assert ctx["commit_count"] == 7

    def test_unknown_base_ref_no_candidate_survives_stays_unknown(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        monkeypatch.setattr(workflow_module, "resolve_workspace_for_wp", lambda *_a, **_k: _lane_workspace(wp_id="WP02", branch_name="kitty/mission-x-lane-a"))
        monkeypatch.setattr(workflow_module, "_workflow_placement_seam", lambda *_a, **_k: _seam_stub(tmp_path / "kitty-specs" / "trio-mission"))
        monkeypatch.setattr("specify_cli.lanes.persistence.read_lanes_json", lambda _fd: None)
        monkeypatch.setattr("specify_cli.core.git_ops.get_current_branch", lambda _wp: "kitty/mission-x-lane-a")
        monkeypatch.setattr(workflow_module.subprocess, "run", lambda *_a, **_k: _cp(1, ""))

        ctx = _resolve_review_context(workspace_path, tmp_path, "trio-mission", "WP02", "")

        assert ctx["base_branch"] == "unknown"
        assert ctx["commit_count"] == 0
        # branch_name/lane_branch/mission_branch were already resolved before
        # candidate discovery ran -- this is a genuine PARTIAL fill, not a
        # full reset to the all-unknown default.
        assert ctx["branch_name"] == "kitty/mission-x-lane-a"

    def test_known_base_ref_rev_list_failure_yields_zero_commit_count(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        monkeypatch.setattr(workflow_module, "resolve_workspace_for_wp", lambda *_a, **_k: _lane_workspace(wp_id="WP02", branch_name="kitty/mission-x-lane-a"))
        monkeypatch.setattr(workflow_module, "_workflow_placement_seam", lambda *_a, **_k: _seam_stub(tmp_path / "kitty-specs" / "trio-mission"))
        monkeypatch.setattr(
            "specify_cli.lanes.persistence.read_lanes_json",
            lambda _fd: SimpleNamespace(mission_branch="kitty/mission-x"),
        )
        monkeypatch.setattr("specify_cli.core.git_ops.get_current_branch", lambda _wp: "kitty/mission-x-lane-a")
        monkeypatch.setattr(workflow_module.subprocess, "run", lambda *_a, **_k: _cp(1, ""))

        ctx = _resolve_review_context(workspace_path, tmp_path, "trio-mission", "WP02", "")

        assert ctx["base_branch"] == "kitty/mission-x"
        assert ctx["commit_count"] == 0


# ===========================================================================
# Section D -- rejection/rewind/resume paths feeding review-context
# ===========================================================================


def _write_events(feature_dir: Path, events: list[StatusEvent]) -> None:
    for event in events:
        append_event(feature_dir, event)


def _seed_rejected_review_cycle(repo_root: Path, *, wp_id: str, wp_slug: str) -> str:
    """Create a REAL review-cycle artifact via the canonical writer.

    Uses ``create_rejected_review_cycle`` (the exact production write path
    ``tasks.py::_persist_review_feedback`` calls on rejection) rather than a
    hand-written markdown file, so the artifact's on-disk shape is genuinely
    valid and ``resolve_review_cycle_pointer`` accepts it.
    """
    feedback_source = repo_root / "feedback-source.md"
    feedback_source.write_text("Reviewer feedback: fix the thing.\n", encoding="utf-8")
    created = create_rejected_review_cycle(
        main_repo_root=repo_root,
        mission_slug="trio-mission",
        wp_id=wp_id,
        wp_slug=wp_slug,
        feedback_source=feedback_source,
        reviewer_agent="reviewer-renata",
    )
    pointer: str = created.pointer
    return pointer


def _event(*, wp_id: str, from_lane: Lane, to_lane: Lane, review_ref: str | None = None, event_id: str) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug="trio-mission",
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=now_utc_iso(),
        actor="reviewer-renata",
        force=False,
        execution_mode="worktree",
        review_ref=review_ref,
    )


class TestReviewFeedbackAndRejectionResumePaths:
    """``_resolve_review_feedback_context`` / ``_has_prior_rejection`` pin the
    rejection -> rewind -> resume lifecycle that feeds the review-context
    surface with the reviewer's feedback pointer."""

    def test_no_events_and_no_frontmatter_marker_means_no_feedback(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "trio-mission"
        feature_dir.mkdir(parents=True)

        result = _resolve_review_feedback_context(feature_dir, "WP01", "work_package_id: WP01\n")

        assert result == (False, None, None, None)

    def test_canonical_review_ref_from_rejection_event_wins(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "trio-mission"
        feature_dir.mkdir(parents=True)
        pointer = _seed_rejected_review_cycle(tmp_path, wp_id="WP01", wp_slug="WP01")
        _write_events(
            feature_dir,
            [
                _event(wp_id="WP01", from_lane=Lane.IN_REVIEW, to_lane=Lane.PLANNED, review_ref=pointer, event_id="01REJECTEVT0000000000000A"),
            ],
        )

        result = _resolve_review_feedback_context(feature_dir, "WP01", "work_package_id: WP01\n")

        assert result[0] is True
        assert result[1] == pointer
        assert result[3] == "canonical"

    def test_sentinel_review_ref_is_skipped_without_frontmatter_fallback(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "trio-mission"
        feature_dir.mkdir(parents=True)
        _write_events(
            feature_dir,
            [
                _event(
                    wp_id="WP01",
                    from_lane=Lane.FOR_REVIEW,
                    to_lane=Lane.IN_REVIEW,
                    review_ref="action-review-claim",
                    event_id="01CLAIMEVT00000000000000A",
                ),
            ],
        )
        frontmatter = 'review_status: "has_feedback"\nreview_feedback: "legacy-ref"\n'

        result = _resolve_review_feedback_context(feature_dir, "WP01", frontmatter)

        assert result == (False, None, None, None)

    def test_has_prior_rejection_false_when_no_subtask_dir(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "trio-mission"
        feature_dir.mkdir(parents=True)

        assert _has_prior_rejection(feature_dir, "WP01-title", "WP01") is False

    def test_has_prior_rejection_false_when_no_review_cycle_files(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "trio-mission"
        (feature_dir / "tasks" / "WP01-title").mkdir(parents=True)

        assert _has_prior_rejection(feature_dir, "WP01-title", "WP01") is False

    def test_has_prior_rejection_true_for_active_rejection_awaiting_resume(self, tmp_path: Path) -> None:
        """The genuine rejection -> rewind -> resume case: reviewer rejected
        (in_review -> planned with a review_ref), implementer claimed again
        (planned -> in_progress) but has not yet been approved -- feedback is
        still active and must be surfaced on resume."""
        feature_dir = tmp_path / "kitty-specs" / "trio-mission"
        feature_dir.mkdir(parents=True)
        pointer = _seed_rejected_review_cycle(tmp_path, wp_id="WP01", wp_slug="WP01-title")
        _write_events(
            feature_dir,
            [
                _event(wp_id="WP01", from_lane=Lane.FOR_REVIEW, to_lane=Lane.IN_REVIEW, event_id="01EVTA0000000000000000001"),
                _event(wp_id="WP01", from_lane=Lane.IN_REVIEW, to_lane=Lane.PLANNED, review_ref=pointer, event_id="01EVTB0000000000000000002"),
                _event(wp_id="WP01", from_lane=Lane.PLANNED, to_lane=Lane.IN_PROGRESS, event_id="01EVTC0000000000000000003"),
            ],
        )

        assert _has_prior_rejection(feature_dir, "WP01-title", "WP01") is True

    def test_has_prior_rejection_false_once_approved_after_rejection(self, tmp_path: Path) -> None:
        """Rewind resolved: implementer resumed and the WP was subsequently
        approved -- the rejection is no longer active."""
        feature_dir = tmp_path / "kitty-specs" / "trio-mission"
        feature_dir.mkdir(parents=True)
        pointer = _seed_rejected_review_cycle(tmp_path, wp_id="WP01", wp_slug="WP01-title")
        _write_events(
            feature_dir,
            [
                _event(wp_id="WP01", from_lane=Lane.IN_REVIEW, to_lane=Lane.PLANNED, review_ref=pointer, event_id="01EVTD0000000000000000004"),
                _event(wp_id="WP01", from_lane=Lane.PLANNED, to_lane=Lane.IN_PROGRESS, event_id="01EVTE0000000000000000005"),
                _event(wp_id="WP01", from_lane=Lane.IN_PROGRESS, to_lane=Lane.FOR_REVIEW, event_id="01EVTF0000000000000000006"),
                _event(wp_id="WP01", from_lane=Lane.FOR_REVIEW, to_lane=Lane.IN_REVIEW, event_id="01EVTG0000000000000000007"),
                _event(wp_id="WP01", from_lane=Lane.IN_REVIEW, to_lane=Lane.APPROVED, event_id="01EVTH0000000000000000008"),
            ],
        )

        assert _has_prior_rejection(feature_dir, "WP01-title", "WP01") is False


# ===========================================================================
# Section E -- ``collect_feature_summary`` (CC25) wiring, collaborators mocked
# ===========================================================================


def _wp(work_package_id: str, *, path: Path, agent: str | None = "claude", assignee: str | None = "claude", shell_pid: str | None = "123") -> WorkPackage:
    lines = [f"work_package_id: {work_package_id}", "title: Demo WP"]
    if agent is not None:
        lines.append(f"agent: {agent}")
    if assignee is not None:
        lines.append(f"assignee: {assignee}")
    if shell_pid is not None:
        lines.append(f"shell_pid: {shell_pid}")
    frontmatter = "\n".join(lines) + "\n"
    return WorkPackage(
        feature="trio-mission",
        path=path,
        current_lane="approved",
        relative_subpath=Path(work_package_id + ".md"),
        frontmatter=frontmatter,
        body="",
        padding="",
    )


class TestCollectFeatureSummaryWiring:
    """``collect_feature_summary`` orchestrates ~15 collaborators; these tests
    mock every collaborator and pin the WIRING: which computed value flows
    into which downstream call, and which conditional branch inside the
    function body selects which behaviour."""

    def _wire_common(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        *,
        strict_metadata: bool,
        wps: list[WorkPackage],
        snapshot_wps: dict[str, dict[str, Any]] | None = None,
    ) -> tuple[Path, dict[str, list[str]]]:
        feature_dir = tmp_path / "kitty-specs" / "trio-mission"
        feature_dir.mkdir(parents=True)
        (feature_dir / "tasks").mkdir()

        monkeypatch.setattr("mission_runtime.placement_seam", lambda *_a, **_k: SimpleNamespace(read_dir=lambda _kind: feature_dir))
        monkeypatch.setattr(acceptance_module, "_primary_anchor_feature_dir", lambda *_a, **_k: feature_dir)
        monkeypatch.setattr(acceptance_module, "check_pre30_layout", lambda _fd: None)
        monkeypatch.setattr(acceptance_module, "_resolve_git_context", lambda _repo: ("kitty/mission-x", tmp_path, tmp_path, []))
        monkeypatch.setattr(acceptance_module, "_status_read_feature_dir", lambda *_a, **_k: feature_dir)
        monkeypatch.setattr(acceptance_module, "_accept_dirty_gate", lambda *_a, **_k: [])
        monkeypatch.setattr(acceptance_module, "_collect_snapshot_wps", lambda *_a, **_k: snapshot_wps or {})
        monkeypatch.setattr(acceptance_module, "_iter_work_packages", lambda *_a, **_k: iter(wps))
        monkeypatch.setattr(acceptance_module, "_planning_read_dir", lambda *_a, **_k: feature_dir)
        monkeypatch.setattr(acceptance_module, "_find_unchecked_tasks", lambda _f: [])
        monkeypatch.setattr(acceptance_module, "_check_needs_clarification", lambda _files: [])
        monkeypatch.setattr(acceptance_module, "_missing_artifacts", lambda *_a: ([], []))
        monkeypatch.setattr(acceptance_module, "get_mission_for_feature", lambda _fd: (_ for _ in ()).throw(acceptance_module.MissionError("no mission.yaml")))
        monkeypatch.setattr(acceptance_module, "_check_lane_gates", lambda *_a, **_k: None)
        return feature_dir, {}

    def test_strict_metadata_true_flags_missing_agent_and_assignee(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        feature_dir, _ = self._wire_common(
            monkeypatch,
            tmp_path,
            strict_metadata=True,
            wps=[],
            snapshot_wps={"WP01": {"lane": "in_progress"}},
        )
        wp = _wp("WP01", path=feature_dir / "tasks" / "WP01.md", agent=None, assignee=None, shell_pid=None)
        monkeypatch.setattr(acceptance_module, "_iter_work_packages", lambda *_a, **_k: iter([wp]))

        summary = collect_feature_summary(tmp_path, "trio-mission", strict_metadata=True, mutate_matrix=False)

        assert any(i.startswith("WP01: missing agent in canonical runtime state") for i in summary.metadata_issues)
        assert "WP01: missing assignee in canonical runtime state" in summary.metadata_issues
        assert "WP01: missing shell_pid in canonical runtime state" in summary.metadata_issues

    def test_strict_metadata_false_suppresses_metadata_issues(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        feature_dir, _ = self._wire_common(
            monkeypatch,
            tmp_path,
            strict_metadata=False,
            wps=[],
            snapshot_wps={"WP01": {"lane": "in_progress"}},
        )
        wp = _wp("WP01", path=feature_dir / "tasks" / "WP01.md", agent=None, assignee=None, shell_pid=None)
        monkeypatch.setattr(acceptance_module, "_iter_work_packages", lambda *_a, **_k: iter([wp]))

        summary = collect_feature_summary(tmp_path, "trio-mission", strict_metadata=False, mutate_matrix=False)

        assert summary.metadata_issues == []

    def test_terminal_lane_wp_is_exempt_from_active_metadata_gate(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A done/approved WP has no live shell -- the assignee/shell_pid gate
        must not fire for it even under strict_metadata (issue #2369)."""
        feature_dir, _ = self._wire_common(
            monkeypatch,
            tmp_path,
            strict_metadata=True,
            wps=[],
            snapshot_wps={"WP01": {"lane": "done", "agent": "claude"}},
        )
        wp = _wp("WP01", path=feature_dir / "tasks" / "WP01.md", agent="claude", assignee=None, shell_pid=None)
        monkeypatch.setattr(acceptance_module, "_iter_work_packages", lambda *_a, **_k: iter([wp]))

        summary = collect_feature_summary(tmp_path, "trio-mission", strict_metadata=True, mutate_matrix=False)

        assert summary.metadata_issues == []

    def test_missing_feature_dir_raises_acceptance_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        absent = tmp_path / "kitty-specs" / "ghost-mission"
        monkeypatch.setattr("mission_runtime.placement_seam", lambda *_a, **_k: SimpleNamespace(read_dir=lambda _kind: absent))
        monkeypatch.setattr(acceptance_module, "_primary_anchor_feature_dir", lambda *_a, **_k: absent)

        with pytest.raises(acceptance_module.AcceptanceError, match="Mission directory not found"):
            collect_feature_summary(tmp_path, "ghost-mission")

    def test_recommended_fix_order_receives_the_assembled_issue_lists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Pin the wiring: every accumulated issue bucket flows into
        ``_build_recommended_fix_order`` by name, and the summary's
        ``recommended_fix_order`` is exactly what that call returned."""
        feature_dir, _ = self._wire_common(
            monkeypatch,
            tmp_path,
            strict_metadata=False,
            wps=[],
            snapshot_wps={},
        )
        captured: dict[str, Any] = {}
        sentinel = ["do the specific thing"]

        def _spy(**kwargs: Any) -> list[str]:
            captured.update(kwargs)
            return sentinel

        monkeypatch.setattr(acceptance_module, "_build_recommended_fix_order", _spy)

        summary = collect_feature_summary(tmp_path, "trio-mission", strict_metadata=False, mutate_matrix=False)

        assert summary.recommended_fix_order == sentinel
        assert set(captured.keys()) == {
            "lanes",
            "metadata_issues",
            "activity_issues",
            "unchecked_tasks",
            "needs_clarification",
            "missing_artifacts",
            "git_dirty",
            "path_violations",
            "blocked_checks",
        }

    def test_lane_gates_read_from_coord_dir_not_primary(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """T028 / WP04-#2107: the lane-gate check must read from the
        coord-resolved ``read_feature_dir``, NOT the primary ``feature_dir`` --
        these differ under coord topology."""
        coord_dir = tmp_path / "coord-worktree" / "kitty-specs" / "trio-mission"
        coord_dir.mkdir(parents=True)
        primary_dir = tmp_path / "kitty-specs" / "trio-mission"
        primary_dir.mkdir(parents=True)
        (primary_dir / "tasks").mkdir()

        monkeypatch.setattr("mission_runtime.placement_seam", lambda *_a, **_k: SimpleNamespace(read_dir=lambda _kind: coord_dir))
        monkeypatch.setattr(acceptance_module, "_primary_anchor_feature_dir", lambda *_a, **_k: primary_dir)
        monkeypatch.setattr(acceptance_module, "check_pre30_layout", lambda _fd: None)
        monkeypatch.setattr(acceptance_module, "_resolve_git_context", lambda _repo: ("kitty/mission-x", tmp_path, tmp_path, []))
        monkeypatch.setattr(acceptance_module, "_status_read_feature_dir", lambda *_a, **_k: coord_dir)
        monkeypatch.setattr(acceptance_module, "_accept_dirty_gate", lambda *_a, **_k: [])
        monkeypatch.setattr(acceptance_module, "_collect_snapshot_wps", lambda *_a, **_k: {})
        monkeypatch.setattr(acceptance_module, "_iter_work_packages", lambda *_a, **_k: iter([]))
        monkeypatch.setattr(acceptance_module, "_planning_read_dir", lambda *_a, **_k: primary_dir)
        monkeypatch.setattr(acceptance_module, "_find_unchecked_tasks", lambda _f: [])
        monkeypatch.setattr(acceptance_module, "_check_needs_clarification", lambda _files: [])
        monkeypatch.setattr(acceptance_module, "_missing_artifacts", lambda *_a: ([], []))
        monkeypatch.setattr(acceptance_module, "get_mission_for_feature", lambda _fd: (_ for _ in ()).throw(acceptance_module.MissionError("no mission.yaml")))

        lane_gate_calls: list[Path] = []
        monkeypatch.setattr(acceptance_module, "_check_lane_gates", lambda _repo, fd, *_a, **_k: lane_gate_calls.append(fd))

        collect_feature_summary(tmp_path, "trio-mission", strict_metadata=False, mutate_matrix=False)

        assert lane_gate_calls == [coord_dir]


# ===========================================================================
# Section F -- bonus: already-clean pure helpers touched by the same wiring
# ===========================================================================


class TestNormalizedUncheckedTasksHelper:
    def test_missing_tasks_file_sentinel_is_dropped(self) -> None:
        result = acceptance_module._normalized_unchecked_tasks(["tasks.md missing"], {"planned": ["WP01"]})

        assert result == []

    def test_all_terminal_work_packages_drops_unchecked_items(self) -> None:
        result = acceptance_module._normalized_unchecked_tasks(["- [ ] leftover"], {"approved": ["WP01"], "done": ["WP02"]})

        assert result == []

    def test_non_terminal_work_package_keeps_unchecked_items(self) -> None:
        result = acceptance_module._normalized_unchecked_tasks(["- [ ] leftover"], {"approved": [], "in_review": ["WP01"]})

        assert result == ["- [ ] leftover"]

    def test_no_tracked_work_packages_keeps_unchecked_items(self) -> None:
        result = acceptance_module._normalized_unchecked_tasks(["- [ ] leftover"], {"planned": []})

        assert result == ["- [ ] leftover"]
