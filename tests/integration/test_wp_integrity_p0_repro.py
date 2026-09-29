"""SC-001 P0 reproduction for #3371: PRIMARY ``lanes.json`` must never land on coord.

write-path-integrity WP02 / T007 (FR-001 / FR-004 / SC-001). This is the
NON-VACUOUS red-first acceptance test for the mission's P0. It composes the
**real** production path -- ``_ensure_planning_artifacts_committed_git`` (the
implement-time planning auto-commit) followed by the real ``allocate_lane_worktree``
lane allocator -- on a coordination-topology, PR-bound (``--start-branch``)
mission, and proves that a PRIMARY-partition ``lanes.json`` is routed to the
mission's primary target branch, never the coordination branch.

Why this is genuinely RED against the pre-fix tree (the mechanism):

* The mission is coordination-topology, so ``_resolve_placement_ref`` threads a
  ``placement_ref`` whose ``.ref`` is the **coordination branch**. Pre-fix, the
  ``placement_ref is not None`` arm of ``_commit_planning_artifacts_transaction``
  committed the WHOLE batch VERBATIM to that coord ref, so the PRIMARY
  ``lanes.json`` landed on the coordination branch (empirically observed:
  ``git ls-tree -r <coord_ref>`` contains ``lanes.json`` -- non-vacuity leg (a)).
* ``lanes.json``'s recorded ``planning_commit_sha`` points at a commit on the
  primary **target** branch that ALSO carries ``lanes.json`` with DIFFERENT
  content (non-vacuity leg (b): the merge genuinely has a real ``lanes.json`` on
  both sides). ``allocate_lane_worktree`` branches the lane off the coordination
  branch (which now carries the mis-routed ``lanes.json``) and merges the
  recorded ``planning_commit_sha`` on top -- an ``add/add`` conflict on
  ``lanes.json`` (both sides add it, no common-ancestor version), which
  ``_merge_recorded_planning_commit`` fails closed with the specific
  ``PlanningCommitMergeConflictError``.

Why ``--start-branch`` / PR-bound is LOAD-BEARING (documented per T007):

1. The recorded planning tip (a commit on the non-protected PR target branch that
   carries ``lanes.json``) and the coordination base (minted BEFORE planning
   exists) genuinely diverge, so the lane-allocation merge is a real ``add/add``
   rather than a fast-forward.
2. The FIX commits the PRIMARY group to the mission's target branch. If that
   target were the default protected ``main``, ``BookkeepingTransaction`` /
   ``safe_commit`` would REFUSE the primary commit and the test could never go
   GREEN. A real ``--start-branch`` mission targets a non-protected feature
   branch, which is exactly what lets the fixed PRIMARY commit succeed.

Post-fix, ``lanes.json`` (PRIMARY) is committed to the target branch and the
coord ref never carries it, so the lane allocation is a clean merge -- GREEN.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import CommitTarget
from specify_cli.cli.commands.implement import _ensure_planning_artifacts_committed_git
from specify_cli.lanes.branch_naming import code_lane_branch_name
from specify_cli.lanes.implement_support import resolve_claim_ancestry_gate
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.worktree_allocator import (
    PlanningCommitMergeConflictError,
    allocate_lane_worktree,
)
from specify_cli.missions._create import ensure_coordination_branch
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from ulid import ULID

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_SLUG = "wp-integrity-p0-repro-01KZZD69"
_MISSION_ID = "01KZZD69REPR0000000000000P"
_MID8 = _MISSION_ID[:8]
_WP_ID = "WP01"
# A real ``--start-branch`` mission targets a NON-protected feature branch (see
# the module docstring, load-bearing reason 2). ``main`` is protected by default
# and would make the fixed PRIMARY commit unreachable.
_TARGET_BRANCH = "pr/write-path-integrity-repro"

_LANES_REL = f"kitty-specs/{_MISSION_SLUG}/lanes.json"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")


def _ls_tree_paths(repo: Path, ref: str) -> set[str]:
    out = _git(repo, "ls-tree", "-r", "--name-only", ref)
    return set(out.splitlines())


def _lanes_json_payload(*, planning_commit_sha: str | None) -> str:
    return json.dumps(
        {
            "version": 1,
            "mission_slug": _MISSION_SLUG,
            "mission_id": _MISSION_ID,
            "mission_branch": f"kitty/mission-{_MISSION_SLUG}",
            "target_branch": _TARGET_BRANCH,
            "lanes": [
                {
                    "lane_id": "lane-a",
                    "wp_ids": [_WP_ID],
                    "write_scope": ["src/**"],
                    "predicted_surfaces": ["core"],
                    "depends_on_lanes": [],
                    "parallel_group": 0,
                }
            ],
            "computed_at": "2026-08-14T00:00:00+00:00",
            "computed_from": "wp-integrity-p0-repro",
            "planning_artifact_wps": [],
            "planning_commit_sha": planning_commit_sha,
        },
        indent=2,
    )


def _write_meta(feature_dir: Path, *, coordination_branch: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": _MISSION_SLUG,
                "mid8": _MID8,
                "mission_type": "software-dev",
                "target_branch": _TARGET_BRANCH,
                "created_at": "2026-08-14T00:00:00+00:00",
                "friendly_name": "write-path-integrity P0 repro",
                "coordination_branch": coordination_branch,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _make_manifest(*, planning_commit_sha: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        mission_branch=f"kitty/mission-{_MISSION_SLUG}",
        target_branch=_TARGET_BRANCH,
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=(_WP_ID,),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-08-14T10:00:00Z",
        computed_from="test",
        planning_commit_sha=planning_commit_sha,
    )


def test_sc001_primary_lanes_json_never_lands_on_coord(tmp_path: Path) -> None:
    """SC-001 / FR-001 / FR-004: a PRIMARY ``lanes.json`` must route to the target
    branch, so lane allocation never add/add-conflicts on it.

    RED (pre-fix): ``lanes.json`` lands on the coordination branch (non-vacuity
    leg (a) below holds), the lane branches off it, and merging the recorded
    ``planning_commit_sha`` (which also carries ``lanes.json`` -- leg (b))
    raises ``PlanningCommitMergeConflictError``. GREEN (post-fix): ``lanes.json``
    lands on the target branch, the coord ref never carries it, and allocation
    is a clean merge.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    # PR-bound (--start-branch): a non-protected feature target branch.
    _git(repo, "branch", _TARGET_BRANCH, "main")
    _git(repo, "checkout", "-q", _TARGET_BRANCH)

    # Mint the coordination branch BEFORE planning exists (mission-create time).
    coord_result = ensure_coordination_branch(
        repo_root=repo,
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        target_branch=_TARGET_BRANCH,
    )
    assert coord_result.created
    coord_branch = coord_result.branch_name

    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "spec.md").write_text("# Spec\n\nSubstantive.\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("## WP01\n\n- [ ] T001\n", encoding="utf-8")
    _write_meta(feature_dir, coordination_branch=coord_branch)
    # ``lanes.json`` committed to the target branch with the FROZEN (pre-repoint)
    # planning_commit_sha value -- this is the version ``planning_commit_sha``
    # will point at (content Y).
    lanes_path = feature_dir / "lanes.json"
    lanes_path.write_text(_lanes_json_payload(planning_commit_sha=None), encoding="utf-8")
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", f"chore: planning artifacts for {_MISSION_SLUG}")
    planning_commit_sha = _git(repo, "rev-parse", "HEAD")

    # Re-point ``lanes.json``'s ``planning_commit_sha`` in the working tree (the
    # exact real churn WP01's own recovery performs) so the working-tree copy
    # (content X) DIFFERS from the committed target copy (content Y). This is the
    # genuine divergence that makes the lane-allocation merge a real add/add.
    lanes_path.write_text(
        _lanes_json_payload(planning_commit_sha=planning_commit_sha), encoding="utf-8"
    )

    # Real production entry point: the implement-time planning auto-commit, with
    # the coordination ``placement_ref`` a healthy coord mission threads.
    _ensure_planning_artifacts_committed_git(
        repo_root=repo,
        feature_dir=feature_dir,
        mission_slug=_MISSION_SLUG,
        wp_id=_WP_ID,
        planning_branch=_TARGET_BRANCH,
        auto_commit=True,
        placement_ref=CommitTarget(ref=coord_branch),
    )

    # --- Non-vacuity leg (b): the recorded planning tip genuinely carries
    # lanes.json, so a merge of it into a lane that also has lanes.json is a real
    # add/add (holds in BOTH pre- and post-fix states; it is fixture provenance).
    assert _LANES_REL in _ls_tree_paths(repo, planning_commit_sha), (
        "non-vacuity precondition (b) violated: the recorded planning_commit_sha "
        "tree must contain lanes.json for the add/add reproduction to be real."
    )

    # --- SC-001 (FR-001) + non-vacuity leg (a) folded in: PRIMARY lanes.json must
    # NOT be on the coordination ref. RED pre-fix (it IS on coord -- leg (a)
    # holds and this assertion fails); GREEN post-fix.
    coord_paths = _ls_tree_paths(repo, coord_branch)
    assert _LANES_REL not in coord_paths, (
        "SC-001 regression: PRIMARY lanes.json was committed onto the coordination "
        f"branch {coord_branch!r} (#3371 P0). coord tree: {sorted(coord_paths)!r}"
    )
    # And it MUST be on the primary target branch (routed correctly, not dropped).
    assert _LANES_REL in _ls_tree_paths(repo, _TARGET_BRANCH), (
        "PRIMARY lanes.json must land on the primary target branch "
        f"{_TARGET_BRANCH!r}."
    )

    # --- SC-001 acceptance: the real lane allocator must NOT raise the specific
    # add/add ``PlanningCommitMergeConflictError`` (never asserted as a generic
    # non-zero). Pre-fix this raises; post-fix it is a clean merge.
    manifest = _make_manifest(planning_commit_sha=planning_commit_sha)
    try:
        worktree_path, _lane_branch = allocate_lane_worktree(
            repo_root=repo,
            mission_slug=_MISSION_SLUG,
            wp_id=_WP_ID,
            lanes_manifest=manifest,
        )
    except PlanningCommitMergeConflictError as exc:  # pragma: no cover -- RED path
        pytest.fail(
            "SC-001 P0 (#3371) reproduced: allocate_lane_worktree add/add-conflicted "
            f"on the recorded planning commit because PRIMARY lanes.json was "
            f"mis-routed onto the coordination branch: {exc}"
        )
    assert worktree_path.exists()


# ---------------------------------------------------------------------------
# T013 backup — #3281 end-to-end: retry re-enters self-heal to establish
# post-materialize claim ancestry for a late-landing dependency (FR-005/
# FR-007/C-005). This is a BACKUP integration proof, not the sole one -- the
# focused unit coverage lives in
# tests/specify_cli/cli/commands/agent/test_claim_ancestry_gate.py.
# ---------------------------------------------------------------------------

_ANCESTRY_MISSION_SLUG = "wp-integrity-ancestry-backup-01KZZE00"
_ANCESTRY_WP_DEP = "WP01"
_ANCESTRY_WP_SELF = "WP02"


def _ancestry_feature_dir(repo: Path) -> Path:
    return repo / "kitty-specs" / _ANCESTRY_MISSION_SLUG


def _write_ancestry_meta_and_lanes(repo: Path) -> None:
    """Legacy (no ``coordination_branch``) mission -- PRIMARY and STATUS
    dirs coincide, keeping this backup fixture small (see the unit test's
    matching helper for the full rationale)."""
    feature_dir = _ancestry_feature_dir(repo)
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01KZZE00ANCESTRYBACKUP0000",
                "mission_slug": _ANCESTRY_MISSION_SLUG,
                "mid8": "01kzze00",
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-08-26T00:00:00+00:00",
                "friendly_name": "ancestry backup test",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (feature_dir / "lanes.json").write_text(
        json.dumps(
            {
                "version": 1,
                "mission_slug": _ANCESTRY_MISSION_SLUG,
                "mission_id": "01KZZE00ANCESTRYBACKUP0000",
                "mission_branch": f"kitty/mission-{_ANCESTRY_MISSION_SLUG}",
                "target_branch": "main",
                "lanes": [
                    {
                        "lane_id": "lane-a",
                        "wp_ids": [_ANCESTRY_WP_DEP],
                        "write_scope": ["src/**"],
                        "predicted_surfaces": ["core"],
                        "depends_on_lanes": [],
                        "parallel_group": 0,
                    },
                    {
                        "lane_id": "lane-b",
                        "wp_ids": [_ANCESTRY_WP_SELF],
                        "write_scope": ["src/**"],
                        "predicted_surfaces": ["core"],
                        "depends_on_lanes": ["lane-a"],
                        "parallel_group": 1,
                    },
                ],
                "computed_at": "2026-08-26T00:00:00+00:00",
                "computed_from": "test",
                "planning_artifact_wps": [],
                "planning_commit_sha": None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "chore: ancestry backup planning artifacts")


def _ancestry_manifest(repo: Path) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_ANCESTRY_MISSION_SLUG,
        mission_id="01KZZE00ANCESTRYBACKUP0000",
        mission_branch=f"kitty/mission-{_ANCESTRY_MISSION_SLUG}",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=(_ANCESTRY_WP_DEP,),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            ),
            ExecutionLane(
                lane_id="lane-b",
                wp_ids=(_ANCESTRY_WP_SELF,),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=("lane-a",),
                parallel_group=1,
            ),
        ],
        computed_at="2026-08-26T00:00:00Z",
        computed_from="test",
    )


