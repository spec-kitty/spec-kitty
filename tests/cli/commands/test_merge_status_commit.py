"""Tests for FR-019 (safe_commit insertion) and FR-020 (done events in git history).

``TestLanesConsolidateRecordsDoneForEveryWp`` runs a real LANES-topology
``spec-kitty consolidate`` and reads ``status.events.jsonl`` / ``status.json`` back
from the target branch with ``git show`` (never from the working tree).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from specify_cli.cli.commands.consolidate import _record_baseline_merge_commit
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.coordination.workspace import CoordinationWorkspace
from tests.terminus.conftest import CoordMission, build_coord_mission, run_terminus, sha_reachable
from tests._support.git_cli import git_out
from tests.terminus.lanes_fixture import build_lanes_mission

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


def _write_wp_file(tasks_dir: Path, wp_id: str, *, review_status: str = "approved", reviewed_by: str = "reviewer-1") -> None:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{wp_id}-impl.md").write_text(
        f'---\nwork_package_id: "{wp_id}"\nreview_status: "{review_status}"\nreviewed_by: "{reviewed_by}"\n---\n# {wp_id}\n',
        encoding="utf-8",
    )


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
# FR-020 -- done events for EVERY WP land on the target (real LANES consolidate)
# ---------------------------------------------------------------------------


@pytest.mark.slow  # real `spec-kitty consolidate` subprocess on a real 2-lane LANES mission
class TestLanesConsolidateRecordsDoneForEveryWp:
    """FR-019/FR-020 on LANES topology: a real consolidate records ``done`` for each merged WP.

    Replaces the 17-patch ``_run_lane_based_consolidation`` harness that stubbed the
    lane merge, reconciliation, gates and state store. Nothing is stubbed here; the
    target defaults to ``develop`` (a protected ``main`` target crashes, #5385).
    """

    def test_every_wp_has_done_event_and_snapshot_on_target(self, tmp_path: Path) -> None:
        wps = ("WP01", "WP02")
        mission = build_lanes_mission(tmp_path, wps=wps)

        result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
        assert result.returncode == 0, f"the real LANES consolidate must succeed\nstdout={result.stdout}\nstderr={result.stderr}"

        # Read from the target branch's git history, never from the working tree.
        prefix = f"{mission.target_branch}:kitty-specs/{mission.slug}"
        events = [json.loads(line) for line in git_out(mission.repo, "show", f"{prefix}/status.events.jsonl").splitlines() if line.strip()]
        assert {e["wp_id"] for e in events if e.get("to_lane") == "done"} == set(wps)

        snapshot = json.loads(git_out(mission.repo, "show", f"{prefix}/status.json"))
        assert {wp: snapshot["work_packages"][wp]["lane"] for wp in wps} == dict.fromkeys(wps, "done")


# ---------------------------------------------------------------------------
# #5019 -- graceful exit on an unmaterialized coordination worktree
# ---------------------------------------------------------------------------


def _build_declared_coord_mission(tmp_path: Path, label: str) -> tuple[str, str, str]:
    """A committed coord-topology Mission (meta + WP file) whose coordination branch exists.

    Returns ``(mission_slug, coord_branch, mid8)``. The coordination branch is
    cut at the commit that carries the Mission dir; no worktree is created.
    """
    mid8 = "01KMATRX"
    mission_slug = f"{label}-{mid8}"
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
    subprocess.run(["git", "branch", coord_branch], cwd=tmp_path, check=True, capture_output=True)
    return mission_slug, coord_branch, mid8


def _run_consolidation_expecting_abort_or_failure(tmp_path: Path, mission_slug: str) -> typer.Exit | None:
    """Drive ``_run_lane_based_consolidation`` and return the ``typer.Exit`` it raised (if any)."""
    from specify_cli.consolidation.executor import _run_lane_based_consolidation

    try:
        _run_lane_based_consolidation(
            repo_root=tmp_path,
            mission_slug=mission_slug,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
        )
    except typer.Exit as exc:
        return exc
    return None


class TestUnmaterializedCoordWorktreeMerge:
    """A coord merge whose worktree was never materialized no longer aborts when the branch is local.

    Ruling Q4 (coord-artifact-single-home): the executor's status location is
    the WRITE accessor (``write_dir``), which materializes an UNMATERIALIZED
    surface whose coordination branch has a local head. Only a REMOTE-ONLY branch
    (#4970) still aborts before any state change. This class used to hold ONE test
    pinning "abort on every UNMATERIALIZED cell"; that is split into the two
    tests below. The split is a deliberate behaviour change, not a stale test.
    """

    def test_local_branch_unmaterialized_coord_is_materialized_before_merge(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """#5019 re-pin (R23, ruling Q4): a declared + extant LOCAL coordination
        branch whose worktree was removed (the fresh-clone / CI-runner /
        ``git worktree remove`` window, ``CoordState.UNMATERIALIZED``) is
        MATERIALIZED by the executor's pre-phase and consolidation proceeds past the
        surface resolution instead of aborting with "Merge aborted before any
        state change ... Materialize the coordination worktree".

        The fixture has no ``lanes.json``, so the run stops later on that
        unrelated precondition (``MissingLanesError``); what this pins is that the
        surface phase did not abort and that the surface is MATERIALIZED afterwards.
        """
        from specify_cli.coordination.surface_resolver import CoordState, probe_coord_state
        from specify_cli.lanes.persistence import MissingLanesError

        mission_slug, coord_branch, mid8 = _build_declared_coord_mission(tmp_path, "merge-unmat-coord")

        with pytest.raises(MissingLanesError):
            _run_consolidation_expecting_abort_or_failure(tmp_path, mission_slug)

        output = " ".join(capsys.readouterr().out.split())
        assert "Merge aborted before any state change" not in output, output
        assert "Materialize the coordination worktree" not in output, output
        assert probe_coord_state(tmp_path, mission_slug, mid8, coordination_branch=coord_branch) is CoordState.MATERIALIZED
        coord_wt = CoordinationWorkspace.worktree_path(tmp_path, mission_slug, mid8)
        assert (coord_wt / "kitty-specs" / mission_slug / "meta.json").is_file()

    def test_remote_only_coord_branch_still_aborts_before_state_change(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """#4970 control: a coordination branch that exists ONLY on a remote still aborts cleanly.

        New fixture (a ``file://`` bare remote, the branch pushed, the local head
        deleted); the assertions are the original test's, byte for byte.
        """
        mission_slug, coord_branch, _mid8 = _build_declared_coord_mission(tmp_path, "merge-unmat-coord")
        remote_dir = tmp_path.parent / f"{tmp_path.name}-remote.git"
        subprocess.run(["git", "init", "--bare", "-b", "main", str(remote_dir)], check=True, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", remote_dir.as_uri()], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "push", "origin", coord_branch], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "fetch", "origin", coord_branch], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "branch", "-D", coord_branch], cwd=tmp_path, check=True, capture_output=True)

        exit_exc = _run_consolidation_expecting_abort_or_failure(tmp_path, mission_slug)

        assert exit_exc is not None
        assert exit_exc.exit_code == 1
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
