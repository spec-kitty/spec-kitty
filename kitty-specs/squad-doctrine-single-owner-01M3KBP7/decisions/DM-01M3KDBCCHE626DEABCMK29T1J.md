# Decision Moment `01M3KDBCCHE626DEABCMK29T1J`

- **Mission:** `squad-doctrine-single-owner-01M3KBP7`
- **Origin flow:** `specify`
- **Slot key:** `specify.commit.safe_commit_tier`
- **Input key:** `safe_commit_tier`
- **Status:** `resolved`
- **Created:** `2026-09-28T07:05:59.441785+00:00`
- **Resolved:** `2026-09-28T07:06:01.421213+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

#5078: is safe-commit consumer doctrine, and who opens PRs for workflow-changing WPs?

## Options

_(none)_

## Final answer

Operator: safe-commit is consumer doctrine (printed recipes become spec-kitty safe-commit <files> -m ... --to-branch <lane>, protected-main planning case spelled out); the WP agent pushes only and the orchestrator opens the draft PR and records the run ID.

## Rationale

_(none)_

## Change log

- `2026-09-28T07:05:59.441785+00:00` — opened
- `2026-09-28T07:06:01.421213+00:00` — resolved (final_answer="Operator: safe-commit is consumer doctrine (printed recipes become spec-kitty safe-commit <files> -m ... --to-branch <lane>, protected-main planning case spelled out); the WP agent pushes only and the orchestrator opens the draft PR and records the run ID.")
