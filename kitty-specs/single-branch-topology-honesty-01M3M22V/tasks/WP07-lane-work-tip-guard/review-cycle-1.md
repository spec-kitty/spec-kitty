---
affected_files: []
cycle_number: 1
mission_slug: single-branch-topology-honesty-01M3M22V
reproduction_command:
reviewed_at: '2026-09-29T04:11:27Z'
reviewer_agent: claude
wp_id: WP07
---

# WP07 review feedback, cycle 1 (reviewer-renata)

**Verdict: changes requested.** The guard, the hook, the installer and the migration are correct and follow the contract (see "Verified"). Two blocking items remain: a fail-closed row of the decision table that nothing tests, and record points that nothing tests.

## Blocking

**Issue 1: the data-model row "tip present, cannot evaluate (git < 2.38) → refuse" is untested at the guard.**

- **Mutation M5.** In `worktree_allocator._refuse_on_tip`, I changed `except AbsorptionUnsupported: raise DestroyedLaneError(...)` to `except AbsorptionUnsupported: return` (fail OPEN). The run of the #5115 file, `test_lane_tip.py`, `test_lane_tip_recorder.py -m "not timing"` and `test_claim_base.py` stayed green: 57 passed.
- **What is covered today.** `test_lane_tip.py:209` only proves that `is_absorbed` raises. Nothing proves the GUARD refuses when it does.
- **Required fix.** Add a guard-level test that simulates an old git: monkeypatch `specify_cli.lanes.worktree_allocator.is_absorbed` (or the merge-tree probe) to raise `AbsorptionUnsupported` for a destroyed lane with a recorded tip. Assert `DESTROYED_LANE` and that the message names the tip SHA and the restore/abandon commands. M5 must then go red.

**Issue 2: the explicit `record_tip` record points are untested. They are load-bearing, not redundant.**

- **Mutations.** Each of these left the same 57 tests green:
  - M2: `tasks_move_task._mt_commit_lane_deliverables` `record_tip` → `pass`;
  - M3: `auto_rebase._finalize_auto_rebase` `record_tip` → `pass`;
  - M4: `implement_support.reenter_lane_self_heal` `record_tip` → `pass`.
- **Why they matter.** They look redundant next to the post-commit hook, but they are the ONLY recording path whenever the hook is not installed:
  - a foreign `post-commit` / `post-rewrite` hook occupies the slot, which C-010 says to skip (your installer's own warning says "recording will only happen at spec-kitty's own lane touches");
  - or a `core.hooksPath` repo where the install is skipped.

  So they must not be dead weight.
- **Required fix.** For each record point, add a focused test that runs with the recorder hook absent or occupied by a foreign hook, drives the real function, and asserts `read_tip(...) == <new lane HEAD>` afterwards:
  - the for_review auto-commit in move-task;
  - the auto-rebase finalize commit;
  - the self-heal re-entry.

  M2, M3 and M4 must each go red. If any point is genuinely redundant even in the foreign-hook case, remove it instead and say why.

## Non-blocking

**Nit 3.** Red-first test 4 (`test_live_branch_backfills_tip`) goes red at 5780a8b9 through `CalledProcessError` from `_git rev-parse` of the missing ref, not an assertion. Prefer `read_tip(...) is not None` / `== head`, so the red is an assertion failure.

**Nit 4: FR-022 deviation.** Accepted as a documented deviation. `_backfill_context_if_missing` is a no-op when a context exists. It closes the orchestrator gap: `test_orchestrator_allocated_lane_has_a_context` drives the real `_resolve_start_workspace`. `create_lane_workspace`'s richer write overwrites the backfill (last-write-wins), so the CLI path's behaviour does not change. Record the deviation from "one allocator that persists" in the Activity Log and the PR.

## Verified

**Red→green.** At 5780a8b9, test 1 fails at `assert result.exit_code != 0` (implement re-cut the lane). The context-deleted and unknown-tip tests fail the same way. The three "re-opens" controls pass. At HEAD, all 7 pass.

**The controls discriminate.** Mutation M1 made `_refuse_on_tip` always refuse. That turned all three controls red: squash-merged, tip==base and ancestor-merged.

**Contract fidelity.**
- The hook body matches the contract verbatim: the signature line, the `${b##*-lane-}` suffix plus the `[!a-z]` guard, and always `exit 0`. It is installed in both `post-commit` and `post-rewrite` at `git rev-parse --git-path hooks`.
- A foreign hook is never overwritten, and there is no backup. Installation is idempotent.
- The installer is separate from `hook_installer.py` (plan fold M5 supersedes the contract's "by policy/hook_installer.py" line; fix that contract line in WP09 docs).
- `lane_tip.py` imports only the stdlib (no `consolidation.*`).

**Guard order.**
- The #4889 base-unreachable refusal still fires first, unchanged. The 26 #4889 guard tests pass.
- Context present with no tip → `LANE_WORK_TIP_UNKNOWN`. A live branch (REUSE / CRASH_RECOVERY) backfills the tip.
- Context deleted with the tip present → refuses.
- The error names the SHA plus the restore and abandon commands.
- With `tip_sha=None` the message is byte-identical to before.

**Other checks.**
- The `executor.py` hunk is one import plus one `clear_tip` call (C-005 minimal).
- The migration is registered (`get_by_id`), idempotent (becomes undetectable after apply), dry-run safe, and skips a foreign hook.

**Tests** (with `GIT_CONFIG_GLOBAL` set to an empty file, and `-m "not timing"`).
- 93 passed across: the #5115 file, `test_lane_tip`, `test_lane_tip_recorder`, the migration test, `test_claim_base`, the #4889 guard file plus its helpers, and `test_issue_4889_caller_independence`.
- Gates: `test_no_dead_symbols` 34, `test_layer_rules` 74.
- ruff is clean.
