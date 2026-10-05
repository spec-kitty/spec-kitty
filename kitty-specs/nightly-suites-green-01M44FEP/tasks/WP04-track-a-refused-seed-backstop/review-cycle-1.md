---
affected_files: []
cycle_number: 1
mission_slug: nightly-suites-green-01M44FEP
reproduction_command:
reviewed_at: '2026-10-05T06:22:08Z'
reviewer_agent: reviewer-renata
wp_id: WP04
---

# WP04 review cycle 1: changes requested

Reviewer: reviewer-renata. The fix itself is sound; two small changes are required.

1. **Drop the shared mock helper** (`tests/consolidation/test_refused_seed_commit_backstop.py:36,152-154`, docstring `:10-16`). All four tests pass with every one of its eight patches removed, so call the CLI directly with no `_real_bookkeeping_commit_external_mocks`.
2. **"No branch was moved" is unconditional** (`src/specify_cli/consolidation/entry_preflight.py:451`). The refusal has no merge-record check; a re-run after an earlier failed attempt can fire the backstop with a record present. Scope the wording to this run, or reuse `_protected_refusal_footer` (`:393`), and add a unit test for the record-present case.

Residual to record, not required here: only the planning-only path of `orchestrator-api consolidate-mission` reaches the backstop, and it returns a `PREFLIGHT_FAILED` envelope without the cause text; the code-lane path has no backstop.

Verified: red then green (3 failed, 1 passed at the red commit; 4 passed at HEAD); refusal precedes the lock, snapshots and teardown; nothing is deleted; no false positive found; no status events were lost in the base behaviour.
