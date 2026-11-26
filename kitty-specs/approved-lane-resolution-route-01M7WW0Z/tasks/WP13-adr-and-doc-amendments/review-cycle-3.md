---
affected_files: []
cycle_number: 3
mission_slug: approved-lane-resolution-route-01M7WW0Z
reproduction_command:
reviewed_at: '2026-11-26T07:26:38Z'
reviewer_agent: claude::implementer-runner
wp_id: WP13
---

# Pre-accept squad fold (Mission approved-lane-resolution-route-01M7WW0Z, #5604)

The squad reviewed lane-m b4db082483, which contains every lane. Verdicts:
- integrity: ACCEPT
- architecture: ACCEPT-AFTER-FIXES
- fidelity: ACCEPT-AFTER-FIXES

None of the findings lands unreviewed content. All of them are folded in this round, on lane-m (WP13 is reopened). Edits to files owned by other WPs are recorded leeway, with a one-line rationale each in WP13 history.

Full reports:
- squad3/integrity.md
- squad3/architecture.md
- squad3/fidelity.md

Each item is required. For behaviour changes, run red-first.

## MED
- **A1 — one canceled-window rule.** `lanes/incorporate.py:283 _canceled_window_merges` is a second copy of the rule, and it differs from `consolidation/reconciliation_bound.py:363`: it reads first-parent only and raises on a missing stamp, while reconciliation_bound reads any parent and treats a missing stamp or open window as holding every merge. Extract ONE public helper into `consolidation/wp_attribution.py`, with the reconciliation_bound semantics (any parent; missing stamp / open window → all merges inside). Use it from both callers.
  - Red test: a hand merge hidden behind a clean merge inside a canceled WP's window must refuse at `--incorporate`. Today it passes there and only `consolidate` refuses.
- **A2 — auto-rebase merge without pinned config.** In `lanes/auto_rebase.py:1263` the auto-rebase `git merge` runs without `merge_probe_env`. Run it under `merge_probe_env(...)`, the same way incorporate does, so the clone-level config pins (renormalize, directoryRenames, renames, ...) apply to the tool merge as well. Keep `_recorded_merge_attributes_hold` as is.
  - Red test: a clone-level config, e.g. `merge.renormalize=true` or a `merge.directoryRenames` setting via `GIT_CONFIG_COUNT`, must not change the tool merge's result, or the auto-rebase must refuse. Choose the behaviour that matches how `--incorporate` handles the same config, and say which you chose.
- **F1 — FR-003 narrower than the spec** (`lanes/consolidation.py:246`).
  - (a) Add a test that compares the conflicted-path list exactly, with a control: an overlapping path that does NOT conflict must not be listed.
  - (b) When the lane checkout is missing, the refusal must state the halt reason ("no lane checkout, so no in-run auto-rebase ran") instead of saying nothing. Update `test_7755_stale_sibling_lane_recovery.py::test_refusal_without_a_lane_worktree_still_names_the_sibling` to match (recorded leeway).
- **F2 — the FR-004 printed route is never followed to a landing.** Add one real-git end-to-end test that follows the `RESOLUTION_MERGE_UNREVIEWED` recovery exactly as printed: `move-task <WP> --to in_progress ...`, then resolve or rework, then for_review, then independent approval, then consolidate. The Mission must land. Use the frozen route-support module; do not edit it. If the printed route cannot land, stop and report.

## LOW
- **A3** `incorporate.py:358` imports the private `reconciliation_kernel._is_bookkeeping`. Expose a public predicate and use it.
- **A4** `incorporate.py:484` imports the private `_make_merge_env`. Make it public in its own module and update the callers.
- **A5** `incorporate.py:175 _APPROVED_LANES` re-derives approved membership. Reuse the one membership predicate (`reconciliation_authorship._approved_wp_ids`, made public, or the existing public equivalent).
- **A6** `reconciliation_authorship.py:319` has a docstring that claims "the single definition". Document the two tiers instead: the claim adds the canceled-window term.
- **A7** `reconciliation_authorship.py:391` probes the advisory `_unreviewed_merge` without `attributes_source` on a memo miss. Pass the claim's source.
- **A8** `auto_rebase_record.py:23` has a stale comment, and `delete` is not in `__all__`. Add `delete` to `__all__` and fix the comment.
- **A9** `tasks_verdict_persistence.py:370` has a docstring that still lists `skip_target_branch_commit` as a cause of non-durability. Remove that clause.
- **I1** In the forged-record paragraph of the ADR 2026-10-04-5 amendment, state that the auto-rebase record is clone-local state and not proof. Only the gate judges the content. A forged record loses the early refusal and the "nothing moved" guarantee (SC-003), never integrity.
- **I2** `incorporate.py:17-19, 532`: a refused `--incorporate` has already claimed the WP and run the sync-point merge, yet the refusal says "nothing was merged". Fix it in one of two ways:
  - (a) run the incorporate preflight and the attribute guard before the claim and sync side effects. Preferred if it is contained.
  - (b) make the message state exactly what already happened.

  Add a test either way.
- **F3** `tests/consolidation/test_resolution_merge_unreviewed.py:568`: the agreement test's claim-is-a-subset-of-gate half is tautological. Build the gate side from `_drop_unreviewed_merges` alone.
- **F4** `rollback.py:1064`: `lane_rebase_moves` holds a single move per lane. Pin this with a comment and a unit test showing that a second move of the same lane in one attempt is reported, not restored (fail closed). Record it in the WP13 ADR text as a residual.

## Process
- Re-enter WP13 with `spec-kitty agent action implement WP13 --agent claude --mission approved-lane-resolution-route-01M7WW0Z`. Keep the sync merge.
- New signed commits only. Do not push.
- No `noqa` or `type: ignore`. C901 ≤ 15.
- Run with `-n 3` at most:
  - every touched test file;
  - `tests/lanes`;
  - `tests/consolidation`;
  - the terminus route modules (WP12 and WP14);
  - the arch gates `layer_rules`, `no_dead_symbols` (`-n0`), `merge_pipeline_ratchets*`, `destructive_op_routing*`, `commit_scope_owner`, `single_rollback_authority`, `no_legacy_terminology`;
  - `make test-fast` markers.
- ruff, format and mypy must be clean on every touched file.
- When done, mark the subtasks done, then `move-task WP13 --to for_review` without `--note`.
- Report: head SHA, each item → commit and test, red-first evidence, counts.
