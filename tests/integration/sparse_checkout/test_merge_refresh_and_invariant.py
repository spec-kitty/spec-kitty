"""WP05/T006/T007 — post-merge refresh and invariant assertion.

FR-013: After a successful mission→target merge, the primary checkout must be
refreshed against HEAD so any paths git left out (e.g. legacy sparse-checkout)
are restored before the housekeeping commit runs.

FR-014: After the refresh, ``git status --porcelain`` in the primary checkout
MUST report at most the status files that the immediately-following
``safe_commit`` is about to persist. Any other divergence is an invariant
violation and must raise a merge-specific error.

These tests drive ``_run_lane_based_merge_locked`` indirectly through
``_run_lane_based_merge`` with the heavy merge helpers patched out, so we can
verify the two git subprocess calls (``git reset --hard HEAD`` and
``git status --porcelain``) fire between ``integrate_mission_into_target`` and
``safe_commit``.
"""

from __future__ import annotations

import contextlib
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from specify_cli.cli.commands.merge import _run_lane_based_merge
from specify_cli.merge.config import MergeStrategy


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


def _seed_wp_done(feature_dir: Path, mission_slug: str, wp_ids: list[str]) -> None:
    """Seed every ``wp_ids`` entry as ``done`` on the real event log (#4764/T007).

    ``_assert_mission_terminal_ready`` reads ``status.events.jsonl`` directly,
    not the ``get_wp_lane`` mock these fixtures patch elsewhere -- so a
    mission with no real event log now refuses before mutation. These tests
    exercise the post-merge refresh/invariant ordering, not readiness, so
    seed every WP as done to let the merge proceed far enough to reach it.
    """
    import json

    jsonl_path = feature_dir / "status.events.jsonl"
    with jsonl_path.open("a", encoding="utf-8") as handle:
        for index, wp_id in enumerate(wp_ids):
            event = {
                "actor": "test",
                "at": "2026-04-07T00:00:00+00:00",
                "event_id": f"TESTREFRESH{wp_id}{index:03d}",
                "evidence": None,
                "execution_mode": "direct_repo",
                "feature_slug": mission_slug,
                "force": True,
                "from_lane": "planned",
                "reason": "test seed",
                "review_ref": None,
                "to_lane": "done",
                "wp_id": wp_id,
            }
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    from specify_cli.status.reducer import materialize

    materialize(feature_dir)


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)])
    _run(["git", "-C", str(repo), "config", "user.email", "test@test.com"])
    _run(["git", "-C", str(repo), "config", "user.name", "Test"])
    _run(["git", "-C", str(repo), "config", "commit.gpgsign", "false"])
    (repo / "README.md").write_text("init\n")
    _run(["git", "-C", str(repo), "add", "."])
    _run(["git", "-C", str(repo), "commit", "-m", "init"])


