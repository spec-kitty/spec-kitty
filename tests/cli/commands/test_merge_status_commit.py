"""Tests for FR-019 (safe_commit insertion) and FR-020 (done events in git history).

The most important test is test_done_events_committed_to_git which uses
git show HEAD: to prove the events are durably committed after _run_lane_based_merge
returns (the canonical mechanically-correct assertion — NOT git reset --hard HEAD).

Note on patching: consolidate_lane_into_mission/integrate_mission_into_target are imported locally inside
_run_lane_based_merge, so they must be patched at the source module level
(specify_cli.lanes.merge.*) not at specify_cli.cli.commands.merge.*.
evaluate_merge_gates and load_policy_config are similarly patched at their source paths.
"""

from __future__ import annotations

import json
import subprocess
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from specify_cli.cli.commands.merge import (
    _mark_wp_merged_done,
    _record_baseline_merge_commit,
    _run_lane_based_merge,
)
from specify_cli.merge.config import MergeStrategy

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_git_repo(path: Path, branch: str = "main") -> None:
    """Initialize a git repo with a signed-off initial commit."""
    subprocess.run(["git", "init", f"-b{branch}"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=path, check=True, capture_output=True
    )
    (path / "README.md").write_text("init\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"],
        cwd=path, check=True, capture_output=True,
    )


def _seed_mission_branch(repo_path: Path, mission_slug: str) -> None:
    """Create the expected mission branch for tests that mock merge internals."""
    if not (repo_path / ".git").exists():
        _init_git_repo(repo_path)
    subprocess.run(
        ["git", "branch", f"kitty/mission-{mission_slug}"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )


def _write_wp_file(tasks_dir: Path, wp_id: str, *, review_status: str = "approved", reviewed_by: str = "reviewer-1") -> None:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{wp_id}-impl.md").write_text(
        f"---\nwork_package_id: \"{wp_id}\"\nreview_status: \"{review_status}\"\nreviewed_by: \"{reviewed_by}\"\n---\n# {wp_id}\n",
        encoding="utf-8",
    )


def _seed_status_event(feature_dir: Path, mission_slug: str, wp_id: str, to_lane: str) -> None:
    """Write a minimal status event JSON line to status.events.jsonl."""
    event = {
        "actor": "test",
        "at": "2026-04-07T00:00:00+00:00",
        "event_id": f"TEST{wp_id}000",
        "evidence": None,
        "execution_mode": "direct_repo",
        "feature_slug": mission_slug,
        "force": True,
        "from_lane": "planned",
        "reason": "test seed",
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": wp_id,
    }
    jsonl_path = feature_dir / "status.events.jsonl"
    with jsonl_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def _write_meta(feature_dir: Path, mission_slug: str, **overrides: object) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "created_at": "2026-04-07T00:00:00+00:00",
        "friendly_name": mission_slug.replace("-", " "),
        "mission_id": "01KTESTMISSIONID00000000000",
        "mission_number": None,
        "mission_slug": mission_slug,
        "mission_type": "software-dev",
        "slug": mission_slug,
        "target_branch": "main",
    }
    meta.update(overrides)
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _baseline_run_command_side_effect(feature_dir: Path, baseline_sha: str):
    """run_command side_effect that simulates a target carrying the baseline.

    Every git command returns ``(0, baseline_sha, "")`` EXCEPT ``git show
    <target>:kitty-specs/<slug>/meta.json``, which returns the committed
    target meta.json with ``baseline_merge_commit`` populated. This lets the
    full merge flow exercise ``_assert_baseline_merge_commit_on_target``
    without a real git history.
    """
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    meta["baseline_merge_commit"] = baseline_sha
    committed_meta_json = json.dumps(meta, sort_keys=True)

    def _side_effect(cmd, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        if (
            isinstance(cmd, (list, tuple))
            and len(cmd) >= 3
            and cmd[0] == "git"
            and cmd[1] == "show"
            and str(cmd[2]).endswith("meta.json")
        ):
            return (0, committed_meta_json, "")
        if (
            isinstance(cmd, (list, tuple))
            and len(cmd) >= 3
            and cmd[0] == "git"
            and cmd[1] == "show"
            and str(cmd[2]).endswith("status.events.jsonl")
        ):
            committed_events = "\n".join(
                json.dumps({"wp_id": wp_id, "to_lane": "done"})
                for wp_id in ("WP01", "WP02")
            )
            return (0, committed_events + "\n", "")
        return (0, baseline_sha, "")

    return _side_effect


class TestAssertMergedWpsReachedDoneAbsentLog:
    """Absent canonical log must fail cleanly, not crash post-integration."""

    def test_clean_exit_when_canonical_log_absent(self, tmp_path: Path) -> None:
        import typer

        from specify_cli.cli.commands.merge import _assert_merged_wps_reached_done
        from specify_cli.status import CanonicalStatusNotFoundError

        mission_slug = "068-no-canonical-log"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)

        with (
            patch(
                "specify_cli.merge.done_bookkeeping.resolve_status_surface",
                return_value=feature_dir / "status.json",
            ),
            patch(
                "specify_cli.status.get_wp_lane",
                side_effect=CanonicalStatusNotFoundError("no event log"),
            ),
            # Deliberate typer.Exit, NOT an uncaught CanonicalStatusNotFoundError.
            pytest.raises(typer.Exit),
        ):
            _assert_merged_wps_reached_done(tmp_path, mission_slug, ["WP01"])


