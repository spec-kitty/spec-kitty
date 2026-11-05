# Decision Moment `01M6MKH1MTXGX9YKARWHR8FJAE`

- **Mission:** `landed-worktree-cleanup-01M6KZNP`
- **Origin flow:** `plan`
- **Slot key:** `plan.prune.unreadable_process`
- **Input key:** `unreadable_process_policy`
- **Status:** `resolved`
- **Created:** `2026-11-05T01:00:16.410615+00:00`
- **Resolved:** `2026-11-05T06:41:43.661499+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How should the prune treat a same-uid process whose cwd cannot be read (PermissionError)?

## Options

_(none)_

## Final answer

Skip and report: ignore same-uid processes whose cwd cannot be read, report how many could not be inspected, document the residual next to the other-uid one

## Rationale

_(none)_

## Change log

- `2026-11-05T01:00:16.410615+00:00` - opened
- `2026-11-05T06:41:43.661499+00:00` - resolved (final_answer="Skip and report: ignore same-uid processes whose cwd cannot be read, report how many could not be inspected, document the residual next to the other-uid one")
