# Design Decisions Tracer

## D1 — Reuse symbolic-HEAD detection

The mutating repair calls `_coord_worktree_head_finding`; it does not duplicate
`git symbolic-ref` parsing.

## D2 — Preserve the blocked-fix code

A branch mismatch is another unsafe precondition of the existing repair operation, so
it uses `COORDINATION_BRANCH_STALE_FIX_BLOCKED` and the current multi-mission
continuation path rather than creating a new error family or raising.

## D3 — Success is a postcondition

The command may print `Fast-forwarded` only after the declared coordination ref is
re-read and equals the target SHA.
