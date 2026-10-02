# Decision Moment `01M3V70EM5F1VEWYCSDDF4SDHZ`

- **Mission:** `coord-artifact-single-home-01M3V4BE`
- **Origin flow:** `plan`
- **Slot key:** `plan.design.fresh-clone`
- **Input key:** `fresh_clone_write`
- **Status:** `resolved`
- **Created:** `2026-10-01T07:49:05.286002+00:00`
- **Resolved:** `2026-10-01T07:52:35.445450+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

In a fresh clone where the coordination branch exists only on the remote, should a COORD write keep the #4970 parity refusal (with a recovery hint) or create the local tracking branch and materialize?

## Options

_(none)_

## Final answer

Keep the #4970 parity refusal for a remote-only coordination branch, with a recovery hint; materialize-then-write applies when the local branch exists and only the worktree is missing.

## Rationale

_(none)_

## Change log

- `2026-10-01T07:49:05.286002+00:00` — opened
- `2026-10-01T07:52:35.445450+00:00` — resolved (final_answer="Keep the #4970 parity refusal for a remote-only coordination branch, with a recovery hint; materialize-then-write applies when the local branch exists and only the worktree is missing.")
