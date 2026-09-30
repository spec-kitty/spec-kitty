---
title: 'Recovery: --start-branch Coordination Divergence'
description: 'Recovery when agent mission create <mission_slug> --start-branch plus coord topology diverges the coordination branch from the primary planning commit, blocking every lane claim.'
doc_status: active
updated: '2026-08-15'
related:
- docs/operations/recovery-index.md
- docs/operations/coord-off-main-addadd.md
- docs/archive/plans/engineering-notes/coord-splitbrain-rootcause.md
---

# Recovery: --start-branch Coordination Divergence

Every `spec-kitty agent action implement WP##` claim fails with an add/add
conflict on `lanes.json`, even after re-finalizing tasks.

## Why this happens

`spec-kitty agent mission create <mission_slug> --start-branch <start-branch>` (pr-bound) plus
coord topology produces a coordination branch (`kitty/mission-<slug>`) that
does **not** contain the primary planning commit: coord branches from the
old base and gets its own planning snapshot, while spec/plan/tasks and
`lanes.json` land on `<start-branch>`. Lanes seed from coord and merge the
primary `planning_commit_sha` — an add/add conflict on `lanes.json` (it
embeds the SHA) on every claim. Re-finalizing does not converge: the
allocator regenerates coord's snapshot on each claim, and re-finalize
re-captures `planning_commit_sha` against the tip *before* its own commit —
a self-inconsistent loop. Root cause: [Coord-branch bookkeeping split-brain
root-cause](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/engineering-notes/coord-splitbrain-rootcause.md).

**Contributing footgun:** never `git add` `status.json` /
`status.events.jsonl` on the primary branch of a coord-topology mission —
they are coord-authority under this topology. `status.json` has no merge
driver, so it is the first hard conflict layer if you do. Note that
`finalize-tasks` itself commits `status.*` to primary under coord topology —
that is a known split-brain seed, not something you did wrong.

## No shipped `--fix` for this case

There is no `doctor` subcommand for coord/primary divergence of this shape.
`spec-kitty doctor coordination --fix` only removes stale
`coordination_branch` keys and fast-forwards simple Gap-1 staleness — it does
not reconcile two branches that both hold independent planning commits.

## Manual fix (operator-approved)

Reconcile coord FROM the start branch — merge the start branch into the
coord branch, not the other way round. (`spec-kitty doctor coordination`
prints the exact `.worktrees/<slug>-<mid8>-coord` path for your mission —
use that instead of hand-constructing it.)

```bash
git -C .worktrees/<slug>-<mid8>-coord merge <start-branch>
```

Spec Kitty's union merge drivers auto-reconcile `status.events.jsonl`,
`issue-matrix.json`, and `meta.json`; `lanes.json` auto-merges, or resolve
with `git checkout --theirs -- lanes.json` if it doesn't. Coord now CONTAINS
the planning commit, so the next lane seed is a no-op merge and allocation
succeeds.

Disable the sync fan-out while you work through claims — it hangs after the
local state persists, and claims already take 60-120s each on a
coord-topology mission:

```bash
SPEC_KITTY_SYNC_DISABLE=1 spec-kitty agent action implement WP## --mission <handle> --agent <agent>
```

## Related

- [Coordination branch created off main (add/add)](coord-off-main-addadd.md)
- [Coord-branch bookkeeping root-cause](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/engineering-notes/coord-splitbrain-rootcause.md)
- [Recovery & Troubleshooting (agent-facing)](../guides/how-to/recovery/index.md) — implementation-crash and merge recovery
