# Umbrella Op: #5353 slice-3 follow-ups

PR: https://github.com/spec-kitty/spec-kitty/pull/5495 (one PR, per the operator's instruction)
Closes #5479 (R, retrospect), #5480 (M, D2), #5481 (A, auth e2e), #5482 (C, charter sidecar guard), #5483 (Q, scanner). Part of #5353.

## Operator rulings
- `retrospect synthesize --proposal-id` bypassing the accepted-only filter is a bug: non-accepted ids are refused.
- The retrospect auto-commit uses the canonical STANDARD router (`commit_for_mission(kind=RETROSPECTIVE)`), with no MERGE_BOOKKEEPING widening; a protected target warns instead of committing.
- Ship one PR closing all workstream issues; file one issue per workstream.

## Workstreams
- R, M, A, C, Q: implemented, independently reviewed (R twice), and review findings folded.
- S (`ensure_sync_daemon` removal) was superseded by main's dead-code sweep 6180dd01 and ships no code.

## Verification (final tip)
- targeted suite: 1308 passed, 8 skipped
- make test-fast: 2176 passed, 8 skipped
- rebased onto 04f8f0b6: gates plus retrospect and router tests, 182 passed

## Deferred
Listed in the PR's Deferred section.
