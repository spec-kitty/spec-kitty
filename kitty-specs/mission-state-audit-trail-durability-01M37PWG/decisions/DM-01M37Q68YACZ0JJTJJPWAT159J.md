# Decision Moment `01M37Q68YACZ0JJTJJPWAT159J`

- **Mission:** `mission-state-audit-trail-durability-01M37PWG`
- **Origin flow:** `specify`
- **Slot key:** `specify.audit-trail.commit-behavior`
- **Input key:** `audit_commit_behavior`
- **Status:** `resolved`
- **Created:** `2026-09-23T18:07:04.650077+00:00`
- **Resolved:** `2026-09-23T18:08:35.893734+00:00`
- **Resolved by:** `stijn-dejongh`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

Once the audit trail lives at a git-tracked path, does 'doctor mission-state --fix' commit it itself, or write it to the tracked location and leave the operator to commit (with the exit summary telling them to)?

## Options

- write-only-operator-commits
- fix-auto-commits-audit-trail
- Other

## Final answer

write-only-operator-commits

## Rationale

Repair stays a non-git-mutating maintenance op: --fix writes manifest+quarantine to the tracked path and the exit summary instructs the operator to commit them. Avoids surprise commits in a dirty tree and entanglement with the operator's staged changes.

## Change log

- `2026-09-23T18:07:04.650077+00:00` — opened
- `2026-09-23T18:08:35.893734+00:00` — resolved (final_answer="write-only-operator-commits")
