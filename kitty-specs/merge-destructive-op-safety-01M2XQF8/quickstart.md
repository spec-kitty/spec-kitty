# Quickstart — Red-First Repro Recipes

How to reproduce each defect RED before its fix (ATDD, NFR-004). All use real git;
mock only out-of-git side effects, per
`tests/integration/test_merge_lane_planning_data_loss.py` Layer 2.

## #4752 — primary checkout reset

1. Real repo + mission staged to merge; put the primary checkout on a non-target
   branch with an uncommitted tracked edit.
2. Drive `_run_lane_based_merge` with `_real_merge_external_mocks`; do NOT mock
   `_refresh_primary_checkout_after_merge`.
3. RED assert (pre-fix): the tracked edit is destroyed / `SafeCommitHeadMismatch`
   raised after the ref advanced.
4. GREEN (post-fix): preflight refuses with `DestructiveOpRefused`
   (`MERGE_UNSAFE_PRIMARY_OFF_TARGET`/`_DIRTY`) before any ref advance; edit
   survives; repo byte-identical.
5. Also add a `--resume` variant (US1 AC4).

## #4753 — lane worktree force-remove

1. Real repo + one lane worktree; leave a tracked edit + an untracked file
   uncommitted in it (never on the lane branch).
2. Drive the merge through the cleanup phase; do NOT mock the worktree loop.
3. RED (pre-fix): worktree force-removed, files gone, exit 0.
4. GREEN (post-fix): preflight detects the dirty worktree; fail-closed refusal
   (no retention) OR retained (retention flag); files survive.
5. Coord variant: dirty coord worktree → refusal holds back the coupled coord
   branch + marker teardown (FR-004); assert all three survive together.

## #4754 — abort of the user's own merge

1. Real repo; create a genuine in-progress user merge (`MERGE_HEAD` in `repo_root`)
   and NO spec-kitty merge state.
2. Run `_dispatch_abort` (the `merge --abort` path).
3. RED (pre-fix): `git merge --abort` fires on `repo_root`; user's resolution lost;
   "No active merge state to abort." followed by "Aborted in-progress git merge."
4. GREEN (post-fix): no abort on `repo_root`; user's `MERGE_HEAD` preserved;
   messaging internally consistent.

## Parity + residue (regression safety)

- Clean/on-target merge, `--resume`, and abort-with-active-state: unchanged behavior
  (NFR-002).
- `meta.json` diff limited to the VCS-lock stamp does NOT trigger a refusal
  (NFR-003) — dedicated unit test on `assert_worktree_clean` with the injected
  `is_toolchain_generated_churn`.

## Local test commands (targeted)

```bash
cd <clone>
.venv/bin/python -m pytest tests/integration/test_merge_lane_planning_data_loss.py -q   # harness home
.venv/bin/python -m pytest tests/git/ tests/specify_cli/merge -q                        # guard + merge units
.venv/bin/python -m pytest tests/architectural/ -k "destructive or routing" -q          # NFR-006 gate (targeted)
```
