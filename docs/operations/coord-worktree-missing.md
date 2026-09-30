---
title: 'Recovery: Coordination Branch Declared but Worktree Missing'
description: "Recovery when a mission's meta.json declares coordination_branch but the -coord worktree was never created, using spec-kitty doctor coordination --fix."
doc_status: active
updated: '2026-08-15'
related:
- docs/operations/recovery-index.md
- docs/operations/stale-lane-seed.md
- docs/archive/plans/engineering-notes/coord-splitbrain-rootcause.md
---

# Recovery: Coordination Branch Declared but Worktree Missing

`spec-kitty agent context resolve` / `agent tasks map-requirements` fail with
`StatusReadPathNotFound`, or `spec-kitty doctor coordination` reports a
`COORDINATION_WORKTREE_NEVER_CREATED` or `COORDINATION_WORKTREE_MISSING`
finding.

## Why this happens

The mission's `meta.json` carries a `coordination_branch` key, but the
`.worktrees/<slug>-<mid8>-coord/` worktree was never created — commonly
because all planning happened on a separate feature branch instead of
through the coordination worktree. Read resolvers intentionally fail closed
rather than silently read stale primary status when coord topology is
declared but its authority surface is absent.

## Lead with the shipped fix

Diagnose first:

```bash
spec-kitty doctor coordination
```

This distinguishes two sub-cases:

- **The declared coordination branch was never created (or was deleted).**
  `--fix` handles this automatically — it removes the stale
  `coordination_branch` key from `meta.json` and re-derives topology:

  ```bash
  spec-kitty doctor coordination --fix
  ```

  `--fix` sweeps **every** mission under `kitty-specs/`, not only the broken
  one. Review the diff before committing, or restore unrelated missions with
  `git checkout -- kitty-specs/` if you meant to scope it narrower.

- **The branch exists but the worktree was never materialized.** `doctor
  coordination` prints the exact recreate command in its finding:

  ```bash
  git -C <repo-root> worktree add .worktrees/<slug>-<mid8>-coord kitty/mission-<slug>
  ```

## If you don't want coordination for this mission

If you never intended to use the coordination worktree (all planning already
lives on a plain feature branch), flatten instead of recreating: remove any
already-materialized coord worktree, then drop the `coordination_branch` key
and re-derive topology.

```bash
git worktree remove --force .worktrees/<slug>-<mid8>-coord   # if it exists
```

Edit `kitty-specs/<mission>/meta.json` to remove `coordination_branch`, then:

```bash
spec-kitty migrate backfill-topology
```

Re-run `spec-kitty agent mission finalize-tasks --mission <handle>` to
re-bootstrap canonical status on the primary checkout.

**Order matters:** removing `coordination_branch` from `meta.json` is not
enough by itself — the read resolver returns the coord worktree whenever it
exists on disk, checked *before* the `meta.json` field is even read. Remove
the worktree first (or in the same pass), or reads keep silently going to the
stale coord copy.

## Related

- [Stale lane seed after re-finalizing tasks](stale-lane-seed.md)
- [Coord-branch bookkeeping root-cause](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/engineering-notes/coord-splitbrain-rootcause.md)
- [Recovery & Troubleshooting (agent-facing)](../guides/how-to/recovery/index.md) — implementation-crash and merge recovery
