"""Issue #2993: a fresh lane worktree used to not descend from the
mission's own planning artifacts (spec.md/tasks.md/meta.json).

Formerly a red-first ``@pytest.mark.regression`` reproduction; relocated
here and un-marked (landing fold: make ``@pytest.mark.regression`` mean
exactly one thing) once the fix landed and this test started passing.
#2993 is fixed — this is now a permanent guard, not a red-first pin.

Root cause (traced against ``main`` @ upstream/main, WP03 read-side-seam
mission): ``_ensure_planning_artifacts_committed_git``
(``src/specify_cli/cli/commands/implement.py:626-714``) decides what to
auto-commit onto the coordination branch via
``resolve_planning_artifact_staging`` (``implement_cores.py:544-609``). When
the planning artifacts are *already* committed on the planning/primary
branch (the normal spec -> plan -> tasks authoring flow, NOT a dirty
uncommitted edit), ``git status --porcelain`` is clean, so
``_status_paths_for_commit`` contributes nothing. The only other source is
``extra_file_paths`` (a plain filesystem walk of every file currently under
the mission dir), which is then filtered by
``_files_changed_vs_precondition_ref`` -> ``resolve_precondition_ref``
(``implement_cores.py:299-327``). ``resolve_precondition_ref`` classifies
``spec.md`` / ``tasks.md`` / ``meta.json`` as PRIMARY-kind (not
``is_coord_residue_churn``), so they are diffed against ``HEAD`` -- the
planning branch itself, where they are already committed and therefore
byte-identical. They are silently dropped from ``files_to_commit``, which
becomes empty, and the function no-ops (``implement.py:691-692``). The
coordination branch's tip is left exactly where ``ensure_coordination_branch``
minted it -- BEFORE the planning artifacts ever existed. When
``allocate_lane_worktree`` later branches the lane off that coordination
branch (``worktree_allocator.py:213-216``, ``_ensure_branch_exists`` is a
no-op because the branch already exists, ``_create_lane_worktree`` runs
``git worktree add -b <lane> <path> <coordination_branch>``), the resulting
lane branch never contains the planning artifacts at all.

This test drives four real production entry points, in the order below.
Empirically (instrumented run against this exact sequence), this test
reproduces **Cause B** (the silent no-op) of the two independent causes
triage identified for #2993, not Cause A (the copy-onto-coordination-branch
path):

```
coord tip at mint: 71cffbdd38ff...
helper returned: None
coord tip AFTER helper: 71cffbdd38ff...  (moved: False)
git log --oneline <coord> -- kitty-specs/<slug>/  =>  ''
=> CAUSE B (silent no-op)
```

1. ``ensure_coordination_branch`` -- mint the coord branch BEFORE the
   planning artifacts exist.
2. A normal ``git commit`` of ``kitty-specs/<slug>/{spec.md,tasks.md,
   meta.json}`` onto the planning branch (captures the sha).
3. ``_ensure_planning_artifacts_committed_git`` -- the auto-commit helper.
   This test is parametrized over BOTH production call shapes of
   ``implement()`` (``_ensure_planning_artifacts_committed_git(...,
   placement=_placement)``):

   - ``legacy-fallback`` (an unresolved placement): what
     ``resolve_planning_placement`` returns when the WP context hits an
     ``ActionContextError`` (#5232); its coordination filter is the declared
     ``coordination_branch`` (R-1b). Under this precondition (artifacts
     already committed on ``HEAD``, so ``git status --porcelain`` is clean)
     the call is a proven no-op that reproduces **Cause B** -- the coord
     branch tip never moves past its pre-artifact mint point.
   - ``placement-ref`` (a resolved placement on ``CommitTarget(ref=coord_branch)``):
     the path a HEALTHY mission takes, where ``resolve_planning_placement``
     resolves a ``CommitTarget``. This drives
     ``_commit_planning_artifacts_transaction``'s resolved arm, which commits
     the planning-artifact files VERBATIM onto
     ``placement.ref.ref`` via ``_run_planning_artifact_commit`` -- a plain
     content copy, not a git merge/cherry-pick from the planning-branch
     commit. This reproduces **Cause A** -- the coord branch tip DOES move
     (a new commit lands on it), but that commit has no ancestry
     relationship to the planning-artifact commit on the planning branch.

   Both arms leave the lane branch failing Assert A below, for two
   genuinely different reasons: Cause B never advances the coord tip at
   all; Cause A advances it with a disconnected copy. #2993's triage
   requires a fix to close both.
4. ``allocate_lane_worktree`` -- the real WP04 lane allocator.

Discriminator caveat: the triage note's ``git log --oneline
<coordination-branch> -- kitty-specs/<slug>/`` heuristic (non-empty =>
Cause A, empty => Cause B) is a sound *pre-fix* triage signal only. Once
ancestry is genuinely established -- the fix this pin demands -- the
planning-artifact commit legitimately appears in the coordination branch's
history for that path (it is an ancestor, so it is "on" the branch), and
the same heuristic reports "Cause A" for a correctly-fixed repo. Do not
re-open #2993 on that false positive post-fix; check ancestry (Assert A
below), not log non-emptiness.

Coord-descent guard: Assert A alone only requires the lane branch to
descend from the planning-artifact commit. A fix that satisfies Assert A by
branching lanes off ``main`` (which also contains the planning artifacts,
since they are committed there) would satisfy Assert A while silently
severing the lane from the mission's coordination branch -- discarding
coordination-branch lifecycle state (status events, WP claim history) this
repo's coord/primary partition depends on. #2993 does sanction "branch
lanes off the planning-artifact commit" as one legitimate fix shape, so this
guard is not forbidding that option outright -- it is requiring that
whichever commit the lane branches from, the lane must ALSO still descend
from ``coord_branch``, so a fix cannot silently trade one defect (missing
planning artifacts) for another (an orphaned lane that never sees coord
state). This is checked immediately after Assert A (so Assert A keeps
firing first) via ``git merge-base --is-ancestor <coord_branch>
<lane_branch>``.

Related existing coverage this test does NOT contradict:
``tests/specify_cli/cli/commands/test_implement.py:471-545``
(``TestPlanningArtifactAutoCommit.test_auto_commit_uses_coordination_worktree_paths``)
pins a *different* precondition: there the planning artifact is written to
disk but never committed on the planning branch, so it IS picked up by
``git status --porcelain`` and correctly lands on the coordination branch.
That assertion is not disturbed here -- this test's planning artifacts are
committed BEFORE the auto-commit helper runs, which is the gap the existing
test does not cover. Whoever fixes #2993 should re-adjudicate that test only
if the fix changes what counts as "already committed" for the idempotency
filter.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import CommitTarget
from specify_cli.cli.commands.implement_planning_commit import _ensure_planning_artifacts_committed_git
from specify_cli.coordination.planning_commit import PlanningPlacement
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.missions._create import ensure_coordination_branch

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MISSION_SLUG = "annoying-bugs-sweep-01KYHQ9F"
MISSION_ID = "01KYHQ9FTN3W7C5J4K2M6R8QDS"
MID8 = MISSION_ID[:8]
WP_ID = "WP03"
# write-path-integrity WP02 re-baseline: a coord mission's PRIMARY planning
# artifacts now commit to the mission's TARGET branch (FR-001), which must be a
# NON-protected feature branch -- committing planning artifacts to the protected
# default ``main`` is refused by ``BookkeepingTransaction``/``safe_commit`` (the
# same invariant the mission's narrow-triple encodes). This test's target branch
# was incidentally ``main`` pre-fix (when planning artifacts were mis-routed to
# coord); it now uses a real ``--start-branch``-shaped feature target so the
# fixed PRIMARY commit lands on it. The ancestry contract under test is
# unchanged.
TARGET_BRANCH = "mission/annoying-bugs-sweep"


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


def _write_meta(feature_dir: Path, *, coordination_branch: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "mission_id": MISSION_ID,
        "mission_slug": MISSION_SLUG,
        "mid8": MID8,
        "mission_type": "software-dev",
        "target_branch": TARGET_BRANCH,
        "created_at": "2026-07-28T00:00:00+00:00",
        "friendly_name": "Annoying bugs sweep",
        "coordination_branch": coordination_branch,
    }
    (feature_dir / "meta.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def _make_manifest(
    coordination_branch: str, *, planning_commit_sha: str | None = None
) -> LanesManifest:
    """Build the lanes.json fixture this test hand-constructs.

    ``planning_commit_sha`` defaults to ``None`` (pre-WP01 shape) so any other
    caller of this helper keeps exercising the legacy no-recorded-SHA path
    unchanged. WP01 (FR-009 / #2993 / ADR ``2026-07-29-1``) fix landed: the
    production ``lanes.json`` writer (``mission_finalize._compute_and_write_lanes``)
    now ALWAYS populates this field at finalize-tasks time, so
    ``test_lane_worktree_does_not_descend_from_planning_artifacts`` below passes
    the real ``planning_artifact_sha`` it committed to reproduce that contract
    faithfully (this test bypasses the finalize-tasks command entirely and
    constructs the manifest by hand, so it must mirror what that command would
    have written).
    """
    return LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        mission_branch=coordination_branch,
        target_branch=TARGET_BRANCH,
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
        computed_at="2026-07-28T10:00:00Z",
        computed_from="test",
        planning_commit_sha=planning_commit_sha,
    )


@pytest.mark.parametrize(
    "use_placement_ref",
    [False, True],
    ids=["legacy-fallback", "placement-ref"],
)
def test_lane_worktree_does_not_descend_from_planning_artifacts(
    tmp_path: Path,
    use_placement_ref: bool,
) -> None:
    """Pin #2993: the lane branch must contain the mission's own planning
    artifacts. Today it does not, on EITHER of the two production call
    shapes ``implement.py:1706`` can take:

    - ``legacy-fallback`` (``use_placement_ref=False``): the unresolved
      placement taken when the WP context fails to resolve with an
      ``ActionContextError`` -- reproduces Cause B (silent no-op, coord
      tip never moves).
    - ``placement-ref`` (``use_placement_ref=True``): the path a healthy
      mission takes, where a resolved ``CommitTarget`` is threaded through
      -- reproduces Cause A (the coord tip moves, but via a disconnected
      verbatim copy, not a merge/cherry-pick preserving ancestry).
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    # PR-bound (--start-branch) target: a non-protected feature branch (WP02).
    _git(repo, "branch", TARGET_BRANCH, "main")
    _git(repo, "checkout", "-q", TARGET_BRANCH)

    # Step 1: mint the coordination branch BEFORE the planning artifacts exist.
    coord_result = ensure_coordination_branch(
        repo_root=repo,
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        target_branch=TARGET_BRANCH,
    )
    assert coord_result.created
    coord_branch = coord_result.branch_name

    # Step 2: commit the planning artifacts on the planning (primary) branch
    # -- a normal, already-committed spec/tasks authoring commit, not a dirty
    # uncommitted edit.
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    (feature_dir).mkdir(parents=True, exist_ok=True)
    (feature_dir / "spec.md").write_text(
        "# Annoying bugs sweep\n\n"
        "## NFR-002 Retracted Constraint\n\n"
        "This constraint block must be removed after correction.\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "## WP03 Ledger grammar and census\n\n- [ ] T001 Draft grammar\n",
        encoding="utf-8",
    )
    _write_meta(feature_dir, coordination_branch=coord_branch)
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", f"docs: spec+tasks for {MISSION_SLUG}")
    planning_artifact_sha = _git(repo, "rev-parse", "HEAD")

    # Step 3: run the real auto-commit helper. ``placement`` reproduces the
    # value ``implement()`` threads through in production: an unresolved
    # placement on the legacy-fallback arm (context resolution failed; the
    # seam's coordination filter is the declared coordination branch), or a resolved ``CommitTarget(ref=coord_branch)``
    # on the healthy-mission arm (mirrors what ``resolve_planning_placement``
    # returns for a mission whose ``meta.json`` carries this mission's own
    # ``coordination_branch`` -- exactly the fixture state written by
    # ``_write_meta`` above).
    placement = (
        PlanningPlacement(resolved=True, ref=CommitTarget(ref=coord_branch))
        if use_placement_ref
        else PlanningPlacement(resolved=False, ref=None)
    )
    _ensure_planning_artifacts_committed_git(
        repo_root=repo,
        feature_dir=feature_dir,
        mission_slug=MISSION_SLUG,
        wp_id=WP_ID,
        planning_branch=TARGET_BRANCH,
        auto_commit=True,
        placement=placement,
    )

    # Step 4: allocate the lane worktree -- the real WP04 lane allocator.
    # planning_commit_sha mirrors what mission_finalize._compute_and_write_lanes
    # would have recorded at finalize-tasks time (WP01 / FR-009 / ADR
    # 2026-07-29-1) -- this test bypasses that command and constructs
    # lanes.json by hand, so it must supply the same value.
    manifest = _make_manifest(coord_branch, planning_commit_sha=planning_artifact_sha)
    worktree_path, lane_branch = allocate_lane_worktree(
        repo_root=repo,
        mission_slug=MISSION_SLUG,
        wp_id=WP_ID,
        lanes_manifest=manifest,
    )
    assert worktree_path.exists()

    # Assert A -- ancestry: the lane branch must descend from the commit that
    # introduced the planning artifacts.
    ancestry = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "merge-base",
            "--is-ancestor",
            planning_artifact_sha,
            lane_branch,
        ],
        capture_output=True,
        text=True,
    )
    assert ancestry.returncode == 0, (
        f"lane branch {lane_branch!r} should descend from the planning-artifact "
        f"commit {planning_artifact_sha}, but `git merge-base --is-ancestor` "
        f"returned {ancestry.returncode} (stderr: {ancestry.stderr!r}). This is "
        "the #2993 defect: the coordination branch tip was never advanced past "
        "its pre-artifact mint point before the lane branched off it."
    )

    # Assert A' -- coord-descent guard: a fix must not satisfy Assert A by
    # severing the lane from the mission's coordination branch (e.g. by
    # branching lanes off ``main`` instead). The lane must ALSO still
    # descend from ``coord_branch``, so coordination-branch lifecycle state
    # (status events, WP claim history) is never discarded as a side effect
    # of restoring planning-artifact ancestry. Ordered after Assert A so
    # Assert A keeps firing first.
    coord_ancestry = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "merge-base",
            "--is-ancestor",
            coord_branch,
            lane_branch,
        ],
        capture_output=True,
        text=True,
    )
    assert coord_ancestry.returncode == 0, (
        f"lane branch {lane_branch!r} should still descend from the mission's "
        f"coordination branch {coord_branch!r}, but `git merge-base "
        f"--is-ancestor` returned {coord_ancestry.returncode} (stderr: "
        f"{coord_ancestry.stderr!r}). A fix for #2993 must not restore "
        "planning-artifact ancestry by orphaning the lane from coordination "
        "branch lifecycle state."
    )

    # Assert B -- silent-revert half: amend tasks.md on the planning branch
    # AFTER the lane exists, then union-merge the two branches. A healthy
    # lane (containing the original tasks.md as an ancestor state) merges
    # cleanly and picks up the amendment. Today the lane's tree has no
    # tasks.md at all, so the merge fabricates a stale/absent result instead
    # of the amended text.
    (feature_dir / "tasks.md").write_text(
        "## WP03 Ledger grammar and census (amended)\n\n"
        "- [ ] T001 Draft grammar\n- [ ] T002 Census sweep\n",
        encoding="utf-8",
    )
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "docs: amend tasks.md for WP03")

    merge_tree = subprocess.run(
        ["git", "-C", str(repo), "merge-tree", "--write-tree", lane_branch, TARGET_BRANCH],
        capture_output=True,
        text=True,
    )
    assert merge_tree.returncode == 0, (
        "expected a clean union-merge between the lane branch and the amended "
        f"planning branch under kitty-specs/, got a conflict:\n{merge_tree.stdout}"
        f"\n{merge_tree.stderr}"
    )
    merged_tree_sha = merge_tree.stdout.strip().splitlines()[0]

    show = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "show",
            f"{merged_tree_sha}:kitty-specs/{MISSION_SLUG}/tasks.md",
        ],
        capture_output=True,
        text=True,
    )
    assert show.returncode == 0, (
        f"tasks.md missing from the union-merge tree entirely: {show.stderr!r}"
    )
    assert show.stdout == (
        "## WP03 Ledger grammar and census (amended)\n\n"
        "- [ ] T001 Draft grammar\n- [ ] T002 Census sweep\n"
    ), (
        "the union-merge should carry forward the amended tasks.md; instead it "
        f"kept the lane's stale copy:\n{show.stdout!r}"
    )

    # Assert C -- deletion-only half. #2993's acceptance criteria singles this
    # out as "the sharp case, since it vanishes under a union merge": delete
    # (not amend) the NFR-002 block from spec.md on the planning branch AFTER
    # the lane exists, then union-merge the two branches. A phrase-presence
    # check (like Assert B's) cannot see a resurrected deletion -- only a
    # phrase-ABSENCE check can. A healthy lane must let the deletion win; a
    # lane carrying a stale/frozen copy of the pre-deletion text risks a
    # naive conflict resolution silently reviving text the mission owner
    # deliberately retracted.
    (feature_dir / "spec.md").write_text("# Annoying bugs sweep\n", encoding="utf-8")
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "docs: retract NFR-002 for WP03")

    deletion_merge_tree = subprocess.run(
        ["git", "-C", str(repo), "merge-tree", "--write-tree", lane_branch, TARGET_BRANCH],
        capture_output=True,
        text=True,
    )
    assert deletion_merge_tree.returncode == 0, (
        "expected a clean union-merge between the lane branch and the "
        f"deletion-carrying planning branch, got a conflict:\n{deletion_merge_tree.stdout}"
        f"\n{deletion_merge_tree.stderr}"
    )
    deletion_merged_tree_sha = deletion_merge_tree.stdout.strip().splitlines()[0]

    deletion_show = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "show",
            f"{deletion_merged_tree_sha}:kitty-specs/{MISSION_SLUG}/spec.md",
        ],
        capture_output=True,
        text=True,
    )
    assert deletion_show.returncode == 0, (
        f"spec.md missing from the union-merge tree entirely: {deletion_show.stderr!r}"
    )
    assert "NFR-002 Retracted Constraint" not in deletion_show.stdout, (
        "the union-merge silently resurrected a block that was deleted on the "
        f"planning branch after the lane existed:\n{deletion_show.stdout!r}"
    )
