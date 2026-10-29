# Data Model — Synthesis record integrity

## Created-artifacts record (existing, unchanged shape)

`.kittify/charter/synthesized-artifacts.yaml`

| Key | Type | Meaning |
|-----|------|---------|
| `created_tactics` | list[str] | every tactic id synthesis has created |
| `created_styleguides` | list[str] | every styleguide id synthesis has created |
| other keys | any | preserved verbatim ("foreign") |

Invariant: the lists only grow. A lost id lets a later run append an operator-removed artifact again. Missing file = empty record (hence the deletion caution, #6455).

## Synthesis lock (new)

| Field | Value |
|-------|-------|
| Path (git) | `<git-common-dir>/spec-kitty-locks/charter-synthesis/<sha256(normcase(resolve(worktree root)))[:32]>.lock` |
| Path (no git) | `<repo_root>/.kittify/runtime/locks/charter-synthesis.lock` |
| Mode | re-entrant per thread, blocking, 10 s timeout |
| Holder record | `kernel.locks.LockRecord` (pid, host, version, acquired_at) |
| Timeout error | `SynthesisLockHeldError`, code `CHARTER_SYNTHESIS_LOCK_HELD` |
| Git unusable | `SynthesisLockUnavailableError`, code `CHARTER_SYNTHESIS_LOCK_UNAVAILABLE` |

Atomicity boundary: the write phase of one `charter synthesize` / `charter resynthesize` run in one worktree.

## Legacy `applies` edge (existing)

`<tactic|styleguide>:<slug> --applies--> directive:<id>` on a synthesized artifact. Strip rule after this mission: stripped only when the source is regenerated in this run (full or topic-scoped); then the stamped `directive --suggests--> <kind>:<slug>` edge replaces it.
