---
affected_files: []
cycle_number: 1
mission_slug: approval-honesty-01M78J9S
reproduction_command:
reviewed_at: '2026-11-12T20:34:59Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review feedback, cycle 1 (reviewer: claude::reviewer-renata)

**Verdict: changes requested.** The red-first commit, the claimant fact, the deletion of the git-user detector and the minted tokens, and the lint, format, mypy and C901 gates are all good. One honesty defect and one constraint breach block approval.

## Must fix

1. **`approved -> done` without `--agent` attributes the move to the original reviewer (C-007; non-goal "never fabricate a reviewer").**
   - **Evidence.** I reproduced this with a probe through the real CLI, using the T001 fixture. After a claim by `claude:sonnet:reviewer-renata` and an approval, `move-task WP01 --to done` with no `--agent` exits 0. The done event records `actor = {tool: claude, model: sonnet, profile: reviewer-renata, role: reviewer}` and `force: false`. The reviewer did not perform that move.
   - **Before.** On the base this move was refused with `REVIEW_NOT_INDEPENDENT` (the placeholder `user` refusal). Your own red-commit body records that refusal. Relaxing an existing refusal breaches C-007 ("this mission only adds refusals").
   - **Cause.**
     - `tasks_move_task_hops.py:182-184` (`_mt_hop_actor`) returns `record.identity` for the `carried` kind.
     - `tasks_move_task_executor.py:192` sets `st.actor = record.identity`.
     - `tasks_move_task.py:342-344` builds that record.
   - **Required.** FR-007 and decision `carry_forward` govern the **review fields** only: `evidence.review.reviewer` and `reference`, `review_result`, and `policy_metadata.tool` as the carried reviewer. The done hop's **actor** must stay the asserted mover: `--agent`, else a strictly parsed `--reviewer`. With neither, the prior `REVIEW_NOT_INDEPENDENT` placeholder refusal must still fire. A `carried` record must never set the hop actor or `st.actor`.
   - **Tests.**
     - Change T001 case 3 (`test_approval_honesty_identity.py:141`) to pass `--agent <mover>`. Assert the done `actor` is the mover, and that `evidence.review` carries the approval's reviewer and reference verbatim.
     - Add a test that `approved -> done` with neither `--agent` nor `--reviewer` is still refused with `REVIEW_NOT_INDEPENDENT`.

2. **An unforced approval can still record `force-override` (WP01 T005 step 4: "make sure no path emits `force-override` for an unforced review").**
   - **Path.** When the review slot is damaged, `_approval_write_skip_reason` skips the cycle write and `_mt_recorded_approval` returns `None`. A damaged slot is `slot_present`, `result=None`, and not `cleared_without_verdict`. `_mt_review_reference` (`tasks_move_task_executor.py:99-115`) then keeps the provisional `req.effective_approval_ref or "force-override"` from `_approval_evidence`.
   - **Result.** An unforced `in_review -> approved` event is labelled as forced. It is reachable whenever the event log holds a malformed review slot.
   - **Required.** Fail closed instead. Refuse the unforced approval and name the unreadable verdict, for example by reusing the existing `REVIEW_NOT_INDEPENDENT` or the readable-verdict refusal path. A refusal is preferable to recording a false `force-override`. Pin the case with a test.
   - If you believe it is unreachable, prove that with a test, not prose.

3. **The pure combiner has no direct unit tests (T003 step 3).**
   - `resolve_reviewer_of_record` is only patched (seam test) or exercised end-to-end. Several branches are never asserted:
     - `carrying=True` with no recorded approval and an asserted identity gives `force-override`;
     - `carrying=True` with no identity at all gives `None`;
     - forced with an `arbiter_ref`;
     - forced with no identity gives `user`;
     - the review kind keeps `--approval-ref`;
     - blank and whitespace candidates are skipped by `_first_identity`.
   - The `carrying` flag is justified, but only these tests would justify it. Add a table-driven test, for example in the T001 file.

## Handoff notes (not blocking on their own)

4. `test_move_task_structured_actor_6400.py::test_recorded_migration_reviewer_identity_stays_a_reconstruction_seed` is red because of WP01's claimant definition: a `migration:` seed claim (seeded `force=True`) is no longer a claimant, so the unforced approval with no `--agent` refuses. The file is in WP02's `owned_files`, but WP02's prompt does not name this test. Record it in `add-history` with the intended re-pin: assert `--agent` or the refusal, and keep the seed-replay intent of #6754.
5. `test_no_dead_symbols` flags `synthetic_auto_approval_ref` (owned by WP03) and `same_review_identity` (WP02 adds its caller). Both handoffs are acceptable as recorded.

## Verified OK

- Red-first: commit `52e54856` is test-only and its parent is the base. On the base, the new file gives 5 failed, as the commit body states. On the tip, all of its tests pass.
- No `user.name`, `_detect_reviewer_name`, `synthetic_auto_approval_ref(`, `synthetic_approval_ref(` or `auto-forward:` remains on the approval path. The one remaining hit is `tasks_verdict_persistence.py:918`, the cycle writer, which belongs to WP03.
- The absence assertions search the whole JSON line, with positive controls.
- `latest_review_claim_identity` and `same_review_identity` are strict. Bare `claude` is not equal to `claude:sonnet:reviewer-renata`, and the equality rule is not derived from `actor_identities_independent`.
- ruff, `ruff format --check --force-exclude` and mypy are clean on the changed files, with no new suppressions. C901 passes, so `_do_move_task` is at 15 or less. No forbidden files were touched. The trailers are correct.
