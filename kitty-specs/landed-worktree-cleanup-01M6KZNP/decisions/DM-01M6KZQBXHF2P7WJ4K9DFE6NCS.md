# Decision Moment `01M6KZQBXHF2P7WJ4K9DFE6NCS`

- **Mission:** `landed-worktree-cleanup-01M6KZNP`
- **Origin flow:** `specify`
- **Slot key:** `specify.prune.branch_delete`
- **Input key:** `prune_deletes_branch`
- **Status:** `resolved`
- **Created:** `2026-11-04T19:14:12.017744+00:00`
- **Resolved:** `2026-11-04T19:19:14.616827+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Should --prune also delete the landed worktree's local branch?

## Options

- Yes, after the same proof
- Worktree only
- Other

## Final answer

Yes, after the same proof (git branch -D only after absorption proof; recreate command printed)

## Rationale

_(none)_

## Change log

- `2026-11-04T19:14:12.017744+00:00` - opened
- `2026-11-04T19:19:14.616827+00:00` - resolved (final_answer="Yes, after the same proof (git branch -D only after absorption proof; recreate command printed)")