def test_3281_retry_reenters_self_heal_to_establish_post_materialize_ancestry(
    tmp_path: Path,
) -> None:
    """End-to-end (backup) proof of the #3281 fix, chaining T008 + T011 + T012:

    1. lane-b is allocated FRESH while its dependency, lane-a, does not exist
       yet (a realistic ordering -- lane-b's WP was claimable before lane-a's
       dependency work landed and got approved). The fresh-path dependency
       merge skips the not-yet-existing lane-a branch with a warning.
    2. lane-a's branch is then created and its WP is marked APPROVED.
    3. A RETRY over lane-b's now-EXISTING worktree, through the real
       ``resolve_claim_ancestry_gate`` (the same shared predicate every claim
       site calls), re-enters the idempotent self-heal -- which merges
       lane-a's now-real tip -- and the ancestry check passes. This is the
       exact #3281 defect: a bare ``workspace.exists`` short-circuit would
       never have re-run the merge, leaving lane-b claimed without lane-a's
       code (FR-007's "ancestry-blind claim").
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_ancestry_meta_and_lanes(repo)
    manifest = _ancestry_manifest(repo)

    # Step 1: fresh allocation of lane-b BEFORE lane-a exists.
    lane_b_worktree, _lane_b_branch = allocate_lane_worktree(
        repo_root=repo,
        mission_slug=_ANCESTRY_MISSION_SLUG,
        wp_id=_ANCESTRY_WP_SELF,
        lanes_manifest=manifest,
    )
    assert lane_b_worktree.exists()
    assert not (lane_b_worktree / "lane_a_output.txt").exists()

    # Step 2: lane-a's dependency work lands and is approved.
    lane_a_branch = code_lane_branch_name(_ANCESTRY_MISSION_SLUG, "lane-a")
    _git(repo, "branch", lane_a_branch, "main")
    _git(repo, "checkout", "-q", lane_a_branch)
    (repo / "lane_a_output.txt").write_text("lane-a code\n", encoding="utf-8")
    _git(repo, "add", "lane_a_output.txt")
    _git(repo, "commit", "-q", "-m", "lane-a: write output")
    _git(repo, "checkout", "-q", "main")

    feature_dir = _ancestry_feature_dir(repo)
    append_event(
        feature_dir,
        StatusEvent(
            event_id=str(ULID()),
            mission_slug=_ANCESTRY_MISSION_SLUG,
            wp_id=_ANCESTRY_WP_DEP,
            from_lane=Lane.PLANNED,
            to_lane=Lane.APPROVED,
            at="2026-08-26T00:00:00+00:00",
            actor="test",
            force=False,
            execution_mode="worktree",
            mission_id="01KZZE00ANCESTRYBACKUP0000",
        ),
    )

    # Step 3: the retry, through the real shared gate.
    bare = resolve_claim_ancestry_gate(
        repo, _ANCESTRY_MISSION_SLUG, feature_dir, _ANCESTRY_WP_SELF, lane_b_worktree
    )
    assert bare.ok is True, (
        f"retry must re-enter self-heal and establish ancestry: {bare.missing_refs}"
    )
    assert (lane_b_worktree / "lane_a_output.txt").exists(), (
        "self-heal must have actually merged lane-a's tip into lane-b's worktree"
    )
