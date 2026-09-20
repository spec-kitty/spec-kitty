"""WP01/T002 — ``spec-kitty merge --resume`` is resumable and bounded.

Pins two contracts on resume:

1. **Idempotence**: when the lane branches are already fully integrated into the
   mission branch (``git rev-list --count <lane> ^<mission>`` == "0"), re-running
   the merge does NOT re-call the per-WP done-recording pipeline and does NOT
   re-merge any lane.  This is what protects an operator who ran merge to
   completion and then unintentionally re-runs it: nothing should happen.
   (FR-037: the skip gate is tree-state, not the ``completed_wps`` proxy.)

2. **Resume after interruption**: when state shows partial progress, the
   resumed pass picks up exactly the remaining WPs and skips the completed
   ones — both at the lane-merge step and the mark-done step.

3. **Bounded**: the resumed run completes well within the NFR-005 30s budget
   for a 10-lane fixture (with the heavy work mocked out, this is also the
   default tolerance — we assert it is not pathologically slow).
"""

from __future__ import annotations

# FR-037 import-order guard: ensure the status sub-package is initialised
# before merge.py's deferred imports fire.  Without this, collection-order
# shifts (e.g. a new test file added in the same suite) can trigger a
# ``BookkeepingTransaction`` partially-initialised-module cycle.
import specify_cli.status  # noqa: F401  (side-effect: module registration)

import contextlib
import json
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.cli.commands.merge import _run_lane_based_merge
from specify_cli.merge.config import MergeStrategy
from specify_cli.merge.state import MergeState, save_state
from tests._perf_helpers import assert_timing_budget
from tests.lane_test_utils import write_mission_meta


pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)])
    _run(["git", "-C", str(repo), "config", "user.email", "test@test.com"])
    _run(["git", "-C", str(repo), "config", "user.name", "Test"])
    _run(["git", "-C", str(repo), "config", "commit.gpgsign", "false"])
    (repo / "README.md").write_text("init\n")
    _run(["git", "-C", str(repo), "add", "."])
    _run(["git", "-C", str(repo), "commit", "-m", "init"])


def _make_manifest(slug: str, lane_count: int = 10) -> MagicMock:
    manifest = MagicMock()
    manifest.target_branch = "main"
    manifest.mission_branch = f"kitty/mission-{slug}"
    lanes = []
    for i in range(lane_count):
        lane = MagicMock()
        lane.lane_id = f"lane-{chr(ord('a') + i)}"
        lane.wp_ids = [f"WP{i+1:02d}"]
        lanes.append(lane)
    manifest.lanes = lanes
    return manifest


def _write_done_events(feature_dir: Path, wp_ids: list[str]) -> None:
    _write_status_events(feature_dir, dict.fromkeys(wp_ids, "done"))


def _write_status_events(feature_dir: Path, wp_to_lane: dict[str, str]) -> None:
    """Seed each ``wp_id`` at ``to_lane`` on the real event log (#4764/T007).

    ``_assert_mission_terminal_ready`` reads ``status.events.jsonl`` directly
    and refuses the merge before any mutation when a WP is not at
    ``approved``/``done`` (or absent from the log entirely). These tests
    exercise the resume/idempotence bookkeeping, not readiness, so every WP
    the fixture references must be seeded acceptable.
    """
    events = []
    for wp_id, to_lane in wp_to_lane.items():
        events.append(
            json.dumps(
                {
                    "event_id": f"01TEST{wp_id}",
                    "mission_slug": feature_dir.name,
                    "wp_id": wp_id,
                    "from_lane": "in_review" if to_lane == "approved" else "approved",
                    "to_lane": to_lane,
                    "at": "2026-04-06T12:00:00+00:00",
                    "actor": "merge",
                    "force": False,
                    "execution_mode": "worktree",
                },
                sort_keys=True,
            )
        )
    (feature_dir / "status.events.jsonl").write_text("\n".join(events) + "\n", encoding="utf-8")


