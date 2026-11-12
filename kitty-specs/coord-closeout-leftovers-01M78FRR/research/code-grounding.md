---
type: explanation
updated: 2026-11-12
audience: implementer and reviewer of this Mission (software-engineer persona)
---

# Code grounding: coordination closeout leftovers (#7598)

Read-only grounding by a three-agent research squad plus one fresh-context challenger, on
`origin/main` 89217ac8. Every claim cites the code; anything not reproduced is labelled.
The checkout is shallow (50 commits), so 90-day churn could not be measured (every file shows
the graft commit only).

## 1. #7491: `--resume` refuses `COORD_LATE_PROJECTION_REFUSED` after `COORD_TEARDOWN_KEPT_ONLY_COPY`

**Reproduced** through the real CLI (`research/repro_7491.py.txt`, built on the
`tests/consolidation/test_late_teardown_projection.py` helpers):

1. A lane's approved commit also edits `kitty-specs/<slug>/spec.md` (line 0).
2. The target carries the same line-0 edit plus a later, different edit (line 10): the
   "re-finalize on the target" precondition from the report.
3. The first run lands, then exits 76 (`COORD_TEARDOWN_KEPT_ONLY_COPY`: the review cycle is
   untracked in the coordination worktree).
4. The operator follows the remedy (commits the review cycle on the coordination branch) and
   runs `--resume`.
5. The resume exits 1: `1 record(s) the coordination branch changed after the merge captured
   the coordination tip are not landed on the target ... kitty-specs/<slug>/spec.md`. The late
   commit never touched `spec.md`.

Control: amending the target alone, with no lane change to a planning file, resumes with exit 0.

**Where it comes from.**

