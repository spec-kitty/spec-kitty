# Tracer 02 — Seam map (file:line, current main)

## Defect A — resume aborts instead of recovering a pure behind-own-HEAD lag
- `merge/executor.py:3166` `_run_lane_based_merge` — OUTER fn (fresh + resume).
- `merge/executor.py:3362-3372` `_pre_mutation_safety_preflight(...)` → at `:2850`
  `assert_checkout_on_target`, `:2851-2853` `assert_worktree_clean(main_repo,
  error_code=MERGE_UNSAFE_PRIMARY_DIRTY)`. Runs BEFORE the global lock (`:3383`).
- `merge/executor.py:3373-3375` `except DestructiveOpRefused` → `_report_pre_mutation_refusal`
  (`:3128-3163`) then `raise typer.Exit(1)`. **← Defect-A fix locus.**
- `_report_pre_mutation_refusal` calls `classify_resume_dirty_remedy(main_repo,
  lane_branch=mission_branch)` (`:3151`) — ADVISORY only.
- Classifier: `merge/preflight.py:705 classify_resume_dirty_remedy`;
  `:691 _is_behind_own_head` → `git_probes.py:31 _lane_already_integrated` (ancestry).
- Guard primitive: `git/destructive_guard.py:155 assert_worktree_clean` (single authority;
  delegates to `ref_advance._dirty_entries`). `MERGE_UNSAFE_PRIMARY_DIRTY` const at
  `destructive_guard.py:41`, consumed only at `executor.py:2852` (raise) + `:3145` (dispatch).
- Lagged base: `MergeState.pre_mutation_target_sha` (`merge/state.py:134`), resolved
  read-persisted-first by `merge/executor.py:1823 _resolve_pre_mutation_target_sha`.

## Defect B — merge-strategy "Already up to date" no-op not adjudicated
- `lanes/merge.py:1174-1218` `_merge_branch_into` MERGE branch: `git merge <source> --no-edit`;
  on "Already up to date" HEAD is unchanged but the fn ALWAYS `return True` (`:1218`).
- `lanes/merge.py:405` `already_applied = not changed` → for the merge no-op = `not True` = **False**.
- FR-037 guard `merge/executor.py:1331-1337` in `_handle_mission_merge_result`: fires
  `_reject_zero_diff_noop_squash` (`:1282`) when `mission_already_applied AND ... AND
  (any_lane_had_unintegrated_code OR not mission_integrated_into_target)`. The FIRST
  conjunct `mission_already_applied` is False for the merge no-op → guard never fires.
- `mission_integrated_into_target = _branch_trees_equal(mission, target)` (`git_probes.py:55`),
  computed `executor.py:1387-1391` — strategy-agnostic tree check.
- **Fix:** `_merge_branch_into` MERGE branch must detect the no-op (compare pre/post target
  tip) and `return False` (mirroring squash's zero-staged handling + `allow_noop_squash`),
  so `already_applied=True` propagates and the (strategy-agnostic) zero-diff guard refuses
  when `not mission_integrated_into_target`. Rename `_reject_zero_diff_noop_squash` →
  strategy-neutral for honesty.

## Fail-closed backstop
- `merge/executor.py:_phase_reconcile_before_teardown` (~`:2102-2140` / runs at `:3061`,
  strictly before teardown `:3064`). On FAIL → CAS target rollback + `Exit(1)`, no teardown.
- `_reconciliation_claim_for_gate` (`:2097-2099`): squash gets `verify_reachability=False`
  + #5013 blob-attribution content axis; merge/rebase get `verify_reachability=True`
  (pure ancestry). → catches a *dropped* lane on merge, BLIND to a *content-reverted*
  merged lane. Residual C-002.

## No parallel dirty-guard authority (whack-a-field: LOW)
- `assert_worktree_clean` is the single primitive. Adjacent-but-distinct:
  `_refresh_primary_checkout_after_merge` (`executor.py:1416`) is a POST-merge refresh,
  not a pre-mutation gate — no collision with the Defect-A fix.
