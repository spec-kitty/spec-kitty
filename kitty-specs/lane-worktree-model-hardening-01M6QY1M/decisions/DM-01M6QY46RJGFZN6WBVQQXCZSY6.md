# Decision Moment `01M6QY46RJGFZN6WBVQQXCZSY6`

- **Mission:** `lane-worktree-model-hardening-01M6QY1M`
- **Origin flow:** `specify`
- **Slot key:** `specify.escalation.s7-deferred-materialization`
- **Input key:** `topology_materialization`
- **Status:** `resolved`
- **Created:** `2026-11-06T08:03:13.299018+00:00`
- **Resolved:** `2026-11-06T08:03:15.625576+00:00`
- **Resolved by:** `stijn-dejongh`
- **Opened by:** `claude`
- **Other answer:** `true`

## Question

Escalation: on a protected target lanes is refused at consolidate and a provisional coordination branch already exists from create. Which rule applies?

## Options

_(none)_

## Final answer

Unless the mission is specified with an explicit topology being defined, no worktrees/lanes/coord branch should be created. A single topic branch for the mission is minted, regardless of default branch protected status. Once the topology is settled, and the finalization has completed -> lanes/worktrees are created. That solves the discrepancy rather naturally, and is more efficient (delay creation until the topology is chosen). Rationale: reworking and reminting topologies is expensive, and compressing a lanes/coord topology into a single_branch one is the most expensive approach. The inverse is a lot simpler to perform.

## Rationale

Operator ruling, stijn-dejongh, 2026-11-06 (epic #7276). Quoted as given.

## Change log

- `2026-11-06T08:03:13.299018+00:00` - opened
- `2026-11-06T08:03:15.625576+00:00` - resolved (final_answer="Unless the mission is specified with an explicit topology being defined, no worktrees/lanes/coord branch should be created. A single topic branch for the mission is minted, regardless of default branch protected status. Once the topology is settled, and the finalization has completed -> lanes/worktrees are created. That solves the discrepancy rather naturally, and is more efficient (delay creation until the topology is chosen). Rationale: reworking and reminting topologies is expensive, and compressing a lanes/coord topology into a single_branch one is the most expensive approach. The inverse is a lot simpler to perform.")