| Fact | Citation |
|---|---|
| `COORD_TEARDOWN_KEPT_ONLY_COPY` (exit 76) and its remedy | `coordination/teardown.py:73-100` |
| `COORD_LATE_PROJECTION_REFUSED` constant | `consolidation/_constants.py:81-82` |
| Raised from the late window | `consolidation/phase_teardown.py:399, 598, 614, 744` |
| Message built | `consolidation/bookkeeping_projection.py:1464-1481` (`_raise_unlanded_late_window`) |
| Window base per run kind | `consolidation/phase_teardown.py:425-454` (`_late_window_base`) |
| First-run anchor captured, in memory only | `consolidation/phase_bookkeeping.py:384`; advanced by `_advance_approved_tip`, `phase_teardown.py:412-422` |
| Resume anchor, persisted once before lanes merge | `consolidation/phase_claim.py:326` (`state.pre_mutation_coord_sha`) |
| The proof judges every changed path, primary included (#7198) | `bookkeeping_projection.py:1338-1441`, two-point `git diff base T -- kitty-specs/<slug>/` (`kernel/git/listing.py:390`) |
| The in-merge projection never carries primary kinds | `bookkeeping_projection.py:668-720` (`_post_checkpoint_mission_paths`) |

**Root cause (high confidence, reproduced).** On a resume the window starts at
`pre_mutation_coord_sha`, so it re-walks the whole merge. Any primary artifact a lane brought
to the coordination branch and the target later changed differently enters the window, and
nothing can land it (primary kinds are never projected). The first run never sees these paths:
its window starts at `coord_tip_after_projection`, which is not persisted
(`run_state.py:311-325`; no field in `state.py`). `_late_window_base`'s own docstring predicts
the failure: "reusing the resume base instead would re-walk the whole merge and re-project
primary artifacts the target authored for itself." The late commit itself is irrelevant.

**Candidate fixes (operator ruling needed; changes ADR-governed late-projection behaviour,
#5570/#6791/#6871/#7199).**

- **(A) Persist the post-projection anchor.** Add `coord_tip_after_projection` to
  `ConsolidationState`; save it where it is captured and advanced; on resume use it when it is
  set, is an ancestor of the live coordination tip, and the record carries a verified landing
  (`reconciliation_passed_for_tip`); otherwise fall back to `pre_mutation_coord_sha`. Clear it
  where the coordination anchors are dropped (`rollback.rebaseline_after_full_restore`,
  `begin_attempt`). A late commit after the anchor stays in the window and is still refused if
  unlanded (primary edits and deletions included). `rollback.py` stays the only rollback
  authority; only a base is selected.
- **(B) Keep the wide resume window but exclude primary paths whose last change in the window
  came from the merge's own lane merges.** Narrower in principle, but it re-derives commit
  authorship inside the proof; more code and a new attribution rule.

Recommendation: (A).

**Red test seam.** `tests/consolidation/test_late_teardown_projection.py` (e2e, ~34 s per
case), a builder variant whose lane plants a planning edit, plus a cheap unit test of
`_late_window_base`. Negative control: a late post-anchor commit that edits `spec.md` and is
not on the target must still refuse.

## 2. #5867: squash refuses "projected coordination bookkeeping content did not land"

- **Raised at** `consolidation/phase_gate.py:355-361` (`_assert_squash_projected_content_landed`,
  `:298`). Rendered: `SQUASH reconciliation refused: projected coordination bookkeeping content
  did not land on the target. Nothing was torn down; re-run spec-kitty consolidate --resume.`
  No `Error code:` line; exit 1 with no rollback, on purpose (`:347-354`).
- **The data exists and is thrown away.** `projected_paths` is computed
  (`_squash_projected_paths_or_refuse`, `:277-295`). `projected_content_matches_target`
  (`bookkeeping_projection.py:1539-1574`) collapses per-path results with `all(...)`. The
  per-path body `_projected_path_content_matches` (`:1490-1537`) has three distinct failures:
  1. the coordination blob is missing (deleted or renamed on the coordination branch);
  2. the target did not change the path since the checkpoint, yet its bytes differ from the
     coordination copy;
  3. both sides changed it and the landed blob is not what the registered merge driver yields.
- **The remedy is wrong.** `--resume` repeats the same proof; it cannot help without an
  operator change.
- **Classification on main** (checked with `kind_for_mission_file`): coordination kinds are
  `traces/*`, `tasks/WPnn*/review-cycle-N.md`, `issue-matrix.json`, `acceptance-matrix.json`,
  `status.events.jsonl`, `status.json`. `research.md`, `data-model.md`, `quickstart.md`
  (CHECKLIST kind), `analysis-report.md`, `contracts/*` are primary and never projected. No
  planning file is misclassified. `notes/*` is unclassified and not projected.
- **Fix shape.** Return `(path, reason)` per failing path from a sibling of
  `projected_content_matches_target` (keep the bool wrapper for its test callers in
  `tests/terminus/test_repro_5038.py` and `test_bookkeeping_projection_seam.py`), render up to
  20 paths with a reason each, and give a remedy per reason. A named code is an operator ruling.

## 3. #7599: accept's "Next steps" says "No merge needed" for a coordination Mission

- Text built by `_build_acceptance_instructions`, `acceptance/__init__.py:2030-2109`; printed
  by `cli/commands/accept.py:741-744`; caller `perform_acceptance` (`:2217-2233`).
- The `pr` arm already guards coordination Missions with `lands_by_consolidation` (#6450,
  `:2053-2060`). The `local` integration-branch arm (`:2071-2073`) never reads it and prints
  "Acceptance recorded directly on `{branch}`. No merge needed."
- `branch` is the checkout's branch, not where the record was committed (PR #7567 commits the
  record on the Mission branch through `commit_for_mission`).
- Related: a flat `lanes` Mission with merge-pending code lanes also gets "No merge needed".
- No test asserts the string. `tests/specify_cli/test_acceptance_regressions.py:1150-1183`
  pins the `pr` coordination arm; a local twin belongs beside it.

## 4. #7600: `--abort` refusals that tell the operator to `--resume`

Abort flow: `_dispatch_abort` (`cli/commands/consolidate.py:707`) → `_abort_lock_restore_clear`
(`:669-704`) → `rollback_to_snapshot` → `_abort_exit_keeping_record` (`:614-618`) with
`_ABORT_KEPT_RECORD_MESSAGE` (`:447-449`).

| Case | Source of the wrong advice | Remedy that completes the abort |
|---|---|---|
| Branch moved by another actor / unrecorded move (NOT_RESTORED) | `rollback.py:789-791`; no `--release-branch` hint | `--abort --release-branch <b> --release-reason "..."` |
| Checkout dirty (NOT_RESTORED) | `RefAdvanceDirtyWorktreeError` text, `git/ref_advance.py:318-320`: "then resume the consolidation (`spec-kitty consolidate --resume`)" | commit or stash the named edit, re-run `--abort` |
| Coordination checkout not resynced | `_COORD_RESYNC_REMEDY`, `rollback.py:135-139`: "re-run `--resume` or `--abort`" | commit or stash in the coordination worktree, re-run `--abort` |
| Verified landing kept (`refused_verified_landing`, `rollback.py:698-706`) | "resolve the branches named above" though none is named | `--resume` IS the way forward here (finish teardown); say so, labelled |

`RollbackReport.render()` (`rollback.py:244`) is shared by abort (`consolidate.py:588`) and the
gate/door rollback (`executor.py:809`); the `--resume` strings are baked into exception text
that does not know the invoking command. Pattern to copy: `teardown_coordination_topology(
follow_up_command=...)` / `CoordTeardownKeptOnlyCopy` (`coordination/teardown.py:75-100`).
Tests: `tests/terminus/test_rollback_door.py:340-343` pins the gate path's release-branch text;
no test pins the "resume the consolidation" wording.

## 5. #4041: an archived terminal Mission keeps its coordination worktree

- `archive create` (`cli/commands/archive.py:43-118`; core `missions/_archive.py:300-357`)
  writes one JSONL record and touches no git state; its module boundary says it "never mutates
  mission state" (`_archive.py:30-32`). "Terminal" is all WPs done (or done/canceled), not
  `merged_at`. `is_mission_archived` has no production caller.
- `doctor workspaces --fix` removes only unregistered husks; `--prune` treats a coordination
  worktree as `mission_owned` because the coordination branch parses with no lane id
  (`workspace/landed_worktrees.py:447-458`). `context cleanup` removes context files only.
  `doctor coordination --fix` removes nothing.
- **`mission close` already covers part of it** (`cli/commands/mission_type.py:386-714`):
  without `--discard` it requires `is_mission_merged` and calls `teardown_coordination_topology`
  (worktree only; branch and marker stay); `--discard` removes worktree, lanes and branches
  (tips kept under `refs/spec-kitty/discarded/`) and flattens the marker.
- The marker is `meta.json` `coordination_branch`; only `flatten_coordination_metadata`
  (`mission_metadata.py:1263`) may remove it (`tests/coordination/test_flatten_primitive_single_source.py`).
- Safe primitives: `teardown_coordination_topology` (ledger guard, dirty refusal → exit 76),
  `guarded_branch_delete` without `operator_intent` (refuses `BRANCH_HAS_UNIQUE_COMMITS`),
  `flatten_coordination_metadata`. A new `operator_intent=` caller would need a gate edit
  (`tests/architectural/test_destructive_op_routing.py` pins two callers).
- Surface options (operator ruling): (a) `archive create` releases automatically; (b)
  `doctor workspaces --reclaim-archived`; (c) `context cleanup` (wrong domain); (d) a new
  `archive reclaim <mission>`; (e) extend `mission close` (non-discard) to also delete a landed
  coordination branch and flatten the marker, and have `archive create` point at it.

## 6. Gates to run for this Mission

`tests/consolidation/test_single_rollback_authority.py`, `tests/architectural/test_destructive_op_routing.py`,
`test_layer_rules.py`, `test_no_write_side_rederivation.py`, `test_coord_read_residuals_closeout.py`,
`test_exemption_registry_ratchet.py`, `test_merge_reconciliation_class_guard.py`,
`test_git_path_listing_owner.py`, `test_no_worktree_name_guess.py`, `test_no_legacy_terminology.py`,
`test_doctor_cli_surface_golden.py` (if a doctor flag changes), `test_json_contract_enumeration.py`
(if `archive` arguments change), `tests/coordination/test_flatten_primitive_single_source.py`,
`tests/architectural/dead_symbol_allowlist.yaml` consumers (`test_no_dead_symbols.py`).

## 7. Second opinion (fresh-context challenger) — corrections that supersede the sections above

- **#7491, fix (A) refined.** The persisted post-projection tip is UNSOUND as a resume base
  unless the landing was verified: a resume that re-runs the phases checkpoints the LIVE
  coordination tip (`run_state.py:446`, `phase_claim.py:489`), so a tip from a rolled-back
  attempt would skip `pre_mutation..live`. Therefore:
  - write the tip in `_record_reconciliation_pass` (`phase_gate.py:138-153`), in the same
    `save_state` as `reconciliation_passed_target_sha`, not at bookkeeping capture;
  - use it only when `landing_verified_for_resume` (`run_state.py:540-560`) is true (exactly
    when the phases are skipped);
  - clear it wherever the PASS anchor is cleared (`rollback.py` `_clear_bookkeeping` ~830,
    `rebaseline_after_full_restore` ~904, the F4 restore, ~969) and restore it together with
    `anchor_before` (`executor.py:801-802`);
  - legacy records load `None` (`state.py:335` filters fields) and fall back to today's base.
  - Alternative (D): keep the wide base for coordination records, events and deletions, and use
    the narrow tip only for the primary-artifact disposition.
  - No existing test pins the resume base as `pre_mutation_coord_sha`; three docstrings must be
    updated.
- **#5867.** The refusal's `typer.Exit(1)` runs INSIDE the single rollback door
  (`executor.py:696-702`), so the target IS rolled back; the "does NOT roll the target back"
  comment at `phase_gate.py:347-355` is stale. Only a `GitProbeError` is transient; a
  deterministic cause repeats on `--resume`. `tests/consolidation/test_executor_coverage.py:585-597`
  patches `projected_content_matches_target` and must follow the gate's new call. A new code
  needs a `docs/api/cli-commands.md` row and a `tests/consolidation/test_constants_seam.py` pin;
  keep the phrase "projected coordination bookkeeping content did not land".
- **#7599.** Keying on `_lands_by_consolidation` misses a flat `lanes` Mission accepted on its
  target; key the text on "has lanes still to consolidate", with the coordination case naming
  where the record went.
- **#7600 is wider.** `RefAdvanceDirtyWorktreeError` is raised by `advance_branch_ref` /
  `restore_branch_ref`, imported by ~30 modules; its "resume the consolidation" text leaks into
  non-consolidate commands (live: `cli/commands/agent/workflow.py:2255-2256`, review fast-forward).
  Better fix: neutral exception text, each catcher appends its own next step. `ref_advance.py`
  is guard-internal to `test_destructive_op_routing.py` and beside safe-commit: merge-conflict
  risk with sub-epic C.
- **#4041.** Non-discard `mission close` removes only the worktree; `--discard` on a merged
  Mission is wrong provenance. **Blocker for any reclaim:** `guarded_branch_delete` without
  `operator_intent` refuses `BRANCH_HAS_UNIQUE_COMMITS` (`destructive_guard.py:612-616`), and
  after the default squash the coordination branch's bookkeeping commits are on no other ref.
  A tip-bound, absorption-proved delete (`LANDED_INTENT` with `expected_tip`, or a new intent)
  means editing the named-intent pin in `test_destructive_op_routing.py`. `doctor coordination
  --fix` already flattens a marker whose branch is gone. Challenger recommends extending
  non-discard `mission close` over a new `archive reclaim`.
