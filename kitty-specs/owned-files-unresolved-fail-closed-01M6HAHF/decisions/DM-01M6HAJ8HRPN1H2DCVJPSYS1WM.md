# Decision Moment `01M6HAJ8HRPN1H2DCVJPSYS1WM`

- **Mission:** `owned-files-unresolved-fail-closed-01M6HAHF`
- **Origin flow:** `specify`
- **Slot key:** `specify.verdict.code`
- **Input key:** `verdict_code`
- **Status:** `resolved`
- **Created:** `2026-11-03T18:25:55.768910+00:00`
- **Resolved:** `2026-11-03T18:25:56.977435+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Reuse an existing evidence code or add a new one for unresolved ownership?

## Options

_(none)_

## Final answer

Add a new topology-neutral code OWNERSHIP_UNRESOLVED (plus its single_branch twin if the alias map requires one). Do not reuse IMPLEMENTATION_UNREADABLE: its meaning (window diff unreadable) and recovery (restore the branch) point the operator the wrong way. Do not reuse OwnedRefusalCode: the verdict also applies to non-owned missions.

## Rationale

_(none)_

## Change log

- `2026-11-03T18:25:55.768910+00:00` - opened
- `2026-11-03T18:25:56.977435+00:00` - resolved (final_answer="Add a new topology-neutral code OWNERSHIP_UNRESOLVED (plus its single_branch twin if the alias map requires one). Do not reuse IMPLEMENTATION_UNREADABLE: its meaning (window diff unreadable) and recovery (restore the branch) point the operator the wrong way. Do not reuse OwnedRefusalCode: the verdict also applies to non-owned missions.")