def _patches(
    *,
    tmp_path: Path,
    manifest: MagicMock,
    initial_state: MergeState | None,
    mark_done_calls: list[str],
    lane_merge_calls: list[str],
    integrated_lane_ids: frozenset[str] = frozenset(),
):
    lane_result = MagicMock()
    lane_result.success = True
    lane_result.errors = []

    mission_result = MagicMock()
    mission_result.success = True
    mission_result.commit = "abc1234"
    mission_result.errors = []

    def fake_run_command(cmd, *args, **kwargs):  # noqa: ANN001
        if "merge-base" in cmd:
            return (0, "abc123\n", "")
        # Modern mission (post-083 ULID identity): the baseline-capture phase
        # reads ``git rev-parse <target>`` to anchor ``baseline_merge_commit``.
        # Return a realistic 40-char SHA so record_baseline_merge_commit has a
        # non-empty baseline instead of hard-failing the modern-mission invariant.
        if "rev-parse" in cmd:
            return (0, "d4f8a1c2e6b09f37a5c1e8b2f4a6d0c9e3b7f1a2\n", "")
        # FR-037: model the real ``git rev-list --count <lane> ^<mission>``
        # integration check.  Return "0" (zero commits ahead = already
        # integrated) for any lane branch whose lane-id is in
        # ``integrated_lane_ids``; return "" (non-zero / unknown) otherwise so
        # that un-integrated lanes are correctly attempted.
        if "rev-list" in cmd and "--count" in cmd:
            lane_branch_arg = cmd[3] if len(cmd) > 3 else ""
            if any(lid in lane_branch_arg for lid in integrated_lane_ids):
                return (0, "0", "")
        return (0, "", "")

    def fake_lane_merge(repo_root, mission_slug, lane_id, lanes_manifest):  # noqa: ANN001
        lane_merge_calls.append(lane_id)
        return lane_result

    def fake_mark_done(repo_root, mission_slug, wp_id, target_branch):  # noqa: ANN001
        mark_done_calls.append(wp_id)

    return [
        patch("specify_cli.merge.executor.require_lanes_json", return_value=manifest),
        patch("specify_cli.merge.resolve.load_state", return_value=initial_state),
        patch("specify_cli.merge.done_bookkeeping.save_state"),
        patch("specify_cli.merge.executor.get_main_repo_root", return_value=tmp_path),
        patch("specify_cli.merge.executor.require_no_sparse_checkout"),
        patch("specify_cli.lanes.merge.consolidate_lane_into_mission", side_effect=fake_lane_merge),
        patch("specify_cli.lanes.merge.integrate_mission_into_target", return_value=mission_result),
        patch("specify_cli.merge.done_bookkeeping._mark_wp_merged_done", side_effect=fake_mark_done),
        patch("specify_cli.merge.executor.commit_merge_bookkeeping"),
        patch("specify_cli.merge.done_bookkeeping._assert_merged_wps_reached_done"),
        patch("specify_cli.post_merge.stale_assertions.run_check"),
        patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        patch("specify_cli.policy.config.load_policy_config"),
        patch("specify_cli.merge.executor.run_command", side_effect=fake_run_command),
        # WP10 (#2057): the lane-integration check (_lane_already_integrated)
        # runs in the git_probes seam; spy it with the same fake git.
        patch("specify_cli.merge.git_probes.run_command", side_effect=fake_run_command),
        patch("specify_cli.merge.executor.has_remote", return_value=False),
        patch("specify_cli.merge.executor.cleanup_merge_workspace"),
        patch("specify_cli.merge.executor.clear_state"),
        patch("specify_cli.merge.executor._bake_mission_number_into_mission_branch"),
        # WP10 (#2057): mission-branch preflight moved to the preflight seam;
        # appended last to keep positional mock indices stable.
        patch("specify_cli.merge.executor._check_mission_branch", return_value=(True, None)),
        # WP10 (#2057): target-history asserts moved to the done_bookkeeping /
        # baseline seams; the executor binds them — patch there.
        patch("specify_cli.merge.executor._assert_merged_wps_done_on_target"),
        patch("specify_cli.merge.executor._assert_baseline_merge_commit_on_target"),
    ]


def _wire_default_returns(stack):
    """Configure the policy/gate/run_check mocks that several patches need."""
    # Indices match _patches() above; pull the named ones out.
    # Simpler: walk the active mocks looking for the right names.
    for m in stack:
        target = getattr(m, "_mock_name", "") or ""
        if "run_check" in target or "evaluate_merge_gates" in target or "load_policy_config" in target:
            pass