class TestBaselineMergeCommitMetadata:
    def test_record_baseline_merge_commit_fills_blank_field(self, tmp_path: Path) -> None:
        mission_slug = "068-baseline-meta"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        _write_meta(feature_dir, mission_slug, baseline_merge_commit=None)

        result = _record_baseline_merge_commit(feature_dir, "abc123def456")

        assert result == feature_dir / "meta.json"
        data = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
        assert data["baseline_merge_commit"] == "abc123def456"

    def test_record_baseline_merge_commit_preserves_existing_value(self, tmp_path: Path) -> None:
        mission_slug = "068-baseline-preserve"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        _write_meta(feature_dir, mission_slug, baseline_merge_commit="already-set")

        result = _record_baseline_merge_commit(feature_dir, "new-value")

        data = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
        # The existing baseline_merge_commit is still preserved advance-only (#3311)...
        assert data["baseline_merge_commit"] == "already-set"
        # ...but the coupled merged_at writer (#4090) fills the absent completion
        # marker in the same call, so the function reports the meta path it wrote
        # (the return contract changed from None → the written path).
        assert result == feature_dir / "meta.json"
        assert "merged_at" in data


# ---------------------------------------------------------------------------
# FR-019 unit test — safe_commit is called after _mark_wp_merged_done loop
# ---------------------------------------------------------------------------


