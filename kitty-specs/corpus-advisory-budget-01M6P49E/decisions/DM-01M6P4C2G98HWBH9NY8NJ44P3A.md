# Decision Moment `01M6P4C2G98HWBH9NY8NJ44P3A`

- **Mission:** `corpus-advisory-budget-01M6P49E`
- **Origin flow:** `plan`
- **Step id:** `plan.approach`
- **Input key:** `approach`
- **Status:** `resolved`
- **Created:** `2026-11-05T15:13:53.673634+00:00`
- **Resolved:** `2026-11-05T15:16:29.401522+00:00`
- **Opened by:** `22272470+Ivan-Melck@users.noreply.github.com`
- **Other answer:** `false`

## Question

What is the high-level implementation approach?

## Options

_(none)_

## Final answer

Derive the cap from the measured worst case with the repository's existing #5378 headroom formula, record the derivation on the job, extend the guard that already owns the formula to this job, and make a budget expiry legible as INCOMPLETE/advisory via a step budget below the job cap plus a notice step. Reject the path/matrix shard: two live guards pin tree-wide corpus reach and a single pytest invocation. See plan.md Summary and IC-01..IC-04.

## Rationale

_(none)_

## Change log

- `2026-11-05T15:13:53.673634+00:00` — opened
- `2026-11-05T15:16:29.401522+00:00` — resolved (final_answer="Derive the cap from the measured worst case with the repository's existing #5378 headroom formula, record the derivation on the job, extend the guard that already owns the formula to this job, and make a budget expiry legible as INCOMPLETE/advisory via a step budget below the job cap plus a notice step. Reject the path/matrix shard: two live guards pin tree-wide corpus reach and a single pytest invocation. See plan.md Summary and IC-01..IC-04.")
