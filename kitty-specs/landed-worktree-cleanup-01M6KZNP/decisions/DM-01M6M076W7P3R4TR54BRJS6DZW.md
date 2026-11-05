# Decision Moment `01M6M076W7P3R4TR54BRJS6DZW`

- **Mission:** `landed-worktree-cleanup-01M6KZNP`
- **Origin flow:** `plan`
- **Slot key:** `plan.guard.worktree_remove_mode`
- **Input key:** `worktree_remove_mode`
- **Status:** `resolved`
- **Created:** `2026-11-04T19:22:51.143125+00:00`
- **Resolved:** `2026-11-04T19:25:31.166247+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How does --prune remove a worktree given the destructive guard's chokepoint uses --force after its own clean proof?

## Options

_(none)_

## Final answer

Guard gains a no-force mode: same clean proof, then plain git worktree remove

## Rationale

_(none)_

## Change log

- `2026-11-04T19:22:51.143125+00:00` - opened
- `2026-11-04T19:25:31.166247+00:00` - resolved (final_answer="Guard gains a no-force mode: same clean proof, then plain git worktree remove")
