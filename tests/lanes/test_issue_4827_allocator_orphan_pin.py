"""Issue #4827: an orphaned recorded ``planning_commit_sha`` must surface a
recovery-naming, orphan-specific error -- never the generic
``PlanningCommitMergeConflictError`` and never a silent fall-through.

Red-first repro (T011): before this WP, ``_merge_recorded_planning_commit``
only asked "is the recorded pin an ancestor of the LANE'S OWN HEAD?" -- an
orphaned pin (present in the object store, but no longer reachable from the
mission's TARGET-BRANCH tip after a mid-mission rebase) either fell through
into ``git merge <orphan-sha>`` and raised the generic
``PlanningCommitMergeConflictError`` (if the merge happened to conflict), or
silently succeeded with a disconnected merge commit (if it happened not to
conflict) -- neither names the actual problem or the
``finalize-tasks --refresh-planning-commit --allow-orphaned`` recovery.

Post-fix (T012/T013), ``allocate_lane_worktree`` classifies the recorded pin
against the TARGET-BRANCH tip (never the lane HEAD -- C-006, #2993) via the
WP01 shared classifier before either the fresh-path or the reuse-path merge,
and raises :class:`OrphanedPlanningCommitError` -- a sibling to, never a
subclass of, :class:`PlanningCommitMergeConflictError` (see that class's
docstring on why the fresh-path except must not catch it).

See research.md D5/D6 and ``kitty-specs/finalize-repin-orphaned-planning-commit-01M31TAT``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.planning_commit_classify import PinClass
from specify_cli.lanes.worktree_allocator import (
    OrphanedPlanningCommitError,
    PlanningCommitMergeConflictError,
    allocate_lane_worktree,
)

pytestmark = [pytest.mark.git_repo]

MISSION_SLUG = "020-orphan-pin"
MISSION_ID = "01KYP3MHORPHANPIN00000001"
WP_ID = "WP01"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")


def _commit_planning_artifacts(repo: Path, feature_dir: Path, content: str) -> str:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "spec.md").write_text(content, encoding="utf-8")
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "docs: spec")
    return _git(repo, "rev-parse", "HEAD")


def _orphan_a_planning_commit(repo: Path, feature_dir: Path) -> str:
    """Commit a planning-artifact SHA on ``main``, then rebase it away.

    Reproduces the real "mid-mission rebase" shape research.md D1/D5
    describes: the commit object stays present (nothing garbage-collects a
    reachable-by-SHA commit in a fresh test repo) but is no longer an
    ancestor of ``main``'s new tip once history is rewritten past it.
    """
    orphan_sha = _commit_planning_artifacts(repo, feature_dir, "# v1\n")
    # Rewrite main's history past the planning commit -- the same shape a
    # real amend/rebase of the planning authoring commit produces. The hard
    # reset removes kitty-specs/ from the working tree entirely (it only
    # existed in the commit being rewound past), so it must be recreated
    # before writing the "rebased" version.
    _git(repo, "reset", "-q", "--hard", "HEAD~1")
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "spec.md").write_text("# v2 (rebased)\n", encoding="utf-8")
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "docs: spec (rebased)")
    return orphan_sha


def _make_manifest(mission_branch: str, *, planning_commit_sha: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        mission_branch=mission_branch,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=(WP_ID,),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-09-21T10:00:00Z",
        computed_from="test",
        planning_commit_sha=planning_commit_sha,
    )


class TestFreshPathOrphanedPin:
    """#4827 T011: a fresh lane allocation must refuse an orphaned pin."""

    def test_orphaned_pin_raises_orphan_specific_error(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)
        feature_dir = repo / "kitty-specs" / MISSION_SLUG
        orphan_sha = _orphan_a_planning_commit(repo, feature_dir)

        mission_branch = f"kitty/mission-{MISSION_SLUG}"
        manifest = _make_manifest(mission_branch, planning_commit_sha=orphan_sha)

        with pytest.raises(OrphanedPlanningCommitError) as exc_info:
            allocate_lane_worktree(
                repo_root=repo,
                mission_slug=MISSION_SLUG,
                wp_id=WP_ID,
                lanes_manifest=manifest,
            )

        err = exc_info.value
        assert err.lane_id == "lane-a"
        assert err.planning_commit_sha == orphan_sha
        assert err.pin_class is PinClass.ORPHANED
        # Operator-actionable: names both the command and the flag that
        # actually clears an orphan (bare --refresh-planning-commit stays
        # advance-only refused per #4141/D3).
        assert "finalize-tasks" in err.next_step
        assert "--refresh-planning-commit" in err.next_step
        assert "--allow-orphaned" in err.next_step

        # Never the generic, non-actionable conflict error.
        assert not isinstance(err, PlanningCommitMergeConflictError)

    def test_foreign_pin_next_step_points_at_investigation_not_the_flag(self, tmp_path: Path) -> None:
        """#4827 review LOW / DD-10: a FOREIGN pin (object absent, not merely
        unreachable) cannot be re-pinned -- ``--allow-orphaned`` would be
        refused by finalize (FR-004) -- so the allocator's next_step points at
        investigation, not the recovery flag, avoiding a two-hop-to-refusal path.
        """
        repo = tmp_path / "repo"
        _init_repo(repo)
        absent_sha = "d" * 40  # syntactically valid, absent from the object store

        mission_branch = f"kitty/mission-{MISSION_SLUG}"
        manifest = _make_manifest(mission_branch, planning_commit_sha=absent_sha)

        with pytest.raises(OrphanedPlanningCommitError) as exc_info:
            allocate_lane_worktree(
                repo_root=repo,
                mission_slug=MISSION_SLUG,
                wp_id=WP_ID,
                lanes_manifest=manifest,
            )

        err = exc_info.value
        assert err.pin_class is PinClass.FOREIGN
        assert "foreign" in err.next_step
        assert "investigate" in err.next_step
        # Must NOT send the operator to the re-pin flag, which finalize refuses
        # for a foreign object (FR-004).
        assert "--allow-orphaned" not in err.next_step
        assert err.to_dict()["pin_class"] == "foreign"

    def test_orphaned_pin_error_payload_is_machine_readable(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)
        feature_dir = repo / "kitty-specs" / MISSION_SLUG
        orphan_sha = _orphan_a_planning_commit(repo, feature_dir)

        mission_branch = f"kitty/mission-{MISSION_SLUG}"
        manifest = _make_manifest(mission_branch, planning_commit_sha=orphan_sha)

        with pytest.raises(OrphanedPlanningCommitError) as exc_info:
            allocate_lane_worktree(
                repo_root=repo,
                mission_slug=MISSION_SLUG,
                wp_id=WP_ID,
                lanes_manifest=manifest,
            )

        payload = exc_info.value.to_dict()
        assert payload["error_code"] == "ORPHANED_PLANNING_COMMIT"
        assert payload["planning_commit_sha"] == orphan_sha
        assert payload["pin_class"] == "orphaned"
        # Distinct shape from PlanningCommitMergeConflictError's payload --
        # never reuses its "resolve manually" wording (T013).
        assert "resolve the conflicts" not in payload["next_step"]

    def test_orphaned_pin_leaves_worktree_registered_not_removed(self, tmp_path: Path) -> None:
        """The fresh-path except-narrowing (brownfield note 3): an orphan is
        NOT caught by the ``except PlanningCommitMergeConflictError`` cleanup
        -- retrying via crash-recovery would just re-classify ``orphaned``
        forever until an operator re-pins, so the worktree registration is
        left in place rather than removed-and-retried.
        """
        from specify_cli.lanes.branch_naming import worktree_path

        repo = tmp_path / "repo"
        _init_repo(repo)
        feature_dir = repo / "kitty-specs" / MISSION_SLUG
        orphan_sha = _orphan_a_planning_commit(repo, feature_dir)

        mission_branch = f"kitty/mission-{MISSION_SLUG}"
        manifest = _make_manifest(mission_branch, planning_commit_sha=orphan_sha)

        with pytest.raises(OrphanedPlanningCommitError):
            allocate_lane_worktree(
                repo_root=repo,
                mission_slug=MISSION_SLUG,
                wp_id=WP_ID,
                lanes_manifest=manifest,
            )

        expected_path = worktree_path(repo, MISSION_SLUG, mission_id=None, lane_id="lane-a")
        assert expected_path.exists(), "an orphaned-pin failure must leave the worktree registered (never removed-and-retried like a transient merge conflict)"


