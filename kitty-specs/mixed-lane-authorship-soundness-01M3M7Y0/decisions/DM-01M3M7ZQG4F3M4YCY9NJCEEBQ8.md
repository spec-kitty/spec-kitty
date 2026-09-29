# Decision Moment `01M3M7ZQG4F3M4YCY9NJCEEBQ8`

- **Mission:** `mixed-lane-authorship-soundness-01M3M7Y0`
- **Origin flow:** `specify`
- **Slot key:** `specify.remediation.strategy`
- **Input key:** `remediation_strategy`
- **Status:** `resolved`
- **Created:** `2026-09-28T14:51:29.156396+00:00`
- **Resolved:** `2026-09-28T14:51:31.901503+00:00`
- **Opened by:** `cli`
- **Other answer:** `true`

## Question

How should #5046 (canceled WP content in a mixed lane escaping the reconciliation gate) be remediated?

## Options

- Option 2: fail-closed REFUSE on implemented canceled WP
- Option 1: per-WP attribution within a lane
- Option 3: document invariant + strict xfail
- Other

## Final answer

Option 1 with a REFUSE fallback: add per-WP commit provenance so canceled-WP content is attributed precisely; unsuperseded canceled content FAILs with CAS revert, superseded content PASSES; WPs lacking provenance (legacy missions, commits outside the governed flow) fall back to a fail-closed REFUSE, and that fallback is pinned.

## Rationale

_(none)_

## Change log

- `2026-09-28T14:51:29.156396+00:00` — opened
- `2026-09-28T14:51:31.901503+00:00` — resolved (final_answer="Option 1 with a REFUSE fallback: add per-WP commit provenance so canceled-WP content is attributed precisely; unsuperseded canceled content FAILs with CAS revert, superseded content PASSES; WPs lacking provenance (legacy missions, commits outside the governed flow) fall back to a fail-closed REFUSE, and that fallback is pinned.")
