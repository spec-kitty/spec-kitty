# Decision Moment `01M37ZQW41RZJM9F08FPRCFRAX`

- **Mission:** `mission-state-audit-trail-durability-01M37PWG`
- **Origin flow:** `plan`
- **Slot key:** `plan.scope.2384-reconciliation`
- **Input key:** `relocation_scope`
- **Status:** `resolved`
- **Created:** `2026-09-23T20:36:29.953428+00:00`
- **Resolved:** `2026-09-23T20:36:38.469115+00:00`
- **Resolved by:** `stijn-dejongh`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

Brownfield pointcut: relocating to a tracked path collides with #2384 (artifacts ignored so repair does not gate accept/merge). Relocate properly (tracked + self-bookkeeping-churn registration, reconciling both concerns; full scope) or warn-only (keep ignored, advisory durability)?

## Options

- relocate-properly-full-scope
- warn-only-small-scope
- Other

## Final answer

relocate-properly-full-scope

## Rationale

Operator chose the full-scope durable fix: tracked audit root AND register it as self-bookkeeping churn so accept/merge/record-analysis dirty-tree gates do not refuse. Reconciles #4928 (durable-by-construction) with #2384 (repair must not gate accept) — churn-classification replaces the ignore as the mechanism that keeps repair from gating accept. Expanded scope: state/contract.py TRACKED surface, is_self_bookkeeping_churn coverage, drop MANIFEST_ROOT from _assert_git_safe checked set (fixes the tracked-path self-block), repoint 3 architectural archive ratchets, keep legacy .kittify/migrations/ ignore for back-compat, update ~12 tests. Also fix guard citation (_assert_git_safe is :2611, not :526).

## Change log

- `2026-09-23T20:36:29.953428+00:00` — opened
- `2026-09-23T20:36:38.469115+00:00` — resolved (final_answer="relocate-properly-full-scope")
