# Contract — the consolidation record's lifecycle across attempts

Mission: `consolidate-rerun-fresh-baseline-01M67HZD` (#6770). Amends guarantee 5 of
`kitty-specs/consolidation-claim-rollback-integrity-01M3PD1T/contracts/rollback-authority.md`
(“Clears bookkeeping only after a full restore”) by scoping *which* persisted state a full
restore ends, and which it keeps.

## The rule

**A record's transaction geometry — its target baseline, its snapshot, its restore targets and
its per-attempt progress — survives only while some of its attempt is still on the target.**

`.kittify/runtime/merge/<mission_id>/state.json` plus its reconciliation marker are written by
`resolve._load_or_create_merge_state` at transaction start and read back by three surfaces:

| Reader | What it derives from the record |
|---|---|
| `phase_claim._resolve_pre_mutation_target_sha` | the reconciliation **window base** (`excluded_window_base`) |
| `rollback.rollback_to_snapshot` (the door, and `--abort`) | the snapshot, the per-attempt restore targets, the recorded post tips |
| `resolve._load_or_create_merge_state` | **`is_resume`** — an existing record makes the next plain run a resume |

Once a rollback has undone the attempt, the persisted `pre_mutation_target_sha` describes a
transaction that ended, `post_mutation_refs` is empty (a full restore clears it) and
`completed_wps` is empty. Carrying that geometry into the next attempt is what #6770 reports:
the resume inherits a base that predates anything landed on the target since, so those commits
are judged mission content (“un-attributable”), and the same emptiness is what makes a plain
`--abort` refuse a target that moved after the restore (`NOT restored … no post-mutation tip was
recorded`).

## Where it is enforced

`executor._report_rollback` (the single post-mutation rollback door, #5385) is the only site:
after it prints the rollback report it calls `executor._rebaseline_record_after_full_restore`,
which asks `rollback.rebaseline_after_full_restore` for the field change and saves — **iff**
`RollbackReport.fully_restored` holds. That report property is the one owner of “the attempt was
undone” (nothing refused, no branch `NOT_RESTORED`, every branch restored or legitimately
untouched); the door does not re-derive the verdict from git state.

## What a full restore drops, and what it keeps

Dropped (`rollback.rebaseline_after_full_restore`):

- `pre_mutation_target_sha` — the window base and the rollback CAS anchor of the attempt that
  just ended. The next attempt captures the live target tip.
- `pre_mutation_refs`, `restore_targets`, `post_mutation_refs`, `snapshot_lane_branches`,
  `unsettled_refs`, `resume_seeded_refs`, `advance_intents`, `released_refs`,
  `release_reasons` — the snapshot and the per-attempt state of branches that are already back
  where they started. A later rollback must never restore to a tip two attempts old, and
  `--abort` must not believe it still has a snapshot to restore.
- `reconciliation_passed_target_sha` — already cleared by `_clear_bookkeeping` on a full restore.

Kept:

- `pre_mutation_coord_sha`, `pre_mutation_coord_ref`, `pre_interrupt_lane_tips` — the
  reconciliation **claim's authorship base** (#5001 FOLD-4, #4982, #5051). A full restore puts the
  coordination branch back at exactly the captured tip, so the anchors are still accurate, and a
  resume that lost them would rebuild the claim from a live (possibly folded) tree and refuse a
  legitimate merge with an empty authorship set. `test_repro_5051_clean_3way` is the standing
  proof: with the anchors dropped, the re-run false-FAILs with “no approved lane resolved any
  commits”.
- The record itself, its marker, `strategy`, the cleanup flags and `wp_order`: a resume
  re-derives its anchors instead of refusing to exist, `--resume` keeps working, and the Mission
  keeps its provenance trail.

## Behaviour by rollback outcome

| Rollback outcome | Attempt geometry | Record | Why |
|---|---|---|---|
| Every branch restored / already at its restore target / untouched lane (nothing of the attempt landed, or what landed was undone) | **re-baselined** | kept | the next attempt must re-derive from the live tips; the claim's coordination anchors are still accurate and still needed |
| Any `NOT_RESTORED` branch (a foreign commit, a dirty checkout, a missing run-movable branch) | **kept** | kept | that content is still on the target, so the persisted baseline is still the honest one, and `--resume`/`--abort` need the snapshot |
| `refused_verified_landing` (a landing an **earlier** reconciliation verified) | **kept** | kept | nothing was rolled back |
| The rollback itself raised / was interrupted | **kept** | kept | the door reports and re-raises; it never guesses |
| A save of the re-baselined record fails | **kept on disk** | kept | the door warns and names `--abort`; the original failure stays the headline, and the warning never claims the record was settled |

A branch kept by an operator release (`KEPT_BY_OPERATOR`) counts as settled for
`fully_restored`, so it re-baselines too: the operator deliberately released that content, so it
is no longer “of this attempt”. Releases are recorded only by `--abort`, which clears the record
itself, so this state is not reachable through the door today; if it ever is, the outcome is the
same and the released content stays where the operator put it.

## Consequences the tests pin

1. After a clean rollback, the next run — plain or `--resume` — re-derives its reconciliation
   window base from the target's current tip, so commits landed between attempts are not judged
   as mission content and are never rolled back over.
   (`tests/terminus/test_rollback_record_rebaseline.py::test_a_clean_fail_rollback_rebaselines_the_record_and_the_rerun_uses_the_current_target_tip`)
2. After a clean rollback, a plain `spec-kitty consolidate --abort` no longer refuses: it reports
   a clean finish, clears the record and exits 0.
   (`…::test_a_plain_abort_after_a_clean_fail_rollback_is_a_no_op_not_a_refusal`)
3. A partial rollback keeps the attempt's baseline and snapshot, untouched.
   (`…::test_a_partial_rollback_keeps_the_record_with_its_pre_mutation_base`,
   `tests/terminus/test_rollback_door.py::test_dirty_target_checkout_is_reported_not_restored_and_the_record_is_kept`)
4. A failed save warns, names `--abort`, and leaves the stale geometry on disk rather than
   claiming success; the original failure is re-raised unchanged.
   (`tests/consolidation/test_executor_rollback_wiring.py::test_the_door_warns_and_keeps_the_original_error_when_the_record_cannot_be_rebaselined`)
5. The claim's coordination anchors survive, so the #5051 recovery still passes.
   (`tests/terminus/test_repro_5051_clean_3way.py`)

## Non-goals

- The zero-progress record a hard kill leaves (#5372) keeps its current contract.
- The `--release-branch` flow for a genuinely unexplained move (#5687) is unchanged.
- No new persisted field, no migration: the cleared fields already default to their empty
  values, a record written by an older release loads and behaves exactly as before, and one
  written by this release is the same shape.
