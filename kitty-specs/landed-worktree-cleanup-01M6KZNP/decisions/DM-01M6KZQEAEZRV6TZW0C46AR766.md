# Decision Moment `01M6KZQEAEZRV6TZW0C46AR766`

- **Mission:** `landed-worktree-cleanup-01M6KZNP`
- **Origin flow:** `specify`
- **Slot key:** `specify.prune.process_proof`
- **Input key:** `process_proof`
- **Status:** `resolved`
- **Created:** `2026-11-04T19:14:14.478199+00:00`
- **Resolved:** `2026-11-04T19:19:17.209597+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How is 'no process inside the worktree' proven?

## Options

- /proc scan; unprovable means report-only
- lsof when available
- Other

## Final answer

/proc scan; where unprovable the worktree is report-only

## Rationale

_(none)_

## Change log

- `2026-11-04T19:14:14.478199+00:00` - opened
- `2026-11-04T19:19:17.209597+00:00` - resolved (final_answer="/proc scan; where unprovable the worktree is report-only")