class TestMergeResumeIdempotence:
    """When state shows full completion, re-running merge is a no-op for per-WP work."""

    def test_resume_full_state_is_no_op_for_mark_done(self, tmp_path: Path) -> None:
        slug = "test-resume-idempotent"
        _init_git_repo(tmp_path)
        feature_dir = tmp_path / "kitty-specs" / slug
        feature_dir.mkdir(parents=True)
        # Modernize the mission (3.2.x identity) so the mark-done coordination
        # write resolves a non-empty mid8 instead of tripping the #2091 guard.
        write_mission_meta(feature_dir)

        manifest = _make_manifest(slug, lane_count=3)
        _write_done_events(feature_dir, ["WP01", "WP02", "WP03"])

        # State says all three WPs are completed already.
        existing = MergeState(
            mission_id=slug,
            mission_slug=slug,
            target_branch="main",
            wp_order=["WP01", "WP02", "WP03"],
            completed_wps=["WP01", "WP02", "WP03"],
        )

        mark_done_calls: list[str] = []
        lane_merge_calls: list[str] = []

        # FR-037: all three lanes are already integrated into the mission branch
        # (tree-state gate, not the completed_wps proxy).
        patches = _patches(
            tmp_path=tmp_path,
            manifest=manifest,
            initial_state=existing,
            mark_done_calls=mark_done_calls,
            lane_merge_calls=lane_merge_calls,
            integrated_lane_ids=frozenset({"lane-a", "lane-b", "lane-c"}),
        )

        with contextlib.ExitStack() as stack:
            mocks = [stack.enter_context(p) for p in patches]
            # Wire default returns for run_check/policy/gates.
            stale_report = MagicMock()
            stale_report.findings = []
            mocks[10].return_value = stale_report  # run_check

            gate_eval = MagicMock()
            gate_eval.overall_pass = True
            gate_eval.gates = []
            mocks[11].return_value = gate_eval  # evaluate_merge_gates

            policy = MagicMock()
            policy.merge_gates = []
            mocks[12].return_value = policy  # load_policy_config

            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
            )

        # Idempotence contract: every lane branch is already integrated
        # (rev-list returns "0") so _mark_wp_merged_done MUST NOT be called.
        assert mark_done_calls == [], (
            f"FR-002/NFR-005 idempotence regression: re-running merge with all "
            f"lanes already integrated re-marked {mark_done_calls!r}. "
            "The per-WP done pipeline must skip already-completed WPs."
        )

        # Lane-merge step must also be skipped for every lane (tree-state gate).
        assert lane_merge_calls == [], (
            f"Idempotence regression at the lane step: lanes "
            f"{lane_merge_calls!r} were re-merged even though their rev-list "
            "count was 0 (already integrated). See FR-037 _lane_already_integrated."
        )


class TestMergeResumeAfterInterruption:
    """When state shows partial completion, the resume pass picks up the rest only."""

    def test_resume_skips_completed_marks_remaining(self, tmp_path: Path) -> None:
        slug = "test-resume-partial"
        _init_git_repo(tmp_path)
        feature_dir = tmp_path / "kitty-specs" / slug
        feature_dir.mkdir(parents=True)
        # Modernize the mission (3.2.x identity) so the mark-done coordination
        # write resolves a non-empty mid8 instead of tripping the #2091 guard.
        write_mission_meta(feature_dir)

        manifest = _make_manifest(slug, lane_count=3)
        # WP01 already done; WP02/WP03 approved (real pre-merge shape) so the
        # merge-ready precondition (#4764/T007) lets the resume proceed.
        _write_status_events(
            feature_dir, {"WP01": "done", "WP02": "approved", "WP03": "approved"}
        )
        # WP01 completed; WP02 and WP03 remaining.
        existing = MergeState(
            mission_id=slug,
            mission_slug=slug,
            target_branch="main",
            wp_order=["WP01", "WP02", "WP03"],
            completed_wps=["WP01"],
        )

        mark_done_calls: list[str] = []
        lane_merge_calls: list[str] = []

        # FR-037: lane-a is already integrated into the mission branch
        # (rev-list returns "0"); lane-b and lane-c are not yet integrated.
        patches = _patches(
            tmp_path=tmp_path,
            manifest=manifest,
            initial_state=existing,
            mark_done_calls=mark_done_calls,
            lane_merge_calls=lane_merge_calls,
            integrated_lane_ids=frozenset({"lane-a"}),
        )

        with contextlib.ExitStack() as stack:
            mocks = [stack.enter_context(p) for p in patches]
            stale_report = MagicMock()
            stale_report.findings = []
            mocks[10].return_value = stale_report

            gate_eval = MagicMock()
            gate_eval.overall_pass = True
            gate_eval.gates = []
            mocks[11].return_value = gate_eval

            policy = MagicMock()
            policy.merge_gates = []
            mocks[12].return_value = policy

            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
            )

        # WP01 already done — must not be re-marked.
        assert "WP01" not in mark_done_calls, (
            f"Resume re-marked already-completed WP01: {mark_done_calls!r}"
        )
        # WP02 + WP03 must be marked.
        assert "WP02" in mark_done_calls and "WP03" in mark_done_calls, (
            f"Resume failed to finish remaining WPs: {mark_done_calls!r}"
        )

        # Lane-a already integrated (rev-list "0") — must not be re-merged.
        assert "lane-a" not in lane_merge_calls, (
            f"Resume re-merged already-integrated lane-a: {lane_merge_calls!r}"
        )
        # Lane-b and lane-c have unintegrated code — must be merged.
        assert "lane-b" in lane_merge_calls and "lane-c" in lane_merge_calls


