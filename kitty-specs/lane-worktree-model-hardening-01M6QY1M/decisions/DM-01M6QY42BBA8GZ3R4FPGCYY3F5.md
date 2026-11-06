# Decision Moment `01M6QY42BBA8GZ3R4FPGCYY3F5`

- **Mission:** `lane-worktree-model-hardening-01M6QY1M`
- **Origin flow:** `specify`
- **Slot key:** `specify.escalation.s8-compat`
- **Input key:** `single_branch_bound_compat`
- **Status:** `resolved`
- **Created:** `2026-11-06T08:03:08.779729+00:00`
- **Resolved:** `2026-11-06T08:03:11.047364+00:00`
- **Resolved by:** `stijn-dejongh`
- **Opened by:** `claude`
- **Other answer:** `true`

## Question

Escalation: in-flight single_branch Missions have unstamped approvals. What happens to existing Missions when the S8 approval bound is turned on?

## Options

_(none)_

## Final answer

Refuse plus attest: follow the lanes precedent. Every unstamped approval refuses APPROVAL_STAMP_MISSING, and the operator lifts it with --attest-approved-reviewed per WP.

## Rationale

Operator ruling, stijn-dejongh, 2026-11-06 (epic #7276). Quoted as given.

## Change log

- `2026-11-06T08:03:08.779729+00:00` - opened
- `2026-11-06T08:03:11.047364+00:00` - resolved (final_answer="Refuse plus attest: follow the lanes precedent. Every unstamped approval refuses APPROVAL_STAMP_MISSING, and the operator lifts it with --attest-approved-reviewed per WP.")
