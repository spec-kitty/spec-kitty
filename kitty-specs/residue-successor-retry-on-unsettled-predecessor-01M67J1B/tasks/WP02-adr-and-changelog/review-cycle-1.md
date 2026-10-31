---
affected_files: []
cycle_number: 1
mission_slug: residue-successor-retry-on-unsettled-predecessor-01M67J1B
reproduction_command:
reviewed_at: '2026-10-31T01:04:34Z'
reviewer_agent: reviewer-renata
wp_id: WP02
---

# Review cycle 1 — WP02 (rejected)

Blocking: the amendment and the changelog claim "nothing is written"; the first upgrade run after the
repair appends one `skipped` record to the tracked `.kittify/migration-ledger.jsonl`.

Evidence: with a pre-ledger project at 3.2.0 whose predecessor recorded `failed`/`skipped` (all four
pairs), run 1 applies the successor and records `success`; run 2 re-selects the successor, `detect()`
returns False, and the runner's "not needed" branch records `skipped` — `_record_ledger_result` is
idempotent on `(id, result)`, and `(id, "skipped")` is new, so one line is appended to the *tracked*
partition. Run 3 appends nothing. `_snapshot()` skips `.kittify`, so the no-replay test cannot see it.

Required fixes:
- B1 ADR `Amendment 2026-10-30`, the `detect()` bullet and the new residual: state the one-off `skipped`
  ledger record instead of "no writes".
- B1 CHANGELOG `(#6688)` bullet: same correction; keep under 1,200 characters.
- B1 (cross-WP, declared) `src/specify_cli/upgrade/migrations/base.py`: the `predecessor_id` comment
  repeats the same wrong claim.
- B1 (cross-WP, declared) `tests/specify_cli/upgrade/test_successor_retry_6688.py`: pin the exact write
  behaviour of the repeated run (one `skipped` record, then no growth), so the claim is testable.

Should-fix:
- S1 The seam sentence mis-attributes the rule: its body is `registry._predecessor_outcome_settled_in_view`,
  composed into `_settled_in_view`; `settled_in_selection_view` does not call
  `predecessor_outcome_settled` — only `reselect_when_recorded` does.
- S2 Drop or correct "the ~200 ordinary migrations" (136 registered, 132 without a predecessor).
- S3 The new residual must name both unsettled flavours (`skipped` "not applicable" and #6669's superseded
  no-op), or a reader concludes only pre-ledger projects are affected.
- N1 The test list over-attributes to `MigrationRunner.upgrade`; the two audits are registry-level, and the
  dry run is missing.
- N2 "A predecessor with no record at all is unchanged" holds on a pre-ledger project only.
