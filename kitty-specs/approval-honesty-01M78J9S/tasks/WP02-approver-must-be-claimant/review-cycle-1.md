---
affected_files: []
cycle_number: 1
mission_slug: approval-honesty-01M78J9S
reproduction_command:
reviewed_at: '2026-11-13T01:40:37Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP02
---

# WP02 review feedback (cycle 1) — reviewer-renata

**Verdict: changes requested.** One WP02 defect: the guard compares one identity, and the approval records a different one.

## Defect: a non-claimant reviewer is recorded on an unforced approval

`asserted_review_identity` (`tasks_transition_core.py`) builds the compared identity with `build_status_actor`. The dispatch binding wins for the profile there. `resolve_reviewer_of_record` (`tasks_move_task.py:345-358`) records the **raw** `--agent` / `--reviewer` string as `evidence.review.reviewer` and `review_result.reviewer` (`tasks_move_task_executor.py:139`). So the guard does not check the reviewer field it claims to protect.

Probed through the real `move-task` against the #4670 fixture, with an unforced claim:

1. Claimant `claude:sonnet:reviewer-renata`; `--to approved --agent claude:sonnet:supervisor --profile reviewer-renata`.
   - Result: **exit 0, unforced**.
   - The actor is recorded as `claude:sonnet:reviewer-renata`.
   - `evidence.review.reviewer` and `review_result.reviewer` are both `claude:sonnet:supervisor`.

   A supervisor's identity is recorded as the reviewer of an unforced approval out of another identity's review. This is the case FR-005 forbids, and the docstring ("the identity compared with the review claimant is the one the approval would record") does not hold for the reviewer fields.
2. Your own positive control `test_profile_flag_completes_an_asserted_identity` (claimant `codex::reviewer-renata`, `--agent codex --profile reviewer-renata`) records `review.reviewer = "codex"`. By `same_review_identity`, a bare tool is NOT that claimant (case 10's own rule). The test asserts only the actor, so it does not see this.

Under C-007 this is a relaxed path: a `--profile` can turn a mismatched `--agent` into a match while the reviewer field keeps the mismatch.

**Required:** make the guard refuse unless every identity the approval records equals the claimant. In practice the guard must also hold the identity `resolve_reviewer_of_record` will write (the raw `--agent`, else `--reviewer`, under `same_review_identity`). Alternatively, refuse an `--agent` whose embedded profile conflicts with the binding profile. Either way, the recorded reviewer field must equal the claimant.

Add regression tests for both probes above, and assert `evidence.review.reviewer` / `review_result.reviewer` in the binding tests, not only `actor`.

If you choose to keep `--agent codex --profile reviewer-renata` accepted, the reviewer of record must then record the composed identity. That lives in WP01's combiner, so route it through the orchestrator instead of widening your ownership silently.

## Everything else checked and fine

- **Red-first:** `c9b73536` is test-only, and on `1693d554` it gives 9 failed / 6 passed.
- **Probes:**
  - refusals, all with exit 1, a byte-identical log and the right remedy text (claimant and `--force`, no `action review`):
    - supervisor;
    - `--reviewer` alone;
    - `--agent` and `--reviewer` disagreeing (both named);
    - `--to done` from `in_review`;
  - passes:
    - claimant approval: OK;
    - `--force`: OK, forced, `force-override`;
    - direct approvals from `for_review`: unchanged.
- **Placement:** the guard is pure, sits right after `_guard_agent_ownership` and reuses `same_review_identity`. The 3-line wiring in `tasks_move_task.py` is minimal and its rationale is recorded.
- **Case 9:** a non-claimant now writes nothing. A claimant's `--skip-review-artifact-check` still persists its override record (probed: 3 events). This is strictly safer.
- **Re-pins:** `ac5`, `wp03`, `owned_reopen` and the 6400 split are stale fixtures; their intent is preserved and no assertion is weakened.
- **Standard checks:** ruff, format (`--force-exclude`), C901 and mypy are clean; no forbidden files are touched; the trailers are correct.
