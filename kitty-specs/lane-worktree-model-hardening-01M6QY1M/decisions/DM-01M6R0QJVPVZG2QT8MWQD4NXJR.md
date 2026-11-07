# Decision Moment `01M6R0QJVPVZG2QT8MWQD4NXJR`

- **Mission:** `lane-worktree-model-hardening-01M6QY1M`
- **Origin flow:** `plan`
- **Slot key:** `plan.placement.primary-partition-default-topology`
- **Input key:** `primary_partition_default`
- **Status:** `resolved`
- **Created:** `2026-11-06T08:48:45.430898+00:00`
- **Resolved:** `2026-11-06T08:48:47.778522+00:00`
- **Resolved by:** `stijn-dejongh`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

OQ-1 vs OQ-2: where does the PRIMARY partition resolve for a Mission settled from a default topology?

## Options

_(none)_

## Final answer

Topic branch until consolidate: for topology_source: default the PRIMARY partition resolves to the Mission topic branch (meta.mission_branch, also its coordination branch) until consolidate lands it on the target; target_branch stays the landing branch; explicit --topology Missions keep today's placement. Placement contract change recorded by ADR in the S1/S7 ADR WPs; one read door (S1) carries it.

## Rationale

Operator answer, stijn-dejongh, 2026-11-06.

## Change log

- `2026-11-06T08:48:45.430898+00:00` - opened
- `2026-11-06T08:48:47.778522+00:00` - resolved (final_answer="Topic branch until consolidate: for topology_source: default the PRIMARY partition resolves to the Mission topic branch (meta.mission_branch, also its coordination branch) until consolidate lands it on the target; target_branch stays the landing branch; explicit --topology Missions keep today's placement. Placement contract change recorded by ADR in the S1/S7 ADR WPs; one read door (S1) carries it.")
