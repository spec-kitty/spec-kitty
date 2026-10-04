# Decision Moment `01M4457T2HTWW5XGWA55TWYVNT`

- **Mission:** `upgrade-project-global-state-01M44538`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.write_placement`
- **Input key:** `upgrade_worktree_write_placement`
- **Status:** `resolved`
- **Created:** `2026-10-04T19:11:19.121868+00:00`
- **Resolved:** `2026-10-04T19:11:29.330881+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Should upgrade keep writing/committing project-global state in worktrees whose branch integrates back into the primary branch?

## Options

- No: write once on the repository root checkout; skip integrating worktrees
- Yes, but align contents
- Other

## Final answer

No: write once on the repository root checkout; skip integrating worktrees (operator brief Done-when 1; grounding §2/§4)

## Rationale

_(none)_

## Change log

- `2026-10-04T19:11:19.121868+00:00` — opened
- `2026-10-04T19:11:29.330881+00:00` — resolved (final_answer="No: write once on the repository root checkout; skip integrating worktrees (operator brief Done-when 1; grounding §2/§4)")
