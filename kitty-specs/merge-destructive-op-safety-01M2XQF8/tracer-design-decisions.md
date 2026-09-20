# Tracer — Design Decisions

Mission: Merge/Git Destructive-Operation Safety (#4752, #4753, #4754)

## Seed (planning)

- **DD-1 (Decision `guard_strategy`): Unify, not patch-3.** One guard primitive in
  `src/specify_cli/git/` (plumbing-pure per C-005; caller injects the churn
  classifier). Rationale: closes the defect class by construction; avoids minting a
  10th parallel dirty predicate.
- **DD-2: New typed refusal, do NOT overload `SafeCommitHeadMismatch`.** Model on
  `RefAdvanceDirtyWorktreeError` (error_code + remediation). Rationale: the commit
  mismatch exception has ≥6 downstream catchers whose semantics must not shift
  (whack-a-field risk mapped by the surface lens).
- **DD-3 (Decision `adjacent_surface_scope`): Fold coord-teardown + orchestrator-api
  cleanup mirror through `remove_workspace`; defer `branch -D`.** Rationale: the two
  folds are the same seam/defect class (would be the next whack-a-field); `branch -D`
  is a distinct loss surface (committed history, needs an is-merged guard).
- **DD-4: Refusal must be atomic (NFR-001).** The guard fires BEFORE any ref advance
  or destructive op — not a post-hoc restore. For #4752 this means asserting
  HEAD==target and clean in the lane-merge preflight, before `_phase_mission_to_target`
  advances the ref.
- **DD-5: Residue honesty (NFR-003).** The guard must accept the same
  `is_toolchain_generated_churn` injection the merge paths already use, or it
  false-blocks safe merges (the #2795/FR-012 trap, in reverse).

## Appended during implement

_(to be filled per WP)_

## Appended (post-tasks squad, brownfield-driven re-scope)

- **DD-6: `core/vcs/git.py remove_workspace` is DEAD** (zero callers, not on the
  destroy path). The chokepoint is a NEW shared `guarded_worktree_remove` helper in
  WP01 that the live inline destroys (executor lane cleanup, coordination teardown +
  stale-prune, orchestrator cleanup) route through. WP02 re-scoped off `core/vcs/`.
- **DD-7: preflight runs in the OUTER `_run_lane_based_merge` before `_phase_merge_lanes`**
  (not at the `_phase_mission_to_target` seam) — two phases already mutate before
  that seam, so only the top placement makes NFR-001 byte-identical. Resolve
  mission_id from meta at that early point.
- **DD-8: WP05 gate baseline must come from a LIVE census** — a hand-written
  allowlist was factually wrong (missing sites + a phantom); the gate reds on
  untouched sites unless each is adjudicated with an inline rationale.
