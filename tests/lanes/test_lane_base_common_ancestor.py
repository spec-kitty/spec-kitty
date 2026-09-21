"""FR-009 / ADR ``2026-07-29-1``: lane-base common-ancestor regression tests (WP01).

Covers T005's Definition-of-Done trio:

1. A lane created from the recorded ``planning_commit_sha`` shares a common
   ancestor with the consolidation base (both the ``coordination_branch`` /
   ``mission_branch`` parent it always had, AND the planning-artifact commit
   the ADR's merge step now adds).
2. A representative write made on the lane survives consolidation with zero
   silent reversion.
3. ``merge/ordering.get_merge_order`` (the topological sort) is unaffected by
   the lane-base change -- it is proven base-independent by construction (no
   git repository at all is required to run it).

Plus focused coverage of the new pieces this WP introduces: the
``LanesManifest.planning_commit_sha`` schema slot (round-trip + backward
compatibility), the ``_merge_recorded_planning_commit`` allocator helper
(no-op / idempotent / conflict-fails-closed), and the
``mission_finalize._capture_target_branch_tip`` producer helper.

These tests use real git repos (subprocess), matching the project convention
in ``tests/lanes/test_worktree_allocator.py`` and
``tests/lanes/test_issue_2993_lane_planning_ancestry.py`` -- the defect
this WP closes is a git-topology defect, so only real git ancestry checks can
prove it is fixed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.worktree_allocator import (
    PlanningCommitMergeConflictError,
    _merge_recorded_planning_commit,
    allocate_lane_worktree,
)
from specify_cli.merge.ordering import get_merge_order

pytestmark = [pytest.mark.git_repo]

MISSION_SLUG = "010-lane-base-fix"
MISSION_ID = "01KYP3MHLANEBASE0000000001"
WP_ID = "WP01"


# ---------------------------------------------------------------------------
# Shared git helpers (mirrors tests/lanes/test_issue_2993_lane_planning_ancestry.py)
# ---------------------------------------------------------------------------


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


def _mint_coordination_branch(repo: Path, coord_branch: str) -> None:
    """Mint the coordination branch BEFORE planning artifacts exist (the #2993 shape)."""
    _git(repo, "branch", coord_branch)


def _commit_planning_artifacts(repo: Path, feature_dir: Path) -> str:
    """Commit spec.md/tasks.md on ``main`` -- a normal planning-authoring commit."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "spec.md").write_text("# Lane base fix\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("## WP01\n- [ ] T001\n", encoding="utf-8")
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "docs: spec+tasks")
    return _git(repo, "rev-parse", "HEAD")


def _make_manifest(
    coordination_branch: str, *, planning_commit_sha: str | None
) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        mission_branch=coordination_branch,
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
        computed_at="2026-07-29T10:00:00Z",
        computed_from="test",
        planning_commit_sha=planning_commit_sha,
    )


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# DoD 1 -- common ancestor with the consolidation base
# ---------------------------------------------------------------------------


class TestLaneSharesCommonAncestor:
    def test_lane_descends_from_both_planning_commit_and_coordination_branch(
        self, tmp_path: Path
    ) -> None:
        """The lane must descend from BOTH ancestries (#2993 Assert A + Assert A')."""
        repo = tmp_path / "repo"
        _init_repo(repo)
        coord_branch = f"kitty/mission-{MISSION_SLUG}"
        _mint_coordination_branch(repo, coord_branch)

        feature_dir = repo / "kitty-specs" / MISSION_SLUG
        planning_sha = _commit_planning_artifacts(repo, feature_dir)

        manifest = _make_manifest(coord_branch, planning_commit_sha=planning_sha)
        _worktree_path, lane_branch = allocate_lane_worktree(
            repo_root=repo,
            mission_slug=MISSION_SLUG,
            wp_id=WP_ID,
            lanes_manifest=manifest,
        )

        assert _is_ancestor(repo, planning_sha, lane_branch), (
            "lane must descend from the recorded planning-artifact commit"
        )
        assert _is_ancestor(repo, coord_branch, lane_branch), (
            "lane must still descend from its coordination_branch parent "
            "(the fix is additive, not a parent swap)"
        )

    def test_no_recorded_sha_falls_back_to_pre_wp01_behaviour(
        self, tmp_path: Path
    ) -> None:
        """``planning_commit_sha=None`` reproduces byte-identical pre-fix behaviour.

        A ``lanes.json`` written before this WP has no such field. The lane
        must still be created (off ``coordination_branch``), and the merge
        helper must be a pure no-op -- no extra commit, no error.
        """
        repo = tmp_path / "repo"
        _init_repo(repo)
        coord_branch = f"kitty/mission-{MISSION_SLUG}"
        _mint_coordination_branch(repo, coord_branch)

        manifest = _make_manifest(coord_branch, planning_commit_sha=None)
        _worktree_path, lane_branch = allocate_lane_worktree(
            repo_root=repo,
            mission_slug=MISSION_SLUG,
            wp_id=WP_ID,
            lanes_manifest=manifest,
        )

        # Lane tip must equal coord_branch tip exactly (no extra merge commit).
        lane_tip = _git(repo, "rev-parse", lane_branch)
        coord_tip = _git(repo, "rev-parse", coord_branch)
        assert lane_tip == coord_tip, (
            "with no recorded SHA, the lane must be byte-identical to its "
            "coordination_branch parent -- no merge commit introduced"
        )


# ---------------------------------------------------------------------------
# DoD 2 -- a representative lane write survives consolidation, zero reversion
# ---------------------------------------------------------------------------


class TestWriteSurvivesConsolidation:
    def test_lane_write_and_planning_artifact_both_survive_merge(
        self, tmp_path: Path
    ) -> None:
        """Merging the lane back does not revert the planning artifacts it
        gained via the recorded-SHA merge, and the lane's own write survives
        too -- the #2993 "silent revert" failure mode is closed.
        """
        repo = tmp_path / "repo"
        _init_repo(repo)
        coord_branch = f"kitty/mission-{MISSION_SLUG}"
        _mint_coordination_branch(repo, coord_branch)

        feature_dir = repo / "kitty-specs" / MISSION_SLUG
        planning_sha = _commit_planning_artifacts(repo, feature_dir)

        manifest = _make_manifest(coord_branch, planning_commit_sha=planning_sha)
        worktree_path, lane_branch = allocate_lane_worktree(
            repo_root=repo,
            mission_slug=MISSION_SLUG,
            wp_id=WP_ID,
            lanes_manifest=manifest,
        )

        # A representative lane write.
        (worktree_path / "feature.py").write_text("x = 1\n", encoding="utf-8")
        _git(worktree_path, "add", "feature.py")
        _git(worktree_path, "commit", "-q", "-m", "feat: add feature.py")

        # Consolidate the lane into its coordination_branch (mirrors
        # lanes/merge.py's consolidate_lane_into_mission at the git level).
        _git(repo, "checkout", "-q", coord_branch)
        _git(repo, "merge", "--no-ff", "--no-edit", lane_branch)

        # Both survive: the lane's own write, AND the planning artifact the
        # lane picked up via the recorded-SHA merge.
        assert (repo / "feature.py").exists(), "lane write must survive consolidation"
        assert (feature_dir / "spec.md").exists(), (
            "planning artifact must survive consolidation -- zero silent reversion"
        )
        assert "Lane base fix" in (feature_dir / "spec.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# DoD 3 -- merge/ordering.py topo-sort is base-independent
# ---------------------------------------------------------------------------


class TestOrderingUnaffectedByLaneBase:
    def test_get_merge_order_requires_no_git_repository(self, tmp_path: Path) -> None:
        """``get_merge_order`` is a pure frontmatter topo-sort (research.md D-5):
        it never inspects git ancestry, so it cannot be perturbed by this WP's
        lane-base change. Proven by running it against a bare, non-git
        ``tmp_path`` -- if it consulted git ancestry in any way, this would
        fail with a "not a git repository" error instead of sorting cleanly.
        """
        workspaces = [
            (tmp_path / "wt-b", "WP02", "kitty/WP02"),
            (tmp_path / "wt-a", "WP01", "kitty/WP01"),
        ]
        # No dependency frontmatter present -> falls back to numerical order,
        # exercising the real (unmocked) build_dependency_graph read against
        # a feature_dir with no tasks/ directory at all.
        result = get_merge_order(workspaces, tmp_path)
        assert [wp_id for _, wp_id, _ in result] == ["WP01", "WP02"]


# ---------------------------------------------------------------------------
# _merge_recorded_planning_commit -- direct unit coverage
# ---------------------------------------------------------------------------


class TestMergeRecordedPlanningCommit:
    def test_none_sha_is_a_pure_noop(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)
        before = _git(repo, "rev-parse", "HEAD")
        _merge_recorded_planning_commit(repo, repo, "lane-a", None)
        assert _git(repo, "rev-parse", "HEAD") == before

    def test_already_ancestor_sha_is_a_noop(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)
        head = _git(repo, "rev-parse", "HEAD")
        # HEAD is trivially its own ancestor -- merging it in must not create
        # a new commit (idempotency, exercised on the reuse/recovery paths).
        _merge_recorded_planning_commit(repo, repo, "lane-a", head)
        assert _git(repo, "rev-parse", "HEAD") == head

    def test_conflicting_merge_fails_closed_and_leaves_worktree_clean(
        self, tmp_path: Path
    ) -> None:
        """#4827/WP03 T016 GREEN-WASH GATE: this is the ONE test in
        ``tests/lanes/`` that must keep exercising the GENERIC conflict with
        a pin REACHABLE from the target tip. ``other_sha`` is passed as
        BOTH the recorded pin AND (via ``target_tip=other_sha``) the tip it
        is classified against, so it is trivially ``ADVANCED`` (an ancestor
        of itself) -- the orphan check does not fire, and the pre-existing
        genuine-content-conflict path (untouched by #4827) still raises the
        generic :class:`PlanningCommitMergeConflictError`. Do not flip this
        test to expect :class:`OrphanedPlanningCommitError` -- see
        ``test_worktree_allocator_atomicity.py`` for the sibling test that
        WAS an orphan-shaped fixture and was corrected the other way.
        """
        repo = tmp_path / "repo"
        _init_repo(repo)
        # Diverge: same file, different content on two branches.
        _git(repo, "checkout", "-q", "-b", "other")
        (repo / "seed.txt").write_text("other change\n", encoding="utf-8")
        _git(repo, "add", "seed.txt")
        _git(repo, "commit", "-q", "-m", "other: change seed")
        other_sha = _git(repo, "rev-parse", "HEAD")

        _git(repo, "checkout", "-q", "main")
        (repo / "seed.txt").write_text("main change\n", encoding="utf-8")
        _git(repo, "add", "seed.txt")
        _git(repo, "commit", "-q", "-m", "main: change seed")
        head_before = _git(repo, "rev-parse", "HEAD")

        with pytest.raises(PlanningCommitMergeConflictError) as exc_info:
            _merge_recorded_planning_commit(repo, repo, "lane-a", other_sha, other_sha)

        assert exc_info.value.lane_id == "lane-a"
        assert exc_info.value.planning_commit_sha == other_sha
        assert exc_info.value.next_step  # operator-actionable

        # Fail-closed: HEAD is unmoved and no merge is left in progress.
        assert _git(repo, "rev-parse", "HEAD") == head_before
        status = _git(repo, "status", "--porcelain")
        assert status == "", f"worktree must be clean after an aborted merge, got: {status!r}"
        merge_head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "-q", "--verify", "MERGE_HEAD"],
            capture_output=True,
        )
        assert merge_head.returncode != 0, "no MERGE_HEAD should remain after abort"


# ---------------------------------------------------------------------------
# LanesManifest.planning_commit_sha -- schema round-trip
# ---------------------------------------------------------------------------


class TestPlanningCommitShaSchema:
    def _manifest(self, **overrides: object) -> LanesManifest:
        base: dict[str, object] = {
            "version": 1,
            "mission_slug": MISSION_SLUG,
            "mission_id": MISSION_ID,
            "mission_branch": f"kitty/mission-{MISSION_SLUG}",
            "target_branch": "main",
            "lanes": [],
            "computed_at": "2026-07-29T10:00:00Z",
            "computed_from": "test",
        }
        base.update(overrides)
        return LanesManifest(**base)

    def test_roundtrips_through_to_dict_from_dict(self) -> None:
        manifest = self._manifest(planning_commit_sha="a" * 40)
        data = manifest.to_dict()
        assert data["planning_commit_sha"] == "a" * 40
        restored = LanesManifest.from_dict(data)
        assert restored.planning_commit_sha == "a" * 40

    def test_defaults_to_none_and_survives_legacy_dict_without_the_key(self) -> None:
        manifest = self._manifest()
        assert manifest.planning_commit_sha is None
        assert manifest.to_dict()["planning_commit_sha"] is None

        legacy_data = manifest.to_dict()
        del legacy_data["planning_commit_sha"]  # simulate a pre-WP01 lanes.json
        restored = LanesManifest.from_dict(legacy_data)
        assert restored.planning_commit_sha is None


# ---------------------------------------------------------------------------
# mission_finalize._capture_target_branch_tip -- producer helper
# ---------------------------------------------------------------------------


class TestCaptureTargetBranchTip:
    def test_returns_current_tip_sha(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.agent.mission_finalize import (
            _capture_target_branch_tip,
        )

        repo = tmp_path / "repo"
        _init_repo(repo)
        expected = _git(repo, "rev-parse", "main")

        assert _capture_target_branch_tip(repo, "main") == expected

    def test_returns_none_for_unresolvable_branch(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.agent.mission_finalize import (
            _capture_target_branch_tip,
        )

        repo = tmp_path / "repo"
        _init_repo(repo)

        assert _capture_target_branch_tip(repo, "no-such-branch") is None
