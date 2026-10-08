# Decision Moment `01M4AY1VGXRZYAYGQ0883K7JZQ`

- **Mission:** `upgrade-migration-commit-scope-01M4AKVE`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.safe-commit-cli`
- **Input key:** `include_safe_commit_cli`
- **Status:** `resolved`
- **Created:** `2026-10-07T10:20:24.989425+00:00`
- **Resolved:** `2026-10-07T10:20:27.079562+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Include the safe-commit CLI path-expansion bugs (#5401, #5671, #4722; #5393 already fixed) as a parallel WP?

## Options

- include as parallel WP05
- defer to follow-on
- Other

## Final answer

include as parallel WP05

## Rationale

_(none)_

## Change log

- `2026-10-07T10:20:24.989425+00:00` — opened
- `2026-10-07T10:20:27.079562+00:00` — resolved (final_answer="include as parallel WP05")

## Change note (2026-10-07)

The final answer's "parallel WP05" predates the work-package numbering in `tasks.md`: the safe-commit CLI fixes (#5401, #5671, #4722) are WP07, which depends on WP01 (its `safe_commit(index_deletions=...)` work edits one call site in WP01's `upgrade/autocommit.py`), so they are no longer fully parallel. The decision itself (include in this mission) is unchanged.
