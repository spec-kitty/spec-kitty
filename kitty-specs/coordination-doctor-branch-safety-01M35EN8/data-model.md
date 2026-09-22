# Data Model: Coordination Doctor Branch Safety

This repair introduces no persisted data. It clarifies the runtime invariants among
existing Git and mission-metadata values.

## Entities

### Mission coordination metadata

- `coordination_branch`: the declared ref that `--fix` is allowed to advance.
- `target_branch`: the ref whose tip is the requested fast-forward destination.
- `mission_slug` and `mission_id`: inputs used to resolve the recorded coordination
  worktree path.

### Coordination worktree state

- `path`: resolved by `CoordinationWorkspace.worktree_path`.
- `actual_head_ref`: symbolic `HEAD`, or the detached sentinel.
- `dirty`: whether `git status --porcelain` reports changes.

### Repair finding

- `severity`: `error` when a mutation precondition or postcondition is unsafe.
- `error_code`: stable `COORDINATION_BRANCH_STALE_FIX_BLOCKED` for a refused repair.
- `message`: names the concrete reason, including branch mismatch.
- `next_step`: manual inspection/recovery guidance.

## Invariants

1. A repair may mutate only when `actual_head_ref == refs/heads/<coordination_branch>`.
2. The coordination ref must be a strict ancestor of the target ref before mutation.
3. The coordination worktree must be clean before mutation.
4. Success may be printed only after the declared coordination ref equals the target
   SHA.
5. A failed invariant mutates no branch and produces a structured error finding.

## State Transition

`stale + correct branch + clean` -> `coordination ref equals target`.

All other states remain unchanged and become an operator-visible blocked repair.
