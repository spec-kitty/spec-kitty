---
title: Recovery guides
description: Recovery procedures for Spec Kitty operational states, such as restoring access after a logged-out teamspace session or a coord/lane split-brain.
doc_status: active
updated: '2026-10-04'
related:
- docs/index.md
- docs/operations/logged-out-teamspace.md
- docs/operations/upgrade-with-live-lanes-recovery.md
- docs/guides/how-to/recovery/index.md
---
# Recovery guides

Task-oriented recovery procedures for getting an installation or session back to a healthy
state after a failure or interruption.

## In this section

- [Logged-out teamspace](logged-out-teamspace.md) — restore access when your teamspace session has logged out.
- [Sync-drain runbook](sync-drain.md) — work the 3-gate drain order (flag/consent, auth, teamspace) and avoid the `sync doctor` false-green trap.
- [Refusal after an upgrade mid-Mission](upgrade-with-live-lanes-recovery.md) — recover when `consolidate`, review or implement refuses on `.kittify/metadata.yaml` after `spec-kitty upgrade` ran while a Mission had live lanes.

### Coord/lane split-brain recovery

Six recovery entries for the coordination-branch / lane-worktree split-brain states a
coord-topology mission can land in. Each leads with the shipped `spec-kitty doctor …
--fix` where one genuinely exists; the rest are manual, operator-approved procedures,
citing the [coord-branch bookkeeping root-cause
analysis](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/engineering-notes/coord-splitbrain-rootcause.md) for the underlying
"why."

- [Coordination branch created off main (add/add)](coord-off-main-addadd.md)
- [`--start-branch` coordination divergence](start-branch-coord-divergence.md)
- [Stale lane seed after re-finalizing tasks](stale-lane-seed.md)
- [Coordination branch declared but worktree missing](coord-worktree-missing.md)
- [Cutover flip fails from a linked worktree](cutover-flip-linked-worktree.md)
- [Coordination branch stranded after a base rebase](coord-branch-base-strand.md)

## See also

- [How-to guides](../guides/index.md) — including crash and interrupted-merge recovery.
- [Recovery & Troubleshooting](../guides/how-to/recovery/index.md) — the agent-facing
  sibling home: implementation-crash and interrupted-merge how-tos. This page covers
  operational coord/lane recovery (operator-grant, `doctor --fix`); that page covers
  agent-facing crash/merge recovery. Cross-linked, not merged, because the two serve
  different audiences and different failure classes.
- [Documentation home](../index.md)