def _run_bounded_merge_fixture(tmp_path: Path) -> tuple[float, list[str], list[str]]:
    """Shared #4015-split fixture: resumed merge of a 10-lane fixture.

    Returns ``(elapsed_seconds, mark_done_calls, wp_ids)`` so the functional
    (all WPs marked done) and timing (NFR-005 30s budget) halves of the
    original mixed test can each assert their own concern without
    duplicating the mocked merge run's setup semantics.
    """
    slug = "test-resume-bounded"
    _init_git_repo(tmp_path)
    feature_dir = tmp_path / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    # Modernize the mission (3.2.x identity) so the mark-done coordination
    # write resolves a non-empty mid8 instead of tripping the #2091 guard.
    write_mission_meta(feature_dir)

    manifest = _make_manifest(slug, lane_count=10)
    wp_ids = [f"WP{i+1:02d}" for i in range(10)]
    # #4764/T007: seed every WP approved so the merge-ready precondition
    # lets this full-resume fixture proceed to the code under test.
    _write_status_events(feature_dir, dict.fromkeys(wp_ids, "approved"))

    existing = MergeState(
        mission_id=slug,
        mission_slug=slug,
        target_branch="main",
        wp_order=wp_ids,
        completed_wps=[],  # full re-run
    )

    mark_done_calls: list[str] = []
    lane_merge_calls: list[str] = []

    patches = _patches(
        tmp_path=tmp_path,
        manifest=manifest,
        initial_state=existing,
        mark_done_calls=mark_done_calls,
        lane_merge_calls=lane_merge_calls,
    )

    start = time.monotonic()
    with contextlib.ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in patches]
        stale_report = MagicMock()
        stale_report.findings = []
        mocks[10].return_value = stale_report

        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        mocks[11].return_value = gate_eval

        policy = MagicMock()
        policy.merge_gates = []
        mocks[12].return_value = policy

        _run_lane_based_merge(
            repo_root=tmp_path,
            mission_slug=slug,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
        )
    elapsed = time.monotonic() - start

    return elapsed, mark_done_calls, wp_ids


class TestMergeResumeBounded:
    """NFR-005: resumed merge of a 10-lane fixture is fast and completes all WPs."""

    def test_resume_completes_all_wps(self, tmp_path: Path) -> None:
        """Functional half of the #4015 split: all 10 WPs eventually marked done."""
        _elapsed, mark_done_calls, wp_ids = _run_bounded_merge_fixture(tmp_path)
        assert set(mark_done_calls) == set(wp_ids)

    @pytest.mark.performance
    def test_resume_completes_within_30s_budget(self, tmp_path: Path) -> None:
        """NFR-005 (#4015 split): resumed merge stays within the 30s budget."""
        elapsed, _mark_done_calls, _wp_ids = _run_bounded_merge_fixture(tmp_path)
        assert_timing_budget(elapsed, 30.0, name="elapsed")
