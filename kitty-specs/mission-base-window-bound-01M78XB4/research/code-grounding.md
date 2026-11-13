# #7560 code grounding

## Root cause (verified)
The #6771 declaration guard (`consolidation/reconciliation_closed_world.py`) bounds every walk at
`window_base` = the target branch's pre-run tip (`claim_inputs.ClaimInputs.target_base`;
fresh run `phase_claim._resolve_pre_mutation_target_sha` → `capture_branch_tip(refs/heads/<target>)`;
forecast `forecast.py:429` `resolve_commit(<target>)`; resume `state.pre_mutation_target_sha`):

- `_mission_spines`: `rev-list --first-parent <window_base>..<mission_branch>` (`:217`)
- dependency window: `rev-list <window_base>..<ref>` (`_verify_declared_ref`, `:433`)
- `_recorded_work_hit`: `rev-list --first-parent <window_base>..<recorded tip>` (`:314`)

`A..B` drops only ancestors of A. When the local target tip does NOT descend from the commit the
Mission branch was cut from, pre-base history lands on "the mission branch's first-parent spine"
and in the declared ref's window → `DEPENDENCY_REF_COVERS_MISSION_WORK`.

Nothing records the Mission's base commit (only branch names: `mission_branch`, `target_branch`,
`create_return_branch`); `WorkspaceContext.base_commit` is the per-lane allocation tip (above
planning commits); `lanes.json planning_commit_sha` is the finalize pin.

## Shapes that put the base outside the target (fork maintainers)
1. `--pr-bound` with `--start-branch` cut from upstream/origin/HEAD; lands on local fork target that lacks upstream commits (report 1).
2. Mission/topic branch created on upstream pin + overlay, local target never got it (report 2; reproduced, scratch `repro.py`: refusal names `base^` exactly).
3. Local target rewritten/reset after create; 4. `--target` override / stale persisted target.

## Same lower bound on other axes
`excluded_window_base` also feeds the closed-world scan (`reconciliation_verifier._unattributable_in`),
the squash blob/deletion axes (`_window_has_non_bookkeeping_change`, `_unattributable_content_squash`),
the patch-id window, `_bound_claim_base` (approved bound) and `_closed_world_anchors`. Report 2's
155 phantom deletions are the same cause (inference; not yet reproduced end to end).
After the spine fix alone, report 2 still fails the merge closed world: the overlay commit (base
itself) is in `target..mission_branch` and in no declared ref's window.

## History
Refusal code, spine walk and its inputs are byte-identical between `bcd2afa03` (worked 2026-11-08)
and `v4.0.0rc8`. Data-shape dependent, not a code regression. `reconciliation_closed_world.py` and
`claim_inputs.py` are post-rc8 extractions of `reconciliation.py`.

## Overlap
PR #7596 (open) touches `reconciliation_closed_world.py`, `reconciliation_kernel.py`,
`wp_attribution.py`; expect a rebase. A2 (#7598) owns recovery/teardown/resume/refusal text.
