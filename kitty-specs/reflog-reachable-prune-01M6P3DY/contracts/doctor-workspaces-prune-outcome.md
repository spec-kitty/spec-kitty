# Contract: `doctor workspaces --prune` outcome (#7211)

The pruner's per-worktree outcome is `PruneOutcome`
(`src/specify_cli/workspace/landed_worktrees.py`) and is serialised into the
`pruned[]` entries of `spec-kitty doctor workspaces --prune --json`.

## Change

Additive only. Every existing key keeps its name and meaning.

| Key | Type | Meaning |
| --- | --- | --- |
| `path`, `branch`, `tip`, `removed`, `branch_deleted`, `kept_ref`, `recreate`, `refusal` | unchanged | unchanged |
| `kept_commits` | `list[str]` | New. The refs, one per commit, holding a commit that only a reflog this prune destroyed still reached, in the order git reported them. Empty when nothing needed keeping. |

`kept_ref` keeps its existing meaning (the tip record). `kept_commits` is a
separate channel because a tip ref cannot hold a commit no tip reaches.

## Invariants

1. Every ref named in `kept_commits` exists under
   `refs/spec-kitty/discarded/reflog/<sha>` and points at `<sha>`.
2. A commit named there was reachable from no ref after the prune, and its
   content is not provably on the primary ref.
3. When a record cannot be written the outcome is `removed: false` with the
   guard's `DESTRUCTIVE_OP_ONLY_COPY` refusal, and nothing was removed.
4. Text mode prints one `reflog-only commit kept at <ref>` line per entry,
   after the `tip kept at` line and before any branch-kept line.
5. Re-running the prune never moves or duplicates a `refs/spec-kitty/discarded/reflog/<sha>`
   ref: the write is create-only and idempotent.
