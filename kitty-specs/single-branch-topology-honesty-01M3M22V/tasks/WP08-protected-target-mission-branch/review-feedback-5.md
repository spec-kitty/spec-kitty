# WP08 review feedback, cycle 4, the commit_to_target fix (reviewer-renata)

**Verdict: changes requested.** The fix works end to end: create, finalize, implement and for_review on protected `main` with `--commit-to-target`. I also ran consolidate myself (see below). But two safety-relevant seams are untested, and one of them is the mission-scope guard itself.

## Blocking

**Issue 1: the mixed-path scope guard in `git/commit_helpers._single_mission_slug` is untested. This is the property that stops a code commit from riding the bypass.**

- **Mutation.** I replaced `return None` for a path outside `kitty-specs/<slug>/` with `continue`, so a commit mixing `src/…` with `kitty-specs/<ctt-mission>/…` would infer the mission and get the bypass onto protected `main`. `test_commit_to_target_overrides` plus `tests/git/test_protection_policy_mission_scope.py` stayed green: **13 passed**.
- **Required fix.** Add unit tests for `_single_mission_slug`, and for `preflight_commit` on a real repo with a `commit_to_target: true` mission targeting protected `main`:
  - only `kitty-specs/<ctt>/…` → bypass;
  - `kitty-specs/<ctt>/…` plus `src/x.py` → refused (`PROTECTED_BRANCH_REFUSED` / `safe_commit` protected refusal);
  - paths under two different missions → refused;
  - `kitty-specs/<other-mission-without-flag>/…` → refused.

  The mutation above must turn at least one of these red.

**Issue 2: the `coordination/commit_router._mission_scoped` fold is untested.**

- **Mutation.** I reverted `primary_protected=_mission_scoped(policy, repo_root, mission_slug).is_protected(...)` to `policy.is_protected(...)`. Result: **13 passed**.
- **Why it matters.** The one covered caller, `mission_finalize`, already passes `ProtectionPolicy.resolve_for_mission(...)`, so the router fold is redundant there. Every other `commit_for_mission` caller passes an unscoped policy and depends on this fold for a `commit_to_target` mission's planning commits: `mission_setup_plan`, `mission_record_analysis`, `spec_commit_cmd`, `acceptance`, `coordination/write_seam` and `orchestrator_api`.
- **Required fix.** Either add a test that drives one of those callers, for example `spec-kitty agent mission setup-plan` or `commit_for_mission` directly with an unscoped `ProtectionPolicy.resolve(...)`, for a `commit_to_target` mission on protected `main`, and shows the mutation goes red; or remove the fold and scope those callers explicitly. Untested code must not be left as is.

**Issue 3: the WP08 Activity Log was not updated.**
- Record, in the WP file's Activity Log:
  - the cycle-4 red command and the failing test names;
  - the mutation evidence;
  - the out-of-map files touched: `coordination/policy.py`, `types.py`, `transaction.py`, `commit_router.py`, `git/commit_helpers.py`, `implement.py`, `tasks_shared.py`, `tasks_move_task.py`, `tasks_map_requirements.py`, `mission_finalize.py`, `core/owned_mission.py`.
- Record them with a one-line rationale each, as the prompt requires for out-of-map edits.

## Non-blocking

- **Nit 4: consolidate is not pinned.** I ran the full US3 flow with consolidate: create `--commit-to-target` on protected `main` (operator hatch unset), finalize, implement, commit, approve, then `_run_lane_based_consolidation`. It **succeeds**: WP01 and WP02 are recorded `done`, the checkout stays on `main`, and there is no `PROTECTED_BRANCH_REFUSED`. The unprotected single_branch control succeeds too. Consider pinning this in `test_single_branch_consolidate_e2e.py`, but I do not require it.
- **Nit 5: red-first.** The unit reds at 68d22c51 are `AttributeError` (the seam did not exist). The integration red (`test_commit_to_target_overrides`: finalize `PROTECTED_BRANCH_REFUSED`) is a genuine assertion red for the behaviour. That is acceptable, consistent with earlier WPs.

## Verified

- **Mission scope in the policy.** `ProtectionPolicy.mission_bypass_branch` un-protects exactly the mission's own `target_branch`, only on the scoped copy. Tests show that other missions, non-mission commits and a different branch all stay protected.
- **Fail-closed on a non-bool.** A non-bool `commit_to_target` fails closed with a warning and no bypass. The mutation that grants the bypass on a non-bool is caught by 7 tests.
- **Folds that are pinned.** Removing the `preflight_commit` fold or the `WorkflowMutationPolicy` fold is caught by `test_commit_to_target_overrides`.
- **The four `mission_write_bypass` call-site edits** (`implement.py` ×2, `tasks_shared.py` ×2) only add an `and not mission_write_bypass(...)` or `or mission_write_bypass(...)`. That is `False` for a `None` slug, so existing refusals are unchanged. The one test edit (`test_tasks_map_requirements_seam.py`) just passes the new `mission_slug` argument; it is not weakened.
- **mypy --strict.** The 5 `no-any-return` errors (`mission_finalize`, `tasks_shared` ×2, `transaction`, `issue_matrix_migration`) are identical at base b1d39706. None are new.
- **The 23-file named set** (`-m "not timing"`, empty `GIT_CONFIG_GLOBAL`): **252 passed, 0 failed**.
