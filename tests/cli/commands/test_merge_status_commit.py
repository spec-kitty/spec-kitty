"""Tests for FR-019 (safe_commit insertion) and FR-020 (done events in git history).

The most important test is test_done_events_committed_to_git which uses
git show HEAD: to prove the events are durably committed after _run_lane_based_consolidation
returns (the canonical mechanically-correct assertion — NOT git reset --hard HEAD).

Note on patching: consolidate_lane_into_mission/integrate_mission_into_target are imported locally inside
_run_lane_based_consolidation, so they must be patched at the source module level
(specify_cli.lanes.consolidation.*) not at specify_cli.cli.commands.consolidate.*.
evaluate_merge_gates and load_policy_config are similarly patched at their source paths.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from specify_cli.cli.commands.consolidate import (
    _record_baseline_merge_commit,
    _run_lane_based_consolidation,
)
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.coordination.workspace import CoordinationWorkspace
from tests.terminus.conftest import CoordMission, build_coord_mission, run_terminus, sha_reachable
from tests.terminus.conftest import _git_out as git_out

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_git_repo(path: Path, branch: str = "main") -> None:
    """Initialize a git repo with a signed-off initial commit."""
    subprocess.run(["git", "init", f"-b{branch}"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True, capture_output=True)
    (path / "README.md").write_text("init\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-m", "init"],
        cwd=path,
        check=True,
        capture_output=True,
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
        f'---\nwork_package_id: "{wp_id}"\nreview_status: "{review_status}"\nreviewed_by: "{reviewed_by}"\n---\n# {wp_id}\n',
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


class TestAssertMergedWpsReachedDoneAbsentLog:
    """Absent canonical log must fail cleanly, not crash post-integration."""

    def test_clean_exit_when_canonical_log_absent(self, tmp_path: Path) -> None:
        import typer

        from specify_cli.cli.commands.consolidate import _assert_merged_wps_reached_done
        from specify_cli.status import CanonicalStatusNotFoundError

        mission_slug = "068-no-canonical-log"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)

        with (
            patch(
                "specify_cli.consolidation.done_bookkeeping.resolve_status_surface",
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
# FR-019 -- the bookkeeping commit really lands (real git, nothing stubbed)
# ---------------------------------------------------------------------------


@dataclass
class _RealMerge:
    mission: CoordMission
    result: subprocess.CompletedProcess[str]
    target_tip_before: str


@pytest.fixture(scope="module")
def real_merge(tmp_path_factory: pytest.TempPathFactory) -> _RealMerge:
    """ONE real ``spec-kitty consolidate`` (squash, default teardown) on a real coord mission.

    Real lanes, real reconciliation/bake/#4900 mission-number verification, real
    ``commit_merge_bookkeeping``, real coordination teardown. Replaces the three
    ~25-patch mock harnesses that stubbed those gates to keep the tests green.
    """
    mission = build_coord_mission(tmp_path_factory.mktemp("real_merge"))
    target_tip_before = mission.rev(mission.target_branch)
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    return _RealMerge(mission=mission, result=result, target_tip_before=target_tip_before)


def _require_merge_succeeded(real_merge: _RealMerge) -> None:
    """Fail readably (not as a setup ERROR) when the shared real merge did not exit 0."""
    result = real_merge.result
    if result.returncode != 0:
        pytest.fail(
            f"the shared real merge exited {result.returncode}; see test_real_merge_exits_zero\nstdout={result.stdout}\nstderr={result.stderr}",
            pytrace=False,
        )


@pytest.mark.slow  # module-scoped real `spec-kitty consolidate` on a real coord mission (>30s setup)
class TestRealMergeCommitsBookkeeping:
    """FR-019/FR-020: the post-merge bookkeeping is durably committed to the TARGET branch.

    Supersedes the removed mock tests ``test_safe_commit_is_called_with_correct_files``,
    ``test_merge_commits_baseline_merge_commit_metadata`` and
    ``test_safe_commit_called_before_worktree_removal``: their contracts (status
    pair committed; baseline recorded in the committed meta.json; events
    persisted before the coordination worktree is destroyed) are asserted here
    against ``git show <target>:...`` after a real teardown.
    """

    def _target_show(self, real_merge: _RealMerge, relpath: str) -> str:
        mission = real_merge.mission
        return git_out(mission.repo, "show", f"{mission.target_branch}:kitty-specs/{mission.slug}/{relpath}")

    def test_real_merge_exits_zero(self, real_merge: _RealMerge) -> None:
        result = real_merge.result
        assert result.returncode == 0, f"the real merge must succeed\nstdout={result.stdout}\nstderr={result.stderr}"

    def test_status_pair_with_done_event_is_committed_on_target(self, real_merge: _RealMerge) -> None:
        _require_merge_succeeded(real_merge)
        events = [json.loads(line) for line in self._target_show(real_merge, "status.events.jsonl").splitlines() if line.strip()]
        assert any(e["wp_id"] == "WP01" and e["to_lane"] == "done" for e in events)
        snapshot = json.loads(self._target_show(real_merge, "status.json"))
        assert snapshot["work_packages"]["WP01"]["lane"] == "done"

    def test_baseline_merge_commit_is_recorded_in_committed_meta(self, real_merge: _RealMerge) -> None:
        _require_merge_succeeded(real_merge)
        mission = real_merge.mission
        meta = json.loads(self._target_show(real_merge, "meta.json"))
        baseline = meta.get("baseline_merge_commit")
        assert isinstance(baseline, str)
        # The baseline is exactly the pre-merge target tip (not merely "some commit").
        assert baseline == real_merge.target_tip_before
        # It is a real commit reachable from the target branch.
        assert git_out(mission.repo, "cat-file", "-t", baseline).strip() == "commit"
        assert sha_reachable(mission.repo, baseline, mission.target_branch)

    def test_bookkeeping_survives_coordination_teardown(self, real_merge: _RealMerge) -> None:
        """The events are on the target although the coordination branch/worktree were destroyed."""
        _require_merge_succeeded(real_merge)
        mission = real_merge.mission
        branches = git_out(mission.repo, "branch", "--list", mission.coord_branch).strip()
        assert branches == "", "default teardown must remove the coordination branch"
        coord_wt = CoordinationWorkspace.worktree_path(mission.repo, mission.slug, mission.mid8)
        assert not coord_wt.exists(), f"coordination worktree dir must be removed: {coord_wt}"
        registered = [
            Path(line.removeprefix("worktree ")).resolve()
            for line in git_out(mission.repo, "worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ")
        ]
        assert coord_wt.resolve() not in registered
        assert '"to_lane": "done"' in self._target_show(real_merge, "status.events.jsonl")

    def test_bookkeeping_commit_subject_is_on_target_branch(self, real_merge: _RealMerge) -> None:
        """The ``record done transitions`` bookkeeping commit itself is in the target's history."""
        _require_merge_succeeded(real_merge)
        mission = real_merge.mission
        subjects = git_out(mission.repo, "log", mission.target_branch, "--format=%s").splitlines()
        expected = f"chore({mission.slug}): record done transitions"
        assert any(subject.startswith(expected) for subject in subjects), subjects


