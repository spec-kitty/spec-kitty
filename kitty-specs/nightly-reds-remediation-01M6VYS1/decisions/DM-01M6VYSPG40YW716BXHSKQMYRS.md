# Decision Moment `01M6VYSPG40YW716BXHSKQMYRS`

- **Mission:** `nightly-reds-remediation-01M6VYS1`
- **Origin flow:** `specify`
- **Slot key:** `specify.verification.evidence`
- **Input key:** `verification_evidence`
- **Status:** `resolved`
- **Created:** `2026-11-07T21:31:55.268215+00:00`
- **Resolved:** `2026-11-07T21:31:56.525694+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How is each fix verified, given the nodes are nightly-only in CI?

## Options

_(none)_

## Final answer

Run the exact failing node ids locally before (RED) and after (GREEN), then the owning test files and named gates (test_git_remedies, test_read_tracked_meta_6673, test_destructive_op_routing, test_caller_seed_refusal_6754, test_status_broken_charter_6557, etc.); ruff check and ruff format --check --force-exclude on touched files; no full suites (NO_FULL_HEAVY_SUITES_IN_MISSION). Record commands and counts.

## Rationale

_(none)_

## Change log

- `2026-11-07T21:31:55.268215+00:00` - opened
- `2026-11-07T21:31:56.525694+00:00` - resolved (final_answer="Run the exact failing node ids locally before (RED) and after (GREEN), then the owning test files and named gates (test_git_remedies, test_read_tracked_meta_6673, test_destructive_op_routing, test_caller_seed_refusal_6754, test_status_broken_charter_6557, etc.); ruff check and ruff format --check --force-exclude on touched files; no full suites (NO_FULL_HEAVY_SUITES_IN_MISSION). Record commands and counts.")
