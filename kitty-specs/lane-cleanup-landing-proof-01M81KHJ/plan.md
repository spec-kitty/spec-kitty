# Implementation Plan: One landing proof for lane cleanup

**Branch**: `kitty/mission-lane-cleanup-landing-proof-01M81KHJ` (Mission topic branch) → lands on `fix/7747-lane-cleanup-landing-proof` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/lane-cleanup-landing-proof-01M81KHJ/spec.md`

Planning questions were answered by operator rulings (2026-11-22 "Ancestor blob + keep-code", 2026-11-23 Option A; Decision Moments 01M81KHZ, 01M81KJ2, 01M81KJ5, 01M81KJ7, 01M81KXB). No open question remains.

## Summary

Lane cleanup (consolidate) and `doctor workspaces --prune` judge a lane through one public landing proof in `src/specify_cli/lanes/lane_tip.py`. A lane is landed when its tip is an ancestor of the landing ref, or when every lane difference is accounted for: paths outside `kitty-specs/` by an in-memory merge that changes nothing on the landing ref, and paths under `kitty-specs/` by explicit rules that never read a merge result. The four bookkeeping kinds of the lane's own Mission are set aside only when the lane never authored its copy, read from the lane's own commit graph (Option A). Separately, `GuardedLaneRemover` keeps a lane with `LANDING_PROOF_UNAVAILABLE` instead of handing it to the older remover when it has no usable landing proof (#7325).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: git ≥ 2.38 (`merge-tree --write-tree`) through `kernel.git` (`run_git`, `merge_tree`, `changed_paths`, `tree_entry`); no new dependency
**Storage**: git objects and refs only; nothing written by the proof
**Testing**: pytest; real git repositories (synthetic fixtures for unit rules, the real-CLI `build()` harness of `tests/integration/test_default_mission_consolidate_lands_primary.py` for the red-first acceptance)
**Target Platform**: Linux, macOS, Windows (pure git calls; the process probe stays the caller's)
**Project Type**: single (the `spec-kitty` CLI)
**Performance Goals**: one lane proof under 2 s on a 12-WP fixture (NFR-001): two `rev-list` calls, one `diff-tree` per lane-own commit, one `merge-tree`, one path-limited history walk per candidate bookkeeping file
**Constraints**: no guard change (C-001); fail closed on any git error; no merge or merge-driver result counts for `kitty-specs/**` (FR-004)
**Scale/Scope**: three source modules, one ADR amendment

## Charter Check

- **Single canonical authority**: one public predicate replaces the private `_absorbed_but_for_status_log`; doctor and consolidate share it (FR-001). Pass.
- **Architectural alignment**: the predicate lives in `specify_cli.lanes` beside `is_absorbed`; callers stay the evidence suppliers the ADR 2026-11-06-1 guard expects (C-005 of that ADR). No layer rule changes. Pass.
- **ATDD-first**: each WP opens with a failing acceptance test committed before code (red-first list in research.md). Pass.
- **Tiered rigour**: the proof is a destructive-op safety predicate, so every branch gets a direct unit test (NFR-002). Pass.
- **Terminology**: Mission, lane, landing proof, set aside; no `feature`. Pass.
- **Sonar**: complexity ≤ 15 per function; the predicate is split into small helpers. Pass.
- **Test policy**: targeted suites plus the named architectural gate (`tests/architectural/test_destructive_op_routing.py`); no full sweeps. Pass.

## Project Structure

### Documentation (this mission)

```
kitty-specs/lane-cleanup-landing-proof-01M81KHJ/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/landing-proof.md
└── tasks.md            # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/lanes/lane_tip.py                    # the public predicate (+ private helpers)
src/specify_cli/consolidation/lane_cleanup.py        # _absorbed adopts it; #7325 kept legs
src/specify_cli/workspace/landed_worktrees.py        # doctor adopts it for released Mission lanes
docs/adr/4.x/2026-11-06-1-a-destructive-git-operation-discharges-named-proof-obligations.md  # O3 amendment
tests/lanes/test_lane_tip_mission_bookkeeping.py     # unit rules of the predicate
tests/integration/test_lane_cleanup_landing_proof_7747.py   # red-first: real squash landing, every lane Removed
tests/consolidation/test_lane_cleanup_auto_rebase_6736.py   # re-pinned import only
tests/consolidation/test_lane_remover_proof_unavailable_7325.py
tests/specify_cli/workspace/test_landed_worktrees_mission_bookkeeping.py
```

**Structure Decision**: single project; changes stay in the three modules that own lane landing evidence.

## Complexity Tracking

None.

## Recorded Decisions

- **PD-1, retained-branch leg (Decision Moment 01M84SX5).** With `retain_branches`, cleanup removes the worktree and deletes no branch. That leg stays on today's guarded worktree removal (`MainTodayRemover`, `guarded_worktree_remove`) and is not kept with `LANDING_PROOF_UNAVAILABLE`, because no branch is deleted, so it is not the #7325 blind spot, and the FR-033 retention report is unchanged. Operator ruling 2026-11-23 (4A): PD-1 stands; the operator is the decider (Decision Moment 01M84WXRW53P3VQ0BEEV9P5VR6). To flip it, remove the `item.branch is None` hand-off in `GuardedLaneRemover.remove`, so that the leg falls into the proof-unavailable check.

## Implementation Concern Map

- **IC-01 Landing proof predicate.** `is_absorbed_but_for_mission_bookkeeping(repo_root, tip, landing_ref, mission_slug)` in `lanes/lane_tip.py` with the status-log containment check moved from `lane_cleanup.py`. Owns FR-002 to FR-005.
- **IC-02 Consolidate adoption.** `GuardedLaneRemover._absorbed` calls the predicate when it knows the Mission slug, plain `is_absorbed` otherwise; the private status-log proof is deleted. Owns FR-006.
- **IC-03 Doctor adoption.** `landed_worktrees` resolves the slug of a released Mission lane and uses the predicate for its assessment (`_absorption`) and for the guard's proof (`_absorption_proof`); other worktrees keep the plain proof. Owns FR-007.
- **IC-04 Kept legs (#7325).** `GuardedLaneRemover.remove` keeps a lane with `LANDING_PROOF_UNAVAILABLE` when the landing proof is missing, its PASS anchor is empty, the worktree is gone while the branch remains, or no tip can be named. A retained-branch leg (worktree only) keeps today's worktree removal, which deletes no branch. Owns FR-008.
- **IC-05 Decision record.** ADR 2026-11-06-1 amendment to O3: the Mission-file set-aside, the #6736 status-log set-aside, the own-graph authorship rule and its residual. Owns FR-009.