# ---------------------------------------------------------------------------
# FR-020 — done events committed to git (the canonical regression test)
# ---------------------------------------------------------------------------


class TestDoneEventsCommittedToGit:
    """FR-020: after _run_lane_based_consolidation, done events are in git history at HEAD.

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
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        _seed_mission_branch(tmp_path, mission_slug)

        # Seed event log entries (approved state for each WP, as they would be pre-merge)
        for wp_id in wps:
            _seed_status_event(feature_dir, mission_slug, wp_id, "approved")

        # Materialize status.json
        from specify_cli.status.reducer import materialize

        materialize(feature_dir)

        manifest = MagicMock()
        # Lane naming is keyed on lanes_manifest.mission_slug; keep it
        # aligned with the real slug.
        manifest.mission_slug = mission_slug
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
            patch("specify_cli.consolidation.executor.require_lanes_json", return_value=manifest),
            patch("specify_cli.consolidation.resolve.load_state", return_value=None),
            patch("specify_cli.consolidation.done_bookkeeping.save_state"),
            patch("specify_cli.consolidation.executor.get_main_repo_root", return_value=tmp_path),
            # #5001: stub the reconciliation-claim phase — see comment on the
            # same patch pair in test_safe_commit_is_called_with_correct_files
            # above (reconciliation is covered by tests/terminus +
            # tests/merge/test_reconciliation, not this focused unit test).
            patch("specify_cli.consolidation.executor._capture_reconciliation_claim"),
            patch("specify_cli.consolidation.executor._phase_reconcile_before_teardown"),
            patch("specify_cli.lanes.consolidation.consolidate_lane_into_mission", return_value=lane_result),
            patch("specify_cli.lanes.consolidation.integrate_mission_into_target", return_value=mission_result),
            patch("specify_cli.post_merge.stale_assertions.run_check") as mock_run_check,
            patch("specify_cli.policy.merge_gates.evaluate_merge_gates") as mock_gates,
            patch("specify_cli.policy.config.load_policy_config") as mock_policy,
            patch("specify_cli.consolidation.executor.run_command", return_value=(0, "abc123", "")),
            patch("specify_cli.consolidation.executor.has_remote", return_value=False),
            patch("specify_cli.consolidation.executor.cleanup_merge_workspace"),
            patch("specify_cli.consolidation.executor.clear_state"),
            patch("specify_cli.consolidation.state.ConsolidationState"),
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
            _run_lane_based_consolidation(
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
        events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        done_wps = {e["wp_id"] for e in events if e.get("to_lane") == "done"}

        assert done_wps == set(wps), (
            f"Expected done events for every merged WP in git history. "
            f"Got {done_wps}, expected {set(wps)}. "
            "This regression means the FR-019 safe_commit step was missed or failed."
        )
        # Explicitly: do NOT use git reset --hard HEAD here — that would be a no-op
        # (the file is already at HEAD) and proves nothing about the commit having occurred.

    def test_lane_based_merge_exits_cleanly_on_unmaterialized_coord_worktree(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """#5019 landing-pass fold (Finding 1): a coord-topology merge whose
        coordination worktree is declared in meta.json AND still exists in git,
        but was never materialized on disk (the fresh-clone / CI-runner /
        ``git worktree remove`` window — ``CoordState.UNMATERIALIZED``), must
        exit gracefully rather than raise a raw
        ``CoordinationWorktreeUnmaterialized`` traceback.

        Sibling of ``test_lane_based_merge_exits_cleanly_instead_of_tracebacking``
        in tests/merge/test_coord_deleted_degrade_paths.py, which covers the
        DELETED-branch case via the pre-existing ``except CoordinationBranchDeleted``
        handler. That handler does NOT catch ``CoordinationWorktreeUnmaterialized``
        — a sibling ``StatusReadPathNotFound`` subclass, not a
        ``CoordinationBranchDeleted`` subclass — so before this fold's widened
        handler, this scenario propagated the raw exception straight out of
        ``spec-kitty merge`` instead of the graceful pre-state-change exit every
        other coord-partition read failure gets.
        """
        from specify_cli.consolidation.executor import _run_lane_based_consolidation

        mid8 = "01KMATRX"
        mission_slug = f"merge-unmat-coord-{mid8}"
        mission_id = f"{mid8}0000000000000000"
        coord_branch = f"kitty/mission-{mission_slug}"

        _init_git_repo(tmp_path)

        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        _write_meta(
            feature_dir,
            mission_slug,
            mission_id=mission_id,
            mid8=mid8,
            coordination_branch=coord_branch,
        )
        _write_wp_file(feature_dir / "tasks", "WP01")

        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-m", "declared coord branch"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        # The coord branch genuinely exists in git (rules out DELETED) but its
        # worktree is deliberately never materialized (`git worktree add` is NOT
        # run here) — the UNMATERIALIZED cell this fold's handler must degrade
        # gracefully on.
        subprocess.run(["git", "branch", coord_branch], cwd=tmp_path, check=True, capture_output=True)

        with pytest.raises(typer.Exit) as excinfo:
            _run_lane_based_consolidation(
                repo_root=tmp_path,
                mission_slug=mission_slug,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
            )

        assert excinfo.value.exit_code == 1
        # Rich hard-wraps console output at the terminal width, so collapse
        # whitespace before matching — the assertion is about content, not line
        # breaks.
        output = " ".join(capsys.readouterr().out.split())
        assert coord_branch in output, f"the error must name the unmaterialized branch; got: {output!r}"
        # #5113: the remedy names the mission-scoped doctor fixer, not the
        # (worktree-creation-incapable, #2240) husk-only `doctor workspaces --fix`.
        assert "doctor coordination" in output, f"the error must carry the exception's OWN remediation (next_step); got: {output!r}"
        assert "--fix" in output, f"the error must carry the exception's OWN remediation (next_step); got: {output!r}"
        assert "Merge aborted before any state change" in output, f"the operator must be told the merge is a clean no-op; got: {output!r}"
