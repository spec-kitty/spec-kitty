---
affected_files: []
cycle_number: 1
mission_slug: coordless-commit-checkout-01M7DW13
reproduction_command:
reviewed_at: '2026-11-14T21:37:23Z'
reviewer_agent: claude-reviewer
wp_id: WP01
---

# WP01 review feedback (cycle 1), reviewer: claude-reviewer

Verdict: **changes requested**. One blocking regression; the rest of the work package is sound.

## What was verified

- Red then green. On base `d7cedd7e`, the #7648 test `test_commit_idempotent_unchanged_tree_is_a_noop_when_the_pending_check_cannot_read` is red with `BookkeepingCommitFailed ... nothing to commit`, and the strict control passes. On the same base, the 4 diverging rows of `tests/coordination/test_coordless_status_commit_checkout.py` are red: lane-worktree-holds-topic, both (a) rows and (b). That run used a scratch worktree with the constant defined locally. The 7 agreeing rows are green on base. All are green at HEAD.
- `tests/coordination/test_coordless_status_commit_checkout.py` + `tests/specify_cli/coordination/`: 592 passed, 10 skipped.
- Gates `test_no_write_side_rederivation.py`, `test_no_dead_symbols.py`, `test_layer_rules.py`, `test_status_read_single_door.py`: 226 passed.
- ruff check and `ruff format --check --force-exclude` are clean on every changed file. mypy reports one error, `transaction.py:525` `no-any-return`. It comes from `_preflight_policy_verdict`'s `return WorkflowMutationPolicy.assert_allowed(...)`, a line this WP did not change, so it is not counted against this WP.
- No raw holder probe remains in `coordination/transaction.py`. The genuinely-legacy arm is untouched. The hold check runs after the policy gate and before any write, both in `acquire` and in `preflight_refusal`.

## BLOCKING: `consolidate --target` override and its hatch control now refuse with the new code

`tests/terminus/test_protected_target_preflight.py` has 3 tests that pass before this WP and fail now. They run the real CLI:

- `test_target_override_onto_protected_main_is_refused_before_any_mutation`
- `test_control_target_override_hatch_stands_the_guard_down`
- `test_dry_run_reports_the_target_override_refusal`

Fixture (`_build_override_fixture`): a LANES Mission recorded for `develop`, with the repository root checkout standing on `main`, then `consolidate --target main`.

How it fails:
1. `consolidation/entry_preflight._refuse_protected_status_target_or_continue` calls `preflight.refuse_protected_status_target`.
2. That calls `status_transition.status_write_refusal`, which calls `BookkeepingTransaction.preflight_refusal`.
3. The modern coordination-less arm passes the policy gate, because `develop` is unprotected. The new hold check then returns `STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH`, because the root is on `main`, not `develop`.
4. Any non-`None` verdict refuses the consolidation. So:
   - the #6464 target-override guard (`_refuse_protected_target_override_or_continue`, which runs only when the first probe returns `None`) is pre-empted, and its `PROTECTED_BRANCH_REFUSED` code, remedy and hatch text are lost;
   - with `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1`, a consolidation that used to land (`→ main`) is now refused;
   - `--dry-run --json` reports `STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH` instead of `PROTECTED_BRANCH_REFUSED`.

Observed output: `Error: STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH: Refusing to record 'status transition WP01': the status write checkout .../repo is on branch 'main', not on the write branch 'develop', and no checkout outside the lane worktrees holds 'develop'. ... Consolidation refused before any branch moved.`

The probe exists to catch a protected-policy refusal at consolidate entry (#5385). Because `preflight_refusal` now mirrors `acquire`, it also answers a checkout-placement question. That question applies to the done write as it would run now, before the landing and before any checkout switch, not to the done write the consolidation actually performs. This is consumer behaviour that neither the spec nor the operator rulings cover.

To resolve, pick one and pin it with tests:
- (a) Keep `refuse_protected_status_target` and the forecast on the policy question only. For example, give `preflight_refusal` a way to skip the hold check, or filter the new code in the consolidation probe. Then confirm what the post-landing done write does in this fixture: with the hatch, does it now refuse at `acquire` after `main` has moved? Show that it does not, or that the rollback door handles it.
- (b) Get an operator ruling that consolidate entry should refuse here. Then update the 3 terminus tests honestly: the new expected code, and a #6464 path that still reaches its own refusal when the root is on the recorded target.

Also add `tests/terminus/` (at least `test_protected_target_preflight.py`) and the `tests/consolidation/` preflight tests to the blast radius run recorded for this WP. `preflight_refusal`'s consumers live there.

## Non-blocking notes

- These files were edited outside `owned_files`: `tests/integration/test_legacy_mission_fallback.py`, `tests/specify_cli/coordination/test_transaction_legacy_topology_routing.py`, `test_transaction_preflight_refusal.py`, `test_commit_router_settled_holder.py`, `test_transaction_primary_partition_holder_7372.py`. Each fixture edit (`git branch X` changed to `git checkout -b X`) is honest: no asserted expectation changed, and the fixture now has the root hold the write ref, as the ruling requires. Record them in the WP or PR anyway.
- `test_transaction_primary_partition_holder_7372.py::test_mission_that_is_not_default_keeps_the_root_even_when_another_checkout_holds_the_ref` uses an explicit `single_branch` Mission (coordination-less) to exercise `_primary_partition_holder`, which is only reached from the coordination arm (`commit_to_primary_target`). An explicit `lanes_with_coord` Mission would test the M2 scenario more faithfully.
- `placement_seam(...).write_target` can raise (`ActionContextError`, e.g. `SINGLE_BRANCH_CODE_LANES_UNMIGRATED`) on the coordination-less arm and in `preflight_refusal`, where the old holder probe could not. This fails closed, and the consolidate entry catches `ActionContextError`. Mention it in the PR.
