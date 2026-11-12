# Data Model: One placement surface after topology settlement

No persisted data changes. The Mission's `meta.json`, `lanes.json` and status log keep their schema.

## Value objects (existing, behaviour clarified)

### WriteLocation (`mission_runtime`)

| Field | Meaning | Invariant after this Mission |
|---|---|---|
| `path` | Mission directory a write of `kind` lands in | unchanged: byte-identical to `read_dir(kind)` for declared-PRIMARY kinds |
| `surface_root` | the checkout (repository root checkout, owned checkout or worktree) that contains `path` | **`path` is always inside `surface_root`** (today broken for PRIMARY kinds of an unlanded default Mission) |
| `surface` | PRIMARY / COORD partition label | unchanged |

### CommitTarget (`mission_runtime`)

`ref` — the branch a write commits to; unchanged. For a settled default Mission every kind resolves
to the topic branch until the landing.

## State: settled default Mission (until its landing)

| Fact | Value |
|---|---|
| `topology` / `topology_settled` | `lanes_with_coord` / `true` (coordination copy of `meta.json`) |
| `mission_branch` == `coordination_branch` | the topic branch |
| holder of the topic branch | `.worktrees/<slug>-coord` |
| repository root checkout | on `create_return_branch`; no Mission `meta.json` |

## Invariants

1. A write's checkout is `write_dir(kind).surface_root`; no call site derives it from `cwd`, the root
   checkout's HEAD or a literal `kitty-specs/<slug>` join.
2. A protected-branch preflight judges `write_target(kind).ref` of the write it guards.
3. No write reaches a protected target; no refusal or exit code changes.
