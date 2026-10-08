# Decision Moment `01M4B6FZNNSTP6DPN2AAEDEQHZ`

- **Mission:** `upgrade-migration-commit-scope-01M4AKVE`
- **Origin flow:** `plan`
- **Slot key:** `plan.gate.canonical-owners`
- **Input key:** `gate_canonical_owners`
- **Status:** `resolved`
- **Created:** `2026-10-07T12:47:56.597760+00:00`
- **Resolved:** `2026-10-07T12:47:58.568452+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

The empty commit-scope gate needs an exemption for safe_commit's own commit (incl. WP07's index-deletion commit, which is pathspec-less under a temporary index). Exempt the two canonical owners (safe_commit and the merge-conclusion owner) by symbol, with WP05 depending on WP07?

## Options

- exempt the two canonical owners by symbol; WP05 depends on WP07
- re-scope FR-022
- Other

## Final answer

exempt the two canonical owners by symbol; WP05 depends on WP07 (ADR 2026-09-30-1: forbid everywhere except the canonical owner; allowlist stays empty)

## Rationale

_(none)_

## Change log

- `2026-10-07T12:47:56.597760+00:00` — opened
- `2026-10-07T12:47:58.568452+00:00` — resolved (final_answer="exempt the two canonical owners by symbol; WP05 depends on WP07 (ADR 2026-09-30-1: forbid everywhere except the canonical owner; allowlist stays empty)")
