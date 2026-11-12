---
affected_files: []
cycle_number: 2
mission_slug: approval-honesty-01M78J9S
reproduction_command:
reviewed_at: '2026-11-12T21:56:23Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review feedback, cycle 2 (reviewer: claude::reviewer-renata)

**Verdict: changes requested.** All three cycle-1 findings are fixed. I verified each one through the real CLI and with red-first evidence (details below). The out-of-matrix sweep, though, turns up 25 new reds in files no work package owns. The base branch is green on all of them, and WP01 caused all of them. Five are a structural gate that WP01 breaks in its own source files.

## Must fix

1. **The seam re-export gate is red (a real WP01 defect).**
   - **Failing gate.** `tests/specify_cli/cli/commands/agent/test_tasks_move_task_seams.py::test_move_task_reexports_seam_symbol_by_identity`. It is marked `unit`/`fast`, but its directory is out-of-matrix, so per-PR CI never runs it. Five cases are red, each with `AttributeError: module tasks_move_task has no attribute ...`:
     - `tasks_move_task_executor._mt_review_reference`
     - `tasks_move_task_executor._mt_settle_approval_evidence`
     - `tasks_move_task_hops._mt_approval_cycle_result`
     - `tasks_move_task_hops._mt_approval_review_result`
     - `tasks_move_task_hops._mt_record_hop_identity`
   - **Rule.** Every native callable of a `tasks_move_task_*` seam must be an identity re-export on `tasks_move_task`. The base passes this gate.
   - **Required.** Re-export the five names in `tasks_move_task.py` (an owned file), following the existing pattern.
2. **`test_move_task_durability.py`: 20 reds, all caused by WP01.** No WP owns this file. WP03 only runs it, and its prompt (lines 183 and 222) expects it to pass. Base: 145 passed across this file, `test_tasks.py` and the seams file.
   - **(a) 18 tests: stale claimant fixture.**
     - **Cause.** `_seed_wp_event` (line ~186) seeds the `in_review` entry with `force=True`. Under the claimant rule that entry is no claimant, so the approval, which passes no `--agent`, now refuses with `REVIEW_NOT_INDEPENDENT` (placeholder `user`).
     - **Proof.** With only `force=False` in a scratch copy of the file, 31 passed and 2 failed. The two remaining reds are (b) and (c).
   - **(b) `test_json_output_surfaces_skip_reason_end_to_end_for_no_auto_commit` (line 2276).**
     - **Cause.** It asserts that `review_result.reference == --approval-ref` under `--no-auto-commit`. Under WP01 the executor swaps in the `review-cycle://` pointer. plan.md ("swaps only the reference to the verified pointer, which makes `--no-auto-commit` honest") intends that change, so the assertion is stale.
     - **Required.** Re-pin the assertion and say in the commit that a caller `--approval-ref` gives way to the written cycle pointer.
   - **(c) `test_two_queued_rejections_preserve_each_exact_cycle_and_event[causal-mutation]` (line 854, worker thread hangs).**
     - **Cause.** The test wraps `_tmt._mt_hop_review_result` with the OLD five-argument signature, `(st, event, current_event_lane, target, hop_actor)`. WP01 dropped `hop_actor` (`tasks_move_task_hops.py:122`), so the wrapper raises `TypeError` inside the thread.
     - **Required.** Update the wrapper to the new signature.
   - **Required for (a)–(c).** Since no other WP owns or will touch this file, fix it in WP01 under ownership-map leeway, and record that in `add-history`:
     - re-pin (a) with an unforced claim seed or an explicit `--agent`;
     - re-pin (b) and (c) as described above.
3. **Re-run the out-of-matrix sweep before handing back.** Expected afterwards: only `test_move_task_structured_actor_6400::test_recorded_migration_reviewer_identity_stays_a_reconstruction_seed` (WP02) and `test_tasks.py::TestVerdictGuardInMoveTask::test_approve_after_rejected_verdict_without_force_persists_approval` (handed to WP02).
   ```
   pytest tests/specify_cli/cli/commands/agent -k "move_task or approval or verdict or review"
   ```

## Cycle-1 findings: resolved

- **F1 (done actor): resolved.**
  - CLI probe, no flags: refused with `REVIEW_NOT_INDEPENDENT ... placeholder 'user'`. The message is identical to the base's, and the log is byte-identical on both.
  - CLI probe, `--agent codex:gpt5:mover-x`: `actor` = mover and `policy_metadata.tool` = mover. `evidence.review` carries the approval's reviewer and `review-cycle://` reference verbatim, and `force` is false.
  - No other path re-attributes the actor. `_mt_record_hop_identity` gates the hop actor, `st.actor` and the policy tool. A forced done from `approved` gets no claimant.
- **F2 (damaged slot): resolved.**
  - `REVIEW_SLOT_DAMAGED` fires before any write, and the log is byte-identical. With `--approval-ref`, that reference is recorded with `force` false and no `force-override`.
  - `_guard_rejected_verdict` is untouched.
  - The code name is reasonable, and it is recorded in `add-history` for the WP04 ADR amendment.
- **F3 (combiner tests): resolved.** The table has 19 exact-equality cases and covers every branch, including blank and whitespace handling and forced winning over carried.
- **Red-first:** verified in a temporary worktree. At `ff4864fb`: 4 failed, 6 passed, the 4 the commit names. At `07244d63`: 10 passed.
