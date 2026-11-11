# Decision Moment `01M73J4X57HKNF5RK7WVN8QHC5`

- **Mission:** `runtime-status-read-door-01M73HHB`
- **Origin flow:** `plan`
- **Slot key:** `plan.scope.advancing-auto-materialize`
- **Input key:** `advancing_auto_materialize`
- **Status:** `resolved`
- **Created:** `2026-11-10T20:24:46.503450+00:00`
- **Resolved:** `2026-11-11T05:07:29.279510+00:00`
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

No flag; report it. Drop --auto-remediate. Keep advancing next's automatic materialization, and make it visible: one line and a remediation key in --json when the bootstrap had to create or restore the coordination worktree. The board's selector-level block stays for direct callers. Supersedes the --auto-remediate parts of DM-2 and the auto-remediate scope decision (verified: the block is unreachable from the CLI).

## Rationale

_(none)_

## Change log

- `2026-11-10T20:24:46.503450+00:00` - opened
- `2026-11-11T05:07:29.279510+00:00` - resolved (final_answer="No flag; report it. Drop --auto-remediate. Keep advancing next's automatic materialization, and make it visible: one line and a remediation key in --json when the bootstrap had to create or restore the coordination worktree. The board's selector-level block stays for direct callers. Supersedes the --auto-remediate parts of DM-2 and the auto-remediate scope decision (verified: the block is unreachable from the CLI).")
