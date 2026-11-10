# Decision Moment `01M73HHTP85XE7KJVT2235Z1MX`

- **Mission:** `runtime-status-read-door-01M73HHB`
- **Origin flow:** `specify`
- **Slot key:** `specify.auto-remediate.scope`
- **Input key:** `auto_remediate_scope`
- **Status:** `resolved`
- **Created:** `2026-11-10T20:14:21.384523+00:00`
- **Resolved:** `2026-11-10T20:15:13.612998+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

What should 'spec-kitty next --auto-remediate' remediate, and on which paths?

## Options

- Only the missing coordination worktree on the advancing path
- Also the owned-checkout dispatch refusal
- Every block that carries a runnable remedy
- Other

## Final answer

Only the missing coordination worktree on the advancing path: when an advancing next would block because the coordination worktree is not checked out or is empty, materialize it through the existing canonical path (as doctor coordination --fix does), report it, and continue. A deleted coordination branch is never auto-remediated. Query mode ignores the flag.

## Rationale

_(none)_

## Change log

- `2026-11-10T20:14:21.384523+00:00` - opened
- `2026-11-10T20:15:13.612998+00:00` - resolved (final_answer="Only the missing coordination worktree on the advancing path: when an advancing next would block because the coordination worktree is not checked out or is empty, materialize it through the existing canonical path (as doctor coordination --fix does), report it, and continue. A deleted coordination branch is never auto-remediated. Query mode ignores the flag.")
