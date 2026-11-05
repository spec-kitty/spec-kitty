"""WP01/T003 — post-merge index refresh (FR-003).

After the post-merge ``git checkout HEAD -- .`` reconciles working-tree
content with HEAD, the cached stat info in the git index can still trail real
on-disk state. The fix calls ``git update-index --refresh`` to reconcile the
index stats with the working tree without touching any blobs.

This test pins:

1. The merge flow invokes ``git update-index --refresh`` between the
   working-tree refresh and the per-WP done-recording pass.
2. A non-zero return from refresh does NOT abort the merge (informational
   only — refresh divergence is expected, e.g. when the two status files
   are about to be safe_commit'd).
"""

from __future__ import annotations

import contextlib
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.cli.commands.consolidate import _run_lane_based_consolidation
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.lanes.compute import lane_created_branch
from tests.lane_test_utils import commit_branch_implementation, create_lane_branches
from tests.consolidation.executor_family import patch_executor_family
from tests.integration.test_merge_lane_planning_data_loss import _seed_wp_done_raw, _write_wp_file


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


def _make_manifest(slug: str) -> MagicMock:
    manifest = MagicMock()
    # Lane naming is keyed
    # on lanes_manifest.mission_slug; keep it aligned with the real slug.
    manifest.mission_slug = slug
    manifest.target_branch = "main"
    manifest.mission_branch = f"kitty/mission-{slug}"
    lane = MagicMock()
    lane.lane_id = "lane-a"
    lane.wp_ids = ["WP01"]
    lane.depends_on_lanes = ()
    manifest.lanes = [lane]
    return manifest


def _drive_merge(tmp_path: Path, slug: str, *, refresh_returncode: int = 0):
    manifest = _make_manifest(slug)
    # #5417: the approved lane needs its created branch, or the #5338
    # claim-time integrity refusal stops the merge before the refresh.
    create_lane_branches(tmp_path, manifest)
    feature_dir = tmp_path / "kitty-specs" / slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    # #6715: a recorded planning commit, WP01's declared ownership, its lane's implementation
    # commit, and an independent approval stamped at that lane tip precede the seeded ``done``.
    _write_wp_file(feature_dir, "WP01")
    lane_head = commit_branch_implementation(tmp_path, manifest, lane_created_branch(manifest, "lane-a"), path="src/wp01.py")
    _seed_wp_done_raw(feature_dir, slug, ["WP01"], lane_head=lane_head)

    lane_result = MagicMock()
    lane_result.success = True
    lane_result.errors = []

    mission_result = MagicMock()
    mission_result.success = True
    mission_result.commit = "abc1234"
    mission_result.errors = []

    call_log: list[tuple[str, ...]] = []

    def fake_run_command(cmd, *args, **kwargs):  # noqa: ANN001
        call_log.append(tuple(cmd))
        if "merge-base" in cmd:
            return (0, "abc123\n", "")
        # #5668: the approval-bound claim resolves its base ref through the git probe
        # ({ref}^{{commit}}); an empty answer reads as "does not resolve" and refuses the claim.
        if "rev-parse" in cmd:
            return (0, "d4f8a1c2e6b09f37a5c1e8b2f4a6d0c9e3b7f1a2\n", "")
        if "update-index" in cmd and "--refresh" in cmd:
            # Allow caller to simulate divergence via non-zero return.
            return (refresh_returncode, "", "stat info differs")
        return (0, "", "")

    def fake_status_entries(cwd, **kwargs):  # noqa: ANN001, ANN202
        # The post-merge invariant reads status through the kernel.git typed query
        # (``git status --porcelain=v1 -z``), not ``run_command``; log it in the
        # same call log so the ordering assertion still sees the status check, and
        # report a clean tree like the old mocked empty porcelain output.
        call_log.append(("git", "status", "--porcelain=v1", "-z"))
        return ()

    def fake_guarded_reset_hard(*args, **kwargs):  # noqa: ANN001, ANN202
        # #5965/#5966: the post-merge `git reset --hard HEAD` now routes through
        # ``guarded_reset_hard`` (its own ``_git_ok``/``_run_git`` wrapper), not
        # ``run_command``, so ``fake_run_command`` never sees the reset. Record a
        # ``reset --hard HEAD``-equivalent marker here, at the same ordering point
        # the production reset runs, so the FR-003 "reset fires" / ordering
        # assertions hold against the current seam.
        call_log.append(("git", "reset", "--hard", "HEAD"))
        return None

    patches = [
        patch("specify_cli.consolidation.entry_preflight.require_lanes_json", return_value=manifest),
        patch("specify_cli.consolidation.resolve.load_state", return_value=None),
        patch("specify_cli.consolidation.done_bookkeeping.save_state"),
        patch_executor_family("get_main_repo_root", return_value=tmp_path),
        patch("specify_cli.consolidation.executor.require_no_sparse_checkout"),
        patch("specify_cli.lanes.consolidation.consolidate_lane_into_mission", return_value=lane_result),
        patch("specify_cli.lanes.consolidation.integrate_mission_into_target", return_value=mission_result),
        patch("specify_cli.consolidation.done_bookkeeping._mark_wp_merged_done"),
        patch_executor_family("commit_merge_bookkeeping"),
        patch("specify_cli.consolidation.done_bookkeeping._assert_merged_wps_reached_done"),
        patch("specify_cli.post_merge.stale_assertions.run_check"),
        patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        patch("specify_cli.policy.config.load_policy_config"),
        patch_executor_family("run_command", side_effect=fake_run_command),
        # WP10 (#2057): the post-merge working-tree refresh (git reset --hard +
        # git update-index --refresh) lives in the git_probes seam; spy its
        # run_command into the same call log so the FR-003 assertion still sees it.
        patch("specify_cli.consolidation.git_probes.run_command", side_effect=fake_run_command),
        # #5965/#5966: the reset itself now routes through ``guarded_reset_hard``;
        # spy it so the FR-003 ordering/"reset fires" assertions still observe it.
        patch("specify_cli.consolidation.git_probes.guarded_reset_hard", side_effect=fake_guarded_reset_hard),
        patch("specify_cli.consolidation.git_probes.status_entries", side_effect=fake_status_entries),
        patch("specify_cli.consolidation.phase_finalize.has_remote", return_value=False),
        patch("specify_cli.consolidation.phase_finalize.cleanup_merge_workspace"),
        patch_executor_family("clear_state"),
        patch(
            "specify_cli.consolidation.phase_advance._bake_mission_number_into_mission_branch",
            return_value=None,
        ),
        # WP10 (#2057): mission-branch preflight moved to the preflight seam;
        # appended last to keep positional mock indices stable.
        patch("specify_cli.consolidation.executor._check_mission_branch", return_value=(True, None)),
        # WP10 (#2057): target-history asserts moved to the done_bookkeeping /
        # baseline seams; the executor binds them — patch there.
        patch("specify_cli.consolidation.phase_bookkeeping._assert_merged_wps_done_on_target"),
        patch("specify_cli.consolidation.phase_bookkeeping._assert_baseline_merge_commit_on_target"),
        patch("specify_cli.consolidation.executor._phase_reconcile_before_teardown"),
    ]

    with contextlib.ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in patches]
        stale = MagicMock()
        stale.findings = []
        mocks[10].return_value = stale

        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        mocks[11].return_value = gate_eval

        policy = MagicMock()
        policy.merge_gates = []
        mocks[12].return_value = policy

        _run_lane_based_consolidation(
            repo_root=tmp_path,
            mission_slug=slug,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
        )

    return call_log