class TestSafeCommitCalledAfterMarkDoneLoop:
    """FR-019: safe_commit is called with the correct args after the mark-done loop."""

    def test_safe_commit_is_called_with_correct_files(self, tmp_path: Path) -> None:
        mission_slug = "068-test-sc"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        _write_meta(feature_dir, mission_slug, mission_id=None)
        _seed_mission_branch(tmp_path, mission_slug)
        # Materialize the status pair on disk BEFORE the merge, matching what the
        # real (unmocked) `_mark_wp_merged_done` durably writes to the target
        # checkout in production. This test mocks `_mark_wp_merged_done` itself
        # (it only asserts the `commit_merge_bookkeeping` call args, not the
        # done-transition mechanics — that E2E path is covered by
        # `test_done_events_committed_to_git` below), so the on-disk artifact has
        # to be seeded directly or `_phase_commit_and_assert`'s existence filter
        # (added for the optional birth-cutover/baseline meta paths) legitimately
        # drops a path that was never materialized in this fixture.
        _seed_status_event(feature_dir, mission_slug, "WP01", "done")
        from specify_cli.status.reducer import materialize

        materialize(feature_dir)

        manifest = MagicMock()
        manifest.target_branch = "main"
        manifest.mission_branch = f"kitty/mission-{mission_slug}"

        lane_a = MagicMock()
        lane_a.lane_id = "lane-a"
        lane_a.wp_ids = ["WP01"]
        manifest.lanes = [lane_a]

        lane_result = MagicMock()
        lane_result.success = True
        lane_result.errors = []

        mission_result = MagicMock()
        mission_result.success = True
        mission_result.commit = "abc1234"
        mission_result.errors = []

        with (
            patch("specify_cli.merge.executor.require_lanes_json", return_value=manifest),
            patch("specify_cli.merge.resolve.load_state", return_value=None),
            patch("specify_cli.merge.done_bookkeeping.save_state"),
            patch("specify_cli.merge.executor.get_main_repo_root", return_value=tmp_path),
            patch("specify_cli.merge.executor._enforce_target_branch_sync_preflight"),
            patch("specify_cli.merge.executor._pre_mutation_safety_preflight"),
            patch("specify_cli.merge.executor.guarded_worktree_remove"),
            patch("specify_cli.status.get_wp_lane", return_value="done"),
            patch("specify_cli.lanes.merge.consolidate_lane_into_mission", return_value=lane_result),
            patch("specify_cli.lanes.merge.integrate_mission_into_target", return_value=mission_result),
            patch("specify_cli.merge.done_bookkeeping._mark_wp_merged_done"),
            patch("specify_cli.merge.executor.commit_merge_bookkeeping", return_value=True) as mock_safe_commit,
            patch("specify_cli.post_merge.stale_assertions.run_check") as mock_run_check,
            patch("specify_cli.policy.merge_gates.evaluate_merge_gates") as mock_gates,
            patch("specify_cli.policy.config.load_policy_config") as mock_policy,
            patch("specify_cli.merge.executor.run_command", return_value=(0, "abc123", "")),
            patch("specify_cli.merge.executor.has_remote", return_value=False),
            patch("specify_cli.merge.executor.cleanup_merge_workspace"),
            patch("specify_cli.merge.executor.clear_state"),
            patch("specify_cli.merge.state.MergeState"),
        ):
            stale_report = MagicMock()
            stale_report.findings = []
            mock_run_check.return_value = stale_report

            gate_eval = MagicMock()
            gate_eval.overall_pass = True
            gate_eval.gates = []
            mock_gates.return_value = gate_eval

            policy = MagicMock()
            policy.merge_gates = []
            mock_policy.return_value = policy

            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=mission_slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
            )

        # Verify safe_commit was called once with the correct files
        mock_safe_commit.assert_called_once()
        kwargs = mock_safe_commit.call_args.kwargs
        assert kwargs["repo_root"] == tmp_path
        assert kwargs["worktree_root"] == tmp_path
        assert kwargs["branch"] == "main"
        assert mission_slug in kwargs["message"]
        # Verify both status files are in the payload
        files = kwargs["paths"]
        file_names = [f.name for f in files]
        assert "status.events.jsonl" in file_names
        assert "status.json" in file_names

    def test_merge_commits_baseline_merge_commit_metadata(self, tmp_path: Path) -> None:
        mission_slug = "068-test-baseline"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        _write_meta(feature_dir, mission_slug, baseline_merge_commit=None)
        _seed_mission_branch(tmp_path, mission_slug)
        # #4764/T007: _assert_mission_terminal_ready now hard-refuses a mission
        # with an unapproved WP before any mutation. This test's intent is the
        # baseline_merge_commit metadata write, not readiness, so seed WP01 as
        # done (mirrors test_safe_commit_is_called_with_correct_files above)
        # so the merge proceeds far enough to exercise the code under test.
        _seed_status_event(feature_dir, mission_slug, "WP01", "done")
        from specify_cli.status.reducer import materialize as _materialize

        _materialize(feature_dir)

        manifest = MagicMock()
        manifest.target_branch = "main"
        manifest.mission_branch = f"kitty/mission-{mission_slug}"

        lane_a = MagicMock()
        lane_a.lane_id = "lane-a"
        lane_a.wp_ids = ["WP01"]
        manifest.lanes = [lane_a]

        lane_result = MagicMock(success=True, errors=[])
        mission_result = MagicMock(success=True, commit="merged123", errors=[])

        with ExitStack() as stack:
            stack.enter_context(patch("specify_cli.merge.executor.require_lanes_json", return_value=manifest))
            stack.enter_context(patch("specify_cli.merge.resolve.load_state", return_value=None))
            stack.enter_context(patch("specify_cli.merge.done_bookkeeping.save_state"))
            stack.enter_context(patch("specify_cli.merge.executor.get_main_repo_root", return_value=tmp_path))
            stack.enter_context(patch("specify_cli.merge.executor._enforce_target_branch_sync_preflight"))
            stack.enter_context(patch("specify_cli.status.get_wp_lane", return_value="done"))
            stack.enter_context(patch("specify_cli.lanes.merge.consolidate_lane_into_mission", return_value=lane_result))
            stack.enter_context(patch("specify_cli.lanes.merge.integrate_mission_into_target", return_value=mission_result))
            stack.enter_context(patch("specify_cli.merge.done_bookkeeping._mark_wp_merged_done"))
            # WP10 (#2057): the bake (ordering seam) + the done-on-target assert
            # (done_bookkeeping seam) run real git against an unseeded branch in
            # this unit test; patch them at their seam homes.
            stack.enter_context(patch("specify_cli.merge.executor._bake_mission_number_into_mission_branch"))
            stack.enter_context(patch("specify_cli.merge.executor._assert_merged_wps_done_on_target"))
            mock_safe_commit = stack.enter_context(
                patch("specify_cli.merge.executor.commit_merge_bookkeeping", return_value=True)
            )
            mock_run_check = stack.enter_context(patch("specify_cli.post_merge.stale_assertions.run_check"))
            mock_gates = stack.enter_context(patch("specify_cli.policy.merge_gates.evaluate_merge_gates"))
            mock_policy = stack.enter_context(patch("specify_cli.policy.config.load_policy_config"))
            stack.enter_context(
                patch(
                    "specify_cli.merge.executor.run_command",
                    side_effect=_baseline_run_command_side_effect(feature_dir, "base123"),
                )
            )
            stack.enter_context(
                patch(
                    "specify_cli.merge.baseline.run_command",
                    side_effect=_baseline_run_command_side_effect(feature_dir, "base123"),
                )
            )
            stack.enter_context(patch("specify_cli.merge.executor.has_remote", return_value=False))
            stack.enter_context(patch("specify_cli.merge.executor.cleanup_merge_workspace"))
            stack.enter_context(patch("specify_cli.merge.executor.clear_state"))
            stack.enter_context(patch("specify_cli.merge.state.MergeState"))

            stale_report = MagicMock()
            stale_report.findings = []
            mock_run_check.return_value = stale_report

            gate_eval = MagicMock()
            gate_eval.overall_pass = True
            gate_eval.gates = []
            mock_gates.return_value = gate_eval

            policy = MagicMock()
            policy.merge_gates = []
            mock_policy.return_value = policy

            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=mission_slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
            )

        data = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
        assert data["baseline_merge_commit"] == "base123"
        files = mock_safe_commit.call_args.kwargs["paths"]
        assert feature_dir / "meta.json" in files