class TestPostMergeRefreshAndInvariant:
    def _make_manifest(self, slug: str) -> MagicMock:
        manifest = MagicMock()
        manifest.target_branch = "main"
        manifest.mission_branch = f"kitty/mission-{slug}"
        lane_a = MagicMock()
        lane_a.lane_id = "lane-a"
        lane_a.wp_ids = ["WP01"]
        manifest.lanes = [lane_a]
        return manifest

    def test_refresh_and_invariant_run_in_correct_order(self, tmp_path: Path) -> None:
        """FR-013/FR-014: refresh happens before done events, then status check, then safe_commit."""
        slug = "test-refresh-invariant"
        _init_git_repo(tmp_path)

        feature_dir = tmp_path / "kitty-specs" / slug
        feature_dir.mkdir(parents=True)
        _seed_wp_done(feature_dir, slug, ["WP01"])

        manifest = self._make_manifest(slug)

        lane_result = MagicMock()
        lane_result.success = True
        lane_result.errors = []

        mission_result = MagicMock()
        mission_result.success = True
        mission_result.commit = "abc1234"
        mission_result.errors = []

        call_log: list[str] = []
        ordered_calls: list[tuple[str, tuple[object, ...]]] = []

        def fake_run_command(cmd, *args, **kwargs):  # noqa: ANN001
            ordered_calls.append(("run_command", tuple(cmd)))
            if "reset" in cmd and "--hard" in cmd and "HEAD" in cmd:
                call_log.append("hard_refresh")
                return (0, "", "")
            if "merge-base" in cmd:
                return (0, "abc123\n", "")
            return (0, "", "")

        def fake_raw_porcelain(repo_root):  # noqa: ANN001
            call_log.append("status_check")
            # Clean working tree — no offending lines. The post-merge invariant
            # reads porcelain RAW via _raw_porcelain_status.
            return (0, "")

        def fake_safe_commit(**kwargs):  # noqa: ANN001
            call_log.append("safe_commit")
            return True

        def fake_mark_wp_merged_done(*args, **kwargs):  # noqa: ANN001
            call_log.append("mark_done")

        stale_report = MagicMock()
        stale_report.findings = []
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        policy = MagicMock()
        policy.merge_gates = []

        patches = [
            patch("specify_cli.merge.executor.require_lanes_json", return_value=manifest),
            patch("specify_cli.merge.resolve.load_state", return_value=None),
            patch("specify_cli.merge.done_bookkeeping.save_state"),
            patch("specify_cli.merge.executor.get_main_repo_root", return_value=tmp_path),
            patch("specify_cli.merge.executor.require_no_sparse_checkout"),
            patch("specify_cli.status.get_wp_lane", return_value="done"),
            patch("specify_cli.lanes.merge.consolidate_lane_into_mission", return_value=lane_result),
            patch("specify_cli.lanes.merge.integrate_mission_into_target", return_value=mission_result),
            patch("specify_cli.merge.done_bookkeeping._mark_wp_merged_done", side_effect=fake_mark_wp_merged_done),
            patch("specify_cli.merge.executor.commit_merge_bookkeeping", side_effect=fake_safe_commit),
            patch("specify_cli.post_merge.stale_assertions.run_check", return_value=stale_report),
            patch("specify_cli.policy.merge_gates.evaluate_merge_gates", return_value=gate_eval),
            patch("specify_cli.policy.config.load_policy_config", return_value=policy),
            patch("specify_cli.merge.executor.run_command", side_effect=fake_run_command),
            # WP10 (#2057): the post-merge hard refresh runs in the git_probes
            # seam; spy it into the same call log so the ordering assertion sees it.
            patch("specify_cli.merge.git_probes.run_command", side_effect=fake_run_command),
            patch("specify_cli.merge.executor._raw_porcelain_status", side_effect=fake_raw_porcelain),
            patch("specify_cli.merge.executor._paths_have_status_changes", return_value=True),
            patch("specify_cli.merge.executor.has_remote", return_value=False),
            patch("specify_cli.merge.executor.cleanup_merge_workspace"),
            patch("specify_cli.merge.executor.clear_state"),
            patch("specify_cli.merge.state.MergeState"),
            patch("specify_cli.merge.executor._bake_mission_number_into_mission_branch"),
            patch("specify_cli.merge.executor._check_mission_branch", return_value=(True, None)),
            patch("specify_cli.merge.executor._assert_merged_wps_done_on_target"),
            patch("specify_cli.merge.executor._assert_baseline_merge_commit_on_target"),
        ]
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            _run_lane_based_merge(
                repo_root=tmp_path,
                mission_slug=slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
            )

        # Required ordering: hard_refresh → mark_done → status_check → safe_commit.
        assert "hard_refresh" in call_log, (
            f"FR-013: post-merge `git reset --hard HEAD` must fire; call_log={call_log}"
        )
        assert "mark_done" in call_log, "Merged WPs must be recorded as done after refresh"
        assert "status_check" in call_log, (
            f"FR-014: post-merge `git status --porcelain` must fire; call_log={call_log}"
        )
        assert "safe_commit" in call_log, "safe_commit must still fire after refresh/invariant"

        refresh_idx = call_log.index("hard_refresh")
        mark_done_idx = call_log.index("mark_done")
        status_idx = call_log.index("status_check")
        commit_idx = call_log.index("safe_commit")
        assert refresh_idx < mark_done_idx < status_idx < commit_idx, (
            f"Expected refresh → mark_done → status → safe_commit, got {call_log}"
        )

    def test_invariant_violation_aborts_before_safe_commit(self, tmp_path: Path) -> None:
        """FR-014: an unexpected diverging path aborts the merge before safe_commit."""
        slug = "test-invariant-violation"
        _init_git_repo(tmp_path)

        feature_dir = tmp_path / "kitty-specs" / slug
        feature_dir.mkdir(parents=True)
        _seed_wp_done(feature_dir, slug, ["WP01"])

        manifest = self._make_manifest(slug)

        lane_result = MagicMock()
        lane_result.success = True
        lane_result.errors = []

        mission_result = MagicMock()
        mission_result.success = True
        mission_result.commit = "abc1234"
        mission_result.errors = []

        call_log: list[str] = []

        def fake_run_command(cmd, *args, **kwargs):  # noqa: ANN001
            if "reset" in cmd and "--hard" in cmd and "HEAD" in cmd:
                call_log.append("hard_refresh")
                return (0, "", "")
            if "merge-base" in cmd:
                return (0, "abc123\n", "")
            return (0, "", "")

        def fake_raw_porcelain(repo_root):  # noqa: ANN001
            call_log.append("status_check")
            # Simulate an offending diverging path that is NOT one of the two
            # expected status files. This must trigger the invariant. The
            # post-merge invariant reads porcelain RAW via _raw_porcelain_status
            # so the leading status column is preserved.
            return (0, " M src/unexpected_file.py\n")

        def fake_safe_commit(**kwargs):  # noqa: ANN001
            call_log.append("safe_commit")
            return True

        stale_report = MagicMock()
        stale_report.findings = []
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        policy = MagicMock()
        policy.merge_gates = []

        patches = [
            patch("specify_cli.merge.executor.require_lanes_json", return_value=manifest),
            patch("specify_cli.merge.resolve.load_state", return_value=None),
            patch("specify_cli.merge.done_bookkeeping.save_state"),
            patch("specify_cli.merge.executor.get_main_repo_root", return_value=tmp_path),
            patch("specify_cli.merge.executor.require_no_sparse_checkout"),
            patch("specify_cli.status.get_wp_lane", return_value="done"),
            patch("specify_cli.lanes.merge.consolidate_lane_into_mission", return_value=lane_result),
            patch("specify_cli.lanes.merge.integrate_mission_into_target", return_value=mission_result),
            patch("specify_cli.merge.done_bookkeeping._mark_wp_merged_done"),
            patch("specify_cli.merge.executor.commit_merge_bookkeeping", side_effect=fake_safe_commit),
            patch("specify_cli.post_merge.stale_assertions.run_check", return_value=stale_report),
            patch("specify_cli.policy.merge_gates.evaluate_merge_gates", return_value=gate_eval),
            patch("specify_cli.policy.config.load_policy_config", return_value=policy),
            patch("specify_cli.merge.executor.run_command", side_effect=fake_run_command),
            # WP10 (#2057): the post-merge hard refresh runs in the git_probes
            # seam; spy it into the same call log so the ordering assertion sees it.
            patch("specify_cli.merge.git_probes.run_command", side_effect=fake_run_command),
            patch("specify_cli.merge.executor._raw_porcelain_status", side_effect=fake_raw_porcelain),
            patch("specify_cli.merge.executor.has_remote", return_value=False),
            patch("specify_cli.merge.executor.cleanup_merge_workspace"),
            patch("specify_cli.merge.executor.clear_state"),
            patch("specify_cli.merge.state.MergeState"),
            patch("specify_cli.merge.executor._bake_mission_number_into_mission_branch"),
            patch("specify_cli.merge.executor._check_mission_branch", return_value=(True, None)),
            patch("specify_cli.merge.executor._assert_merged_wps_done_on_target"),
            patch("specify_cli.merge.executor._assert_baseline_merge_commit_on_target"),
        ]
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            with pytest.raises(typer.Exit):
                _run_lane_based_merge(
                    repo_root=tmp_path,
                    mission_slug=slug,
                    push=False,
                    delete_branch=False,
                    remove_worktree=False,
                    strategy=MergeStrategy.SQUASH,
                )

        assert "status_check" in call_log, "status check must have run"
        assert "safe_commit" not in call_log, (
            "FR-014: safe_commit must NOT fire when invariant is violated; "
            f"call_log={call_log}"
        )
