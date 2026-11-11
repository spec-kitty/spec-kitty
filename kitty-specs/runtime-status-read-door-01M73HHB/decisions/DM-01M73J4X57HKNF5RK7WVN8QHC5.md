# Decision Moment `01M73J4X57HKNF5RK7WVN8QHC5`

- **Mission:** `runtime-status-read-door-01M73HHB`
- **Origin flow:** `plan`
- **Slot key:** `plan.scope.advancing-auto-materialize`
- **Input key:** `advancing_auto_materialize`
- **Status:** `open`
- **Created:** `2026-11-10T20:24:46.503450+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Advancing next already auto-materializes a missing/empty coordination worktree silently (bootstrap write seam), so the 'materialize it' block and --auto-remediate are unreachable from the CLI. What should the Mission do?

## Options

- Drop --auto-remediate; report the implicit materialization in one line
- Make materialization opt-in via --auto-remediate (block by default)
- Drop --auto-remediate; leave behaviour silent
- Other

## Final answer

_(none)_

## Rationale

_(none)_

## Change log

- `2026-11-10T20:24:46.503450+00:00` - opened