class TestMergeDoneTransitions:
    def test_mark_wp_merged_done_uses_lightweight_emit_path(self, tmp_path: Path) -> None:
        mission_slug = "068-test-lightweight"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        _write_meta(feature_dir, mission_slug, mission_id=None)
        _write_wp_file(tasks_dir, "WP01")

        from specify_cli.status import CurrentWpState, Lane

        with (
            # _mark_wp_merged_done reads the current lane via
            # read_current_wp_state_transactional (coord-aware, #1772/FSM); patch
            # it so the WP reads as approved and the lightweight done-emit fires.
            patch(
                "specify_cli.coordination.status_transition.read_current_wp_state_transactional",
                return_value=CurrentWpState(Lane.APPROVED, "reviewer-1", None),
            ),
            patch("specify_cli.cli.commands.merge._has_transition_to", return_value=False),
            patch("specify_cli.coordination.status_transition.emit_status_transition_transactional") as mock_emit,
        ):
            _mark_wp_merged_done(tmp_path, mission_slug, "WP01", "main")

        mock_emit.assert_called_once()
        kwargs = mock_emit.call_args.kwargs
        assert kwargs["ensure_sync_daemon"] is False

    def test_safe_commit_called_before_worktree_removal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-019: safe_commit must precede any worktree removal step."""
        mission_slug = "068-test-order"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        _write_meta(feature_dir, mission_slug, mission_id=None)
        _seed_mission_branch(tmp_path, mission_slug)
        # #4764/T007: seed WP01 as done so _assert_mission_terminal_ready lets
        # the merge proceed far enough to exercise the safe_commit/worktree
        # ordering under test (this test's actual intent, per FR-019).
        _seed_status_event(feature_dir, mission_slug, "WP01", "done")
        from specify_cli.status.reducer import materialize as _materialize

        _materialize(feature_dir)

        call_order: list[str] = []

        manifest = MagicMock()
        manifest.target_branch = "main"
        manifest.mission_branch = f"kitty/mission-{mission_slug}"

        lane_a = MagicMock()
        lane_a.lane_id = "lane-a"
        lane_a.wp_ids = ["WP01"]
        wt_path = tmp_path / ".worktrees" / f"{mission_slug}-lane-a"
        wt_path.mkdir(parents=True)
        manifest.lanes = [lane_a]

        lane_result = MagicMock()
        lane_result.success = True
        lane_result.errors = []

        mission_result = MagicMock()
        mission_result.success = True
        mission_result.commit = "abc1234"
        mission_result.errors = []

        def record_safe_commit(**kwargs):  # noqa: ANN001
            call_order.append("safe_commit")
            return True

        def record_worktree_remove(cmd, **kwargs):  # noqa: ANN001
            if "worktree" in cmd and "remove" in cmd:
                call_order.append("worktree_remove")
            return (0, "", "")

        monkeypatch.setattr(
            "specify_cli.merge.executor._paths_have_status_changes",
            lambda _repo_root, _paths: True,
        )

        with (
            patch("specify_cli.merge.executor.require_lanes_json", return_value=manifest),
            patch("specify_cli.merge.resolve.load_state", return_value=None),
            patch("specify_cli.merge.done_bookkeeping.save_state"),
            patch("specify_cli.merge.executor.get_main_repo_root", return_value=tmp_path),
            patch("specify_cli.merge.executor._enforce_target_branch_sync_preflight"),
            patch("specify_cli.merge.executor._pre_mutation_safety_preflight"),
            patch("specify_cli.merge.executor.guarded_worktree_remove"),
            patch("specify_cli.status.get_wp_lane", return_value="done"),
            patch("specify_cli.lanes.merge.consolidate_lane_into_mission", return_value=lane_result),
            patch("specify_cli.lanes.merge.integrate_mission_into_target", return_value=mission_result),
            patch("specify_cli.merge.done_bookkeeping._mark_wp_merged_done"),
            patch("specify_cli.merge.executor.commit_merge_bookkeeping", side_effect=record_safe_commit),
            patch("specify_cli.post_merge.stale_assertions.run_check") as mock_run_check,
            patch("specify_cli.policy.merge_gates.evaluate_merge_gates") as mock_gates,
            patch("specify_cli.policy.config.load_policy_config") as mock_policy,
            patch("specify_cli.merge.executor.run_command", side_effect=record_worktree_remove),
            patch("specify_cli.merge.executor.has_remote", return_value=False),
            patch("specify_cli.merge.executor.cleanup_merge_workspace"),
            patch("specify_cli.merge.executor.clear_state"),
            patch("specify_cli.merge.state.MergeState"),
        ):
            stale_report = MagicMock()
            stale_report.findings = []
            mock_run_check.return_value = stale_report

            gate_eval = MagicMock()
            gate_eval.overall_pass = True
            gate_eval.gates = []
            mock_gates.return_value = gate_eval

            policy = MagicMock()
            policy.merge_gates = []
            mock_policy.return_value = policy

            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=mission_slug,
                push=False,
                delete_branch=False,
                remove_worktree=True,  # enable worktree removal to test ordering
                strategy=MergeStrategy.SQUASH,
            )

        # safe_commit must appear before any worktree_remove in the call order
        if "worktree_remove" in call_order:
            sc_idx = call_order.index("safe_commit")
            wr_idx = call_order.index("worktree_remove")
            assert sc_idx < wr_idx, (
                f"safe_commit (idx={sc_idx}) must precede worktree_remove (idx={wr_idx}). "
                "FR-019: persist events before destroying worktree."
            )


# ---------------------------------------------------------------------------
# FR-020 — done events committed to git (the canonical regression test)
# ---------------------------------------------------------------------------


class TestDoneEventsCommittedToGit:
    """FR-020: after _run_lane_based_merge, done events are in git history at HEAD.

    Uses git show HEAD: — the mechanically-correct assertion.
    Does NOT use git reset --hard HEAD (that would be a no-op).
    """

    def test_done_events_committed_to_git(self, tmp_path: Path) -> None:
        """FR-019/FR-020 regression: safe_commit must persist status.events.jsonl to git."""
        mission_slug = "068-done-events-test"
        wps = ["WP01", "WP02"]

        # Set up a real git repo
        _init_git_repo(tmp_path)

        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        _write_meta(feature_dir, mission_slug, mission_id=None)
        tasks_dir = feature_dir / "tasks"

        for wp_id in wps:
            _write_wp_file(tasks_dir, wp_id)

        # Commit the initial feature directory to git (without status files)
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-m", "initial feature"],
            cwd=tmp_path, check=True, capture_output=True,
        )
        _seed_mission_branch(tmp_path, mission_slug)

        # Seed event log entries (approved state for each WP, as they would be pre-merge)
        for wp_id in wps:
            _seed_status_event(feature_dir, mission_slug, wp_id, "approved")

        # Materialize status.json
        from specify_cli.status.reducer import materialize
        materialize(feature_dir)

        manifest = MagicMock()
        manifest.target_branch = "main"
        manifest.mission_branch = f"kitty/mission-{mission_slug}"

        lane_a = MagicMock()
        lane_a.lane_id = "lane-a"
        lane_a.wp_ids = ["WP01"]

        lane_b = MagicMock()
        lane_b.lane_id = "lane-b"
        lane_b.wp_ids = ["WP02"]

        manifest.lanes = [lane_a, lane_b]

        lane_result = MagicMock()
        lane_result.success = True
        lane_result.errors = []

        mission_result = MagicMock()
        mission_result.success = True
        mission_result.commit = "deadbeef"
        mission_result.errors = []

        with (
            patch("specify_cli.merge.executor.require_lanes_json", return_value=manifest),
            patch("specify_cli.merge.resolve.load_state", return_value=None),
            patch("specify_cli.merge.done_bookkeeping.save_state"),
            patch("specify_cli.merge.executor.get_main_repo_root", return_value=tmp_path),
            patch("specify_cli.lanes.merge.consolidate_lane_into_mission", return_value=lane_result),
            patch("specify_cli.lanes.merge.integrate_mission_into_target", return_value=mission_result),
            patch("specify_cli.post_merge.stale_assertions.run_check") as mock_run_check,
            patch("specify_cli.policy.merge_gates.evaluate_merge_gates") as mock_gates,
            patch("specify_cli.policy.config.load_policy_config") as mock_policy,
            patch("specify_cli.merge.executor.run_command", return_value=(0, "abc123", "")),
            patch("specify_cli.merge.executor.has_remote", return_value=False),
            patch("specify_cli.merge.executor.cleanup_merge_workspace"),
            patch("specify_cli.merge.executor.clear_state"),
            patch("specify_cli.merge.state.MergeState"),
            patch("specify_cli.status.emit._saas_fan_out"),
        ):
            stale_report = MagicMock()
            stale_report.findings = []
            mock_run_check.return_value = stale_report

            gate_eval = MagicMock()
            gate_eval.overall_pass = True
            gate_eval.gates = []
            mock_gates.return_value = gate_eval

            policy = MagicMock()
            policy.merge_gates = []
            mock_policy.return_value = policy

            # Run the full merge
            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=mission_slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
            )

        # FR-020: read status.events.jsonl from git history, NOT from the working tree
        result = subprocess.run(
            ["git", "show", f"HEAD:kitty-specs/{mission_slug}/status.events.jsonl"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )
        events = [
            json.loads(line)
            for line in result.stdout.splitlines()
            if line.strip()
        ]
        done_wps = {e["wp_id"] for e in events if e.get("to_lane") == "done"}

        assert done_wps == set(wps), (
            f"Expected done events for every merged WP in git history. "
            f"Got {done_wps}, expected {set(wps)}. "
            "This regression means the FR-019 safe_commit step was missed or failed."
        )
        # Explicitly: do NOT use git reset --hard HEAD here — that would be a no-op
        # (the file is already at HEAD) and proves nothing about the commit having occurred.

    def test_modern_coord_done_events_land_on_target_history(self, tmp_path: Path) -> None:
        """Modern coord topology: target branch must contain done after merge."""
        mid8 = "01KMODER"
        mission_slug = f"068-modern-done-events-{mid8}"
        mission_id = f"{mid8}NSTATUSSURFACE0000000"
        wps = ["WP01", "WP02"]

        _init_git_repo(tmp_path)

        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        coord_branch = f"kitty/mission-{mission_slug}"
        _write_meta(
            feature_dir,
            mission_slug,
            mission_id=mission_id,
            mid8=mid8,
            coordination_branch=coord_branch,
        )
        tasks_dir = feature_dir / "tasks"
        for wp_id in wps:
            _write_wp_file(tasks_dir, wp_id)
            _seed_status_event(feature_dir, mission_slug, wp_id, "approved")

        from specify_cli.status.reducer import materialize

        materialize(feature_dir)
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-m", "initial modern feature"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "branch", coord_branch], cwd=tmp_path, check=True, capture_output=True)

        manifest = MagicMock()
        manifest.target_branch = "main"
        manifest.mission_branch = coord_branch
        lane_a = MagicMock()
        lane_a.lane_id = "lane-a"
        lane_a.wp_ids = ["WP01"]
        lane_b = MagicMock()
        lane_b.lane_id = "lane-b"
        lane_b.wp_ids = ["WP02"]
        manifest.lanes = [lane_a, lane_b]

        lane_result = MagicMock()
        lane_result.success = True
        lane_result.errors = []

        def _integrate_mission_into_target(*_args, **_kwargs):  # noqa: ANN002, ANN003
            subprocess.run(["git", "checkout", "main"], cwd=tmp_path, check=True, capture_output=True)
            subprocess.run(
                ["git", "-c", "commit.gpgsign=false", "merge", "--no-ff", coord_branch, "-m", "merge mission"],
                cwd=tmp_path,
                check=True,
                capture_output=True,
            )
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
            result = MagicMock()
            result.success = True
            result.errors = []
            result.commit = commit
            return result

        with (
            patch("specify_cli.merge.executor.require_lanes_json", return_value=manifest),
            patch("specify_cli.merge.resolve.load_state", return_value=None),
            patch("specify_cli.merge.done_bookkeeping.save_state"),
            patch("specify_cli.merge.executor.get_main_repo_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.merge._bake_mission_number_into_mission_branch"),
            patch("specify_cli.lanes.merge.consolidate_lane_into_mission", return_value=lane_result),
            patch("specify_cli.lanes.merge.integrate_mission_into_target", side_effect=_integrate_mission_into_target),
            patch("specify_cli.post_merge.stale_assertions.run_check") as mock_run_check,
            patch("specify_cli.policy.merge_gates.evaluate_merge_gates") as mock_gates,
            patch("specify_cli.policy.config.load_policy_config") as mock_policy,
            patch("specify_cli.merge.executor.has_remote", return_value=False),
            patch("specify_cli.merge.executor.cleanup_merge_workspace"),
            patch("specify_cli.merge.executor.clear_state"),
            patch("specify_cli.status.emit._saas_fan_out"),
        ):
            stale_report = MagicMock()
            stale_report.findings = []
            mock_run_check.return_value = stale_report

            gate_eval = MagicMock()
            gate_eval.overall_pass = True
            gate_eval.gates = []
            mock_gates.return_value = gate_eval

            policy = MagicMock()
            policy.merge_gates = []
            mock_policy.return_value = policy

            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=mission_slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
            )

        result = subprocess.run(
            ["git", "show", f"main:kitty-specs/{mission_slug}/status.events.jsonl"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )
        events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        done_wps = {event["wp_id"] for event in events if event.get("to_lane") == "done"}
        assert done_wps == set(wps)
