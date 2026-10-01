# Decision Moment `01M3SSYJR31BC18KBK2RJP0VWX`

- **Mission:** `git-paths-are-data-01M3SSXR`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.pr-5437`
- **Input key:** `pr_5437_handling`
- **Status:** `resolved`
- **Created:** `2026-09-30T18:41:38.051718+00:00`
- **Resolved:** `2026-09-30T18:41:56.661854+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How does the mission treat external PR #5437 (point fix for #5400)?

## Options

- Carry its commit (cherry-pick -x, authorship kept) and its tests as the oracle; re-express the predicate on GitPath
- Ignore it and write fresh tests
- Other

## Final answer

Carry its commit (cherry-pick -x, authorship kept) and its tests as the oracle; re-express the predicate on GitPath

## Rationale

_(none)_

## Change log

- `2026-09-30T18:41:38.051718+00:00` — opened
- `2026-09-30T18:41:56.661854+00:00` — resolved (final_answer="Carry its commit (cherry-pick -x, authorship kept) and its tests as the oracle; re-express the predicate on GitPath")