class TestReusePathOrphanedPin:
    """#4827 D6: an already-allocated lane's next touch also refuses while
    the mission-wide pin stays orphaned -- only a re-pin clears it, even
    though the lane's own HEAD may already contain the (now-orphaned) SHA.
    """

    def test_reuse_path_orphaned_pin_raises_on_reentry(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)
        feature_dir = repo / "kitty-specs" / MISSION_SLUG
        healthy_sha = _commit_planning_artifacts(repo, feature_dir, "# v1\n")

        mission_branch = f"kitty/mission-{MISSION_SLUG}"
        manifest = _make_manifest(mission_branch, planning_commit_sha=healthy_sha)

        # Allocate while the pin is still healthy (an ancestor of target
        # "main") -- succeeds and the lane-HEAD no-op gate short-circuits
        # (the fresh legacy mission_branch is minted FROM main's current
        # tip, so it already contains the pin).
        worktree_path_, _branch = allocate_lane_worktree(
            repo_root=repo,
            mission_slug=MISSION_SLUG,
            wp_id=WP_ID,
            lanes_manifest=manifest,
        )

        # Now rebase "main" past that commit -- the manifest's recorded SHA
        # (unchanged, no finalize re-run yet) becomes orphaned relative to
        # the NEW target tip, even though the lane worktree already merged
        # it while it was still healthy. `repo` (the main checkout) never
        # left "main" -- allocation only ever checks out the LANE worktree.
        # The hard reset removes kitty-specs/ from the working tree (it
        # existed only in the commit being rewound past), so recreate it.
        _git(repo, "reset", "-q", "--hard", "HEAD~1")
        feature_dir.mkdir(parents=True, exist_ok=True)
        (feature_dir / "spec.md").write_text("# v2 (rebased)\n", encoding="utf-8")
        _git(repo, "add", "kitty-specs")
        _git(repo, "commit", "-q", "-m", "docs: spec (rebased)")

        # Re-entering the SAME lane (reuse route) re-classifies the recorded
        # (unchanged) SHA against the NEW target tip and must refuse, even
        # though `worktree_path_`'s own HEAD already contains it (D6).
        with pytest.raises(OrphanedPlanningCommitError) as exc_info:
            allocate_lane_worktree(
                repo_root=repo,
                mission_slug=MISSION_SLUG,
                wp_id=WP_ID,
                lanes_manifest=manifest,
            )
        assert exc_info.value.planning_commit_sha == healthy_sha
        assert worktree_path_.exists()
