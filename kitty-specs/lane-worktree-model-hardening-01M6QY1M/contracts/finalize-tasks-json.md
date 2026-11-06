# `agent mission finalize-tasks --json`: topology decision (FR-058)

Additive top-level key `topology_decision`. Present on every successful run and on `--validate-only`. Existing keys are unchanged.

```jsonc
{
  "result": "success",
  // ... existing keys (wp_count, lanes, commit_*, planning_commit, ...) unchanged ...
  "topology_decision": {
    "settled_this_run": true,            // false: already settled (explicit, owned_checkout, legacy, or an earlier finalize)
    "topology_source": "default",        // explicit | owned_checkout | default | null (legacy meta)
    "provisional_topology": "single_branch",   // null when settled_this_run is false
    "settled_topology": "lanes_with_coord",    // the stored topology after this run; a default settlement yields only single_branch | lanes_with_coord (DM 01M6R0B954ZPQN5NV4R1ZRE7NY)
    "rule": "lanes_with_coord",                 // wp_count_le_2 | code_lanes_le_1 | lanes_with_coord | null
    "wp_count": 5,                       // non-canceled WPs, planning-artifact WPs included (A-6)
    "code_lane_count": 3,                // excludes lane-planning
    "target_protected": true,            // informational: the outcome is the same on an unprotected target
    "preview": false                     // true under --validate-only: nothing written
  }
}
```

## Refusal (settlement)

`result: "error"`, `error_code` is one of `WRITE_CHECKOUT_OCCUPIED`, `WRITE_CHECKOUT_DIRTY` or `TOPOLOGY_SETTLEMENT_REFUSED`, and `topology_decision.settled_this_run: false`. The Mission stays provisional. `meta.json`, every branch tip and the repository root checkout's branch (the topic branch) are byte-identical to before the run, and no coordination worktree exists (NFR-003).

## Settlement side effects (`lanes_with_coord`)

The repository root checkout moves to `create_return_branch`, then the coordination worktree is materialized on the topic branch, which becomes `coordination_branch`. No commit lands on the target and no fast-forward or merge runs.

## orchestrator-api

`orchestrator-api tasks` passes the `finalize_tasks` payload through, so `topology_decision` appears in its `data` under contract 1.24.0, the Mission's one bump (DM `01M6R0BJQ6Q1MV6492EH6HB66H`).

## Not decided here

The legacy `agent tasks finalize-tasks` repair path and `doctor mission-state --fix` never settle. They report `settled_this_run: false` if they report the key at all.
