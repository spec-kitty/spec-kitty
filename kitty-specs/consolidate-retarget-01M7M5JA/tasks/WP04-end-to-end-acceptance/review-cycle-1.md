---
affected_files: []
cycle_number: 1
mission_slug: consolidate-retarget-01M7M5JA
reproduction_command:
reviewed_at: '2026-11-17T12:46:46Z'
reviewer_agent: claude::orchestrator
wp_id: WP04
---

# WP04 rework (orchestrator, cycle 1): fold the defects your own run surfaced

The operator's standing rule is to fold related gaps, not defer them. Both findings below are about the retarget's own up-front refusal contract (FR-011, NFR-001, FR-009 parity), so they belong in this Mission. Edits outside WP04's files are authorized, with a one-line rationale in the history.

1. **Skip-worktree / assume-unchanged `meta.json` on `<b>` is admitted (contract says refused).**
   - Today `primary_checkout_refusal` compares blob hashes, so a set bit with no edit passes. The run then fails in the landing, and the rollback cannot resync develop: it is left at the squash commit, with a merge record and staged deletions.
   - Fix: in the retarget path (`preflight.retarget_record_refusal`, when `<b>` is a holder), also refuse `RETARGET_RECORD_UNWRITABLE` when `git ls-files -v -- <rel_meta>` shows the skip-worktree (`S`) or assume-unchanged (lowercase) bit. Name the bit in the message and give `git update-index --no-skip-worktree` / `--no-assume-unchanged` as the next step.
   - Do NOT change the bake's `_primary_checkout_refusal` semantics, because that is a different policy. If you add a shared helper, keep the bake's behaviour identical.
   - Add a red-first e2e arm (skip-worktree bit set, no edit) asserting `RETARGET_RECORD_UNWRITABLE`, nothing moved, and dry-run parity.
   - Separately, find out whether a PLAIN (non-retarget) consolidate with skip-worktree on the root checkout's `meta.json` also leaves the target unrestored after a failure. Report the evidence and do not fix it here: it is a pre-existing rollback-resync question that the orchestrator takes to the operator.
2. **`<b>` cut before the Mission existed, with untracked Mission copies in the root checkout.**
   - The real run fails at the root-checkout resync and rolls back, while the dry run forecasts a landing. That is a parity gap, and it also mutates before failing.
   - Fix: when `<b>` is not a holder but the root checkout (on `<b>`) has an untracked `kitty-specs/<slug>/` path the landing would write, refuse `RETARGET_RECORD_UNWRITABLE` up front. The message says the untracked copies would be overwritten; the next step is to remove or commit them. Forecast and real run go through the same verdict.
   - Turn the existing "rolls back fully" arm into a refusal arm with dry-run parity. Keep the "Mission not found" no-copy arm as is (it already moves nothing). Confirm a default-topology Mission (record on its topic branch, `<b>` has no Mission dir and no untracked copies) is still admitted; WP06's suite is the oracle, so run `tests/integration/test_default_mission_consolidate_retarget.py` once at the end.
3. **The kill-window residual does not occur.** You showed a kill between the record commits and `_persist_retarget_committed` resumes and lands with exactly one record. Keep that test. The orchestrator corrects the ADR and how-to through WP05 (do not edit docs/ in this lane).

Re-run the full WP04 set, `tests/consolidation`, `tests/terminus/test_protected_target_preflight.py`, `test_rollback_door.py`, the architecture gates (`-n0`) and `make test-fast`, plus ruff / format / mypy. Then move WP04 back to for_review.
