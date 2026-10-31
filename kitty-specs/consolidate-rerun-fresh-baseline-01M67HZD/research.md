# Discovery — #6770: a clean rollback leaves a stale consolidation baseline

Mission: `consolidate-rerun-fresh-baseline-01M67HZD`
Grounding commit: `origin/main` `512567eee7` (2026-10-30).
Issue: spec-kitty/spec-kitty#6770 (recurrence of closed #5667; related open #5372, #5687, #5686, #5666).

## Evidence — the defect, on this build

Reproduced in-process against a real LANES mission on current `main`
(`build_lanes_mission`, target `develop`, WP01+WP02 approved) with a *one-shot*
reconciliation FAIL:

1. Attempt 1 lands both lanes, the gate FAILs, the single rollback door restores
   `develop` and the mission branch. The target is back at `T0`, the root checkout
   is clean — and `.kittify/runtime/merge/<mission_id>/state.json` **still exists**,
   carrying `pre_mutation_target_sha = T0`.
2. An operator commit `T0..T1` lands on `develop` (`TEAM.md`).
3. Attempt 2 runs with no injected failure. It FAILs anyway:

   ```text
   Error: Reconciliation FAILED: file 'TEAM.md' (blob 392650a372) IS reachable on
   the target but belongs to NO approved WP — un-attributable ...
   Rollback, restored to the record's restore targets:
     restored   develop     80268ef -> 2f1b076
   ```

   Attempt 2's window base was `T0`, so the operator's own commit was read as
   mission content, and attempt 2's rollback then reset `develop` to `T0` — the
   #5667 data-loss shape.
4. After such a clean rollback, a plain `consolidate --abort` refuses: the clean
   rollback already cleared `post_mutation_refs` (`rollback._clear_bookkeeping`),
   so any target commit made afterwards is "moved since the snapshot but no
   post-mutation tip was recorded (interrupted phase?)".

## Root cause chain (code, at `512567eee7`)

- `consolidation/phase_claim.py::_resolve_pre_mutation_target_sha` is
  read-persisted-first: `state.pre_mutation_target_sha` wins whenever set. Correct
  for a genuine `--resume` (#5001 FOLD-4), because a resume runs *after* attempt 1
  advanced the target, so the live tip is poisoned.
- `consolidation/resolve.py::_load_or_create_merge_state` returns
  `(state, is_resume=True)` whenever a record exists. The executor therefore cannot
  tell "an interrupted run" from "a run that rolled itself back": both are records.
- `consolidation/rollback.py::rollback_to_snapshot` + `_clear_bookkeeping` clear
  the per-attempt progress (`completed_wps`, `post_mutation_refs`,
  `unsettled_refs`, anchors) after a **full** restore, but never the record itself.
  `executor._report_rollback` (the single door, #5385) prints the report and stops.
- `cli/commands/consolidate.py::_dispatch_abort` →
  `rollback.rollback_to_snapshot` → `_rollback_branch`: a tip that is neither the
  restore target nor a recorded/effective post is `NOT_RESTORED` with
  `_UNRECORDED_MOVE_REASON`; the abort then keeps the record and exits 1.

So the persisted base is only *honest* while attempt 1's landing is still on the
target. After a full restore it is stale, and the record is a liability with no
resume value (its progress bookkeeping is already empty).

## Decisions

- **D1 — tie record survival to residue.** A rollback door whose report says the
  attempt was undone (`RollbackReport.fully_restored`) clears the transaction record
  through `state.clear_state` (the single owner of clearing `state.json` + its
  post-fix marker). A partial rollback (any `NOT_RESTORED`, a kept verified landing,
  a missing run-movable branch) keeps the record exactly as today. This makes the
  invariant checkable in one sentence and keeps one owner for the clear.
  *Rejected alternative*: refuse a non-`--resume` run while a record exists and name
  `--abort` (the issue's second suggestion). It contradicts #5111's deliberate
  auto-resume of an interrupted record and #5372's direction ("treat a provably
  zero-progress record as fresh, or refuse"), and it makes every clean failure a
  two-command recovery.
  *Rejected alternative*: re-anchor only `pre_mutation_target_sha` and keep the
  snapshot. The snapshot would still make a later rollback restore to a tip two
  attempts old, and `--abort` would still find recorded geometry for branches that are
  already back where they started.
- **D1b — refined after the aggregate review: drop the geometry, keep the record.**
  Deleting the whole record after a full restore broke three things the first cut did
  not see: (i) 11 existing tests assert a rolled-back run keeps a resumable record and
  drive the follow-up through `--resume`; (ii) `recover-from-interrupted-merge.md`
  promises that an interruption leaves a record to resume; and (iii) — decisive —
  `test_repro_5051_clean_3way` proves the #5051 recovery depends on the persisted
  coordination anchor: with the record gone, a re-run rebuilt the claim from the folded
  live tree and refused with "no approved lane resolved any commits and the authored-blob
  set is empty". The shipped rule is therefore field-scoped: the attempt's transaction
  geometry (target baseline, snapshot, restore targets, post tips, progress) is dropped
  on a full restore, while the record, the marker and the claim's coordination/lane
  authorship anchors stay. Verified: the 11 tests pass untouched, #5051 still passes,
  and the stale-baseline hazard is closed for plain and `--resume` runs alike.
- **D2 — the "fresh baseline" comes from `_load_or_create_merge_state`, not from a
  new resume flag.** With no record, attempt 2 is a genuinely fresh run: it
  snapshots live tips, writes a new marker+state, and `_resolve_pre_mutation_target_sha`
  does its live `rev-parse`. No new field, no migration (NFR-001), and no change to
  the read-persisted-first rule that a real resume still needs.
- **D3 — the abort path is left alone.** After the clear there is no record, so a
  plain `consolidate --abort` takes the existing "No active merge state" branch
  (exit 0). The `--release-branch` flow for a genuinely unexplained move (#5687) is
  untouched and stays necessary for the partial-rollback shape (C-003).
- **D4 — the clear is guarded.** It mirrors `_clear_fresh_record_on_pre_mutation_exit`:
  a failure to clear is reported as a warning and never replaces the original
  `typer.Exit`/exception the door re-raises.

## Open questions (for specify/plan)

- Does any caller *besides* the door rely on the record outliving a full restore?
  Survey says no: `--resume` after a full restore re-does everything anyway
  (`completed_wps == []`), and the record's only unique value (the pre-mutation
  anchors) is exactly what goes stale.
- Test re-pins: `tests/terminus/test_rollback_door.py::test_record_is_truthful_after_rollback_and_a_rerun_succeeds`
  and `tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py`
  assert a fully rolled-back run "keeps its record for a resume". They pin the
  behaviour this Mission changes; they must be re-pinned to "clears its record; the
  re-run starts fresh and still reaches done", keeping their other assertions.