class TestPostMergeIndexRefresh:
    def test_merge_invokes_update_index_refresh(self, tmp_path: Path) -> None:
        slug = "test-index-refresh"
        _init_git_repo(tmp_path)
        call_log = _drive_merge(tmp_path, slug)

        refresh_calls = [c for c in call_log if c[:2] == ("git", "update-index") or "update-index" in c]
        assert refresh_calls, (
            "FR-003 regression: merge did not invoke `git update-index --refresh`. "
            "After post-merge `git reset --hard HEAD`, the index stat cache must "
            "be reconciled against the working tree to prevent phantom deletions."
        )

        # The exact command shape we expect.
        assert any(
            "update-index" in c and "--refresh" in c for c in call_log
        ), f"Did not see `git update-index --refresh`: {call_log!r}"

    def test_refresh_runs_after_hard_reset_before_status_check(self, tmp_path: Path) -> None:
        """Order matters: the refresh must run AFTER `reset --hard HEAD` and
        BEFORE the post-merge `git status --porcelain` invariant check, so
        the invariant assertion sees a clean stat-cache."""
        slug = "test-index-refresh-order"
        _init_git_repo(tmp_path)
        call_log = _drive_merge(tmp_path, slug)

        def _idx(predicate):
            for i, cmd in enumerate(call_log):
                if predicate(cmd):
                    return i
            return -1

        hard_reset_idx = _idx(lambda cmd: "reset" in cmd and "--hard" in cmd and "HEAD" in cmd)
        refresh_idx = _idx(lambda cmd: "update-index" in cmd and "--refresh" in cmd)
        status_idx = _idx(lambda cmd: "status" in cmd and any(a.startswith("--porcelain") for a in cmd))

        assert hard_reset_idx >= 0 and refresh_idx >= 0 and status_idx >= 0, (
            f"Missing one of hard-reset/refresh/status in call log: {call_log!r}"
        )
        assert hard_reset_idx < refresh_idx < status_idx, (
            f"Wrong order: hard_reset={hard_reset_idx}, refresh={refresh_idx}, "
            f"status={status_idx}. Expected hard reset < refresh < status. "
            f"Full log: {call_log!r}"
        )

    def test_nonzero_refresh_does_not_abort_merge(self, tmp_path: Path) -> None:
        """A non-zero return from `git update-index --refresh` is informational
        only (it indicates the working tree differs from the index, which is
        expected when status files are about to be committed). The merge
        must NOT raise on this."""
        slug = "test-refresh-tolerates-divergence"
        _init_git_repo(tmp_path)
        # refresh_returncode=1 simulates "stat info differs" — must not raise.
        call_log = _drive_merge(tmp_path, slug, refresh_returncode=1)
        # safe_commit should still have been wired (proxy: status check ran).
        assert any("status" in c and any(a.startswith("--porcelain") for a in c) for c in call_log), (
            "Merge aborted before reaching the post-merge invariant check, "
            "indicating that a divergent `update-index --refresh` was treated "
            "as fatal. FR-003 requires it to be informational."
        )
