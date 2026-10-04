# Decision Moment `01M43CMN0GADTHK0Q378QYK2WE`

- **Mission:** `charter-test-cwd-isolation-01M43CM3`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.phase3-dry-run-variant`
- **Input key:** `phase3_dry_run_variant`
- **Status:** `resolved`
- **Created:** `2026-10-04T12:01:25.520427+00:00`
- **Resolved:** `2026-10-04T12:02:27.322352+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

test_phase3_dry_run_evidence_smoke runs 'charter synthesize --dry-run-evidence' as a subprocess in the invoking checkout and is refused from a linked worktree. Remedy test-side (keep the product guard unchanged), change the product so a dry run is not refused, or leave it out of scope?

## Options

- Test-side remedy, guard unchanged
- Product change: dry run not refused
- Out of scope, file follow-up
- Other

## Final answer

Test-side remedy, guard unchanged. Resolved by the orchestrator on the operator's standing end-to-end delegation, as the conservative default: it keeps the mission test-only and leaves the product question (should a dry run be refused from a linked worktree) untouched. Flagged to the operator for reversal at PR review.

## Rationale

_(none)_

## Change log

- `2026-10-04T12:01:25.520427+00:00` — opened
- `2026-10-04T12:02:27.322352+00:00` — resolved (final_answer="Test-side remedy, guard unchanged. Resolved by the orchestrator on the operator's standing end-to-end delegation, as the conservative default: it keeps the mission test-only and leaves the product question (should a dry run be refused from a linked worktree) untouched. Flagged to the operator for reversal at PR review.")
