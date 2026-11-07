# `agent mission create --json` / `specify` / `orchestrator-api specify`: topology fields (FR-051, FR-052, FR-058)

## Without `--topology` (provisional)

```jsonc
{
  "result": "success",
  // ... existing keys unchanged ...
  "topology": "single_branch",           // the provisional representation (research R-6, DM 01M6R0BDYC29D6XMDY72R22CP9)
  "topology_source": "default",          // new
  "topology_provisional": true,          // new: settled at the first finalize-tasks
  "mission_branch": "kitty/mission-<slug>-<mid8>"   // the topic branch; always minted, any target
}
```

Side effects: exactly one new branch (the topic branch), checked out in the write checkout. The branch the write checkout was on before the switch is recorded in `meta.json` as `create_return_branch` (not in the JSON payload). No lane, lane worktree, coordination branch or coordination worktree is created.

## With `--topology X` or `--owned-checkout`

`topology_source` is `explicit` or `owned_checkout` and `topology_provisional` is `false`. Behaviour is as today (FR-052).

## Unchanged refusals

`--commit-to-target` without `--topology single_branch` refuses exactly as today (FR-060). A create switch onto an occupied or dirty write checkout refuses `WRITE_CHECKOUT_OCCUPIED` / `WRITE_CHECKOUT_DIRTY` (#5676 fix, IC-13).

## Help text

`--topology` help for `create`, `specify` and `orchestrator-api specify` comes from one constant. It describes the size default settled at the first `finalize-tasks` (`single_branch`, else `lanes_with_coord` with the topic branch as the coordination branch, on every target), that plain `lanes` and `coord` are explicit-only, and that an explicit value always wins (FR-059).

## orchestrator-api

The two new fields appear on `orchestrator-api specify` under contract 1.25.0, the Mission's one bump (DM `01M6R0BJQ6Q1MV6492EH6HB66H`).
