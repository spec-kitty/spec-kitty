# Decision Moment `01M4KBWWGDW6NZ0NA7PMEK3175`

- **Mission:** `destructive-residue-context-01M4KBPS`
- **Origin flow:** `plan`
- **Slot key:** `plan.design.teardown-refusal-after-landing`
- **Input key:** `teardown_refusal_after_landing`
- **Status:** `resolved`
- **Created:** `2026-10-10T16:56:17.677984+00:00`
- **Resolved:** `2026-10-10T17:11:27.754140+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Coord teardown runs after the lanes already landed on the target. When it refuses over only-copy files: keep the landing, keep coord branch+worktree, exit non-zero with a new code (re-run consolidate --resume to finish teardown); or roll the landing back?

## Options

- Keep landing, keep coord triple, exit non-zero (recommended)
- Roll the landing back
- Other

## Final answer

A: keep the verified landing, keep the coordination branch+worktree+marker as one triple, skip the branch delete, exit non-zero with a new refusal code; consolidate --resume finishes teardown after the operator commits/moves the files.

## Rationale

_(none)_

## Change log

- `2026-10-10T16:56:17.677984+00:00` — opened
- `2026-10-10T17:11:27.754140+00:00` — resolved (final_answer="A: keep the verified landing, keep the coordination branch+worktree+marker as one triple, skip the branch delete, exit non-zero with a new refusal code; consolidate --resume finishes teardown after the operator commits/moves the files.")
