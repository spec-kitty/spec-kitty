---
title: 'ADR: a mixed lane refuses commits outside every WP work window, with an operator-attested override'
description: 'Consolidation REFUSEs a mixed lane that carries a content commit no governed WP window owns (closed world), and ships an operator-attested override as the only escape hatch for attribution refusals that can never clear.'
status: Accepted
date: '2026-09-29'
---

## Context and Problem Statement

A **mixed lane** is an execution lane that holds an approved WP and a WP canceled
with operator provenance. Lanes integrate whole, so until
[#5046](https://github.com/spec-kitty/spec-kitty/issues/5046) the canceled WP's
committed content shipped at exit 0. Mission
`mixed-lane-authorship-soundness-01M3M7Y0` fixed that with per-WP attribution:
every lifecycle transition of a lane-mapped WP stamps the lane head, the gate
rebuilds each WP's work windows from those stamps, and it FAILs when the
canceled WP's unsuperseded content is on the target.

The pre-PR adversarial squad then found two gaps:

- **Commits outside every window shipped at exit 0.** A content commit that lands
  on the lane after the cancel (a straggler), or a commit by a WP that never
  entered implementation, falls inside no WP's window. The gate attributed it to
  nobody and let it through. No governed WP ever approved that content.
- **Attribution refusals could never clear.** A lane with no stamps (missions
  created before the stamp existed), a window that never closed, a rewritten
  history, or a contested commit REFUSEs. The event log is append-only, so the
  missing evidence cannot appear later. The printed recovery could not succeed.

## Decision

1. **Closed-world REFUSE on mixed lanes (FR-013).** When every work window of
   every lane WP that entered implementation resolved, any non-merge,
   non-bookkeeping first-parent commit of the lane that lies in no WP's window
   (implementation or review) makes the gate REFUSE with reason
   `commit_outside_windows`. Only commits after the lane's own base count: a
   commit reachable from the lane head at its first governed claim, from any
   dependency-lane tip (`lanes.json` `depends_on_lanes`, transitively), or from
   the target's pre-consolidation tip is not outside. The message names the
   lane, up to three short commit shas and one path. The check is computed in the same spine walk as the
   canceled content. It applies only to mixed lanes; lanes that are not mixed are
   unchanged.
2. **Operator-attested override as the escape hatch (FR-012).**
   `spec-kitty consolidate --attest-canceled-superseded <WP> --attest-reason "<text>"`
   records, through the canonical status write seam, an append-only
   operator-provenance attestation on the canceled WP: a forced
   `canceled -> canceled` transition with the actor, the reason, the timestamp,
   `reason_source = "operator"`, and the marker
   `policy_metadata.attestation = "canceled_superseded"`. It needs no change to
   the external event schema and has one authority, the mission's status event
   log. For an attested WP the gate lifts the attribution-evidence REFUSE reasons
   (`no_stamp`, `open_window`, `stamp_not_ancestor_of_lane_tip`,
   `contested_commit`, and "merged with an independent change"). For the closed
   world the attestation is bounded in time: its own `lane_head` stamp becomes an
   anchor, so lane commits up to the attestation are exempt and a straggler
   committed afterwards still REFUSEs. Every explicit attestation is recorded
   afresh (a new operator act with its own reason and a new stamp), so after
   checking a later straggler the operator re-attests and the recovery succeeds.
   It never lifts a FAIL (canceled content
   the gate can see) or an infrastructure refusal (`events_unreadable`,
   `spine_unreadable`).
3. **Each REFUSE names a recovery that can work.** Attribution-evidence refusals
   say the evidence cannot appear later and name the override. Infrastructure
   refusals say they must be repaired and cannot be overridden. FAIL and
   "merged with an independent change" name the supersede-through-a-surviving-WP
   recovery.

**Real-world impact cannot be assessed at this point; this decision is due for
revision as usage and feedback progress.** We do not yet know how often governed
work lands commits outside a stamped window. Workflow merges and bookkeeping-only
commits are excluded by construction. Two governed shapes put commits no lane WP
owns onto a lane's first-parent history, and both are anchored: the allocator
merges a dependency lane into the dependent lane without `--no-ff`
(`lanes/worktree_allocator.py`), so the dependency lane's WP commits fast-forward
onto it; and the recorded planning-artifact commit merge at allocation can
fast-forward other developers' target-branch commits between the lane base and
the planning commit. The anchors trade two gaps for that, both pinned as strict
`xfail` residuals (#5330): an out-of-workflow commit on the lane before the first
governed claim is exempt via the first-claim anchor (the closed world as first
landed caught it), and a fully-canceled dependency lane's content that
fast-forwards into a dependent mixed lane is exempt via the dependency-tip
anchor (a fully-canceled lane is not mixed, so that content shipped before
FR-013 too). Other shapes may still turn up.

## Consequences

- A straggler or never-claimed commit on a mixed lane can no longer ship
  silently. Two residuals the mission had pinned as strict `xfail` (post-cancel
  reintroduction, never-claimed-WP commit) now REFUSE and are pinned as regular
  tests.
- Every consolidation that refuses on a mixed lane has a recovery that can
  succeed: supersede through a surviving WP (FAIL), or verify by hand and attest
  (attribution evidence).
- Attestation shifts responsibility to the operator. The record is durable and
  auditable in the event log, and it is voided by any later governed transition
  of the WP.
- The attestation is a forced self-transition, so it raises the WP's
  `force_count` and publishes one Team Kitty moment. The snapshot's cancellation
  reason becomes the attestation text; the history keeps the original cancel.
- Fixtures that plant a WP's commits must place them inside that WP's stamped
  window (the terminus builder was corrected accordingly).

## Alternatives Considered

- **Keep commits outside every window as a documented residual.** Rejected by the
  operator (decision `01M3NR7XAJGSJCK5YP937KT91H`): unapproved content would keep
  shipping at exit 0 on exactly the lanes this mission set out to protect.
- **Attested window bounds** (the operator supplies the missing stamps).
  Rejected in favour of the override (decision `01M3NR7QRXJBZXQR1B91XKY3JQ`):
  hand-entered SHAs are easy to get wrong, and a wrong bound silently changes
  which content is attributed, whereas an attestation states plainly what the
  operator checked.
- **Ship the refusal without an escape hatch** and file it. Rejected: a permanent
  REFUSE on legacy, straddling or late-cancel lanes blocks the mission forever.

## References

- [#5046](https://github.com/spec-kitty/spec-kitty/issues/5046) — canceled work on a mixed lane shipped silently
- [#5330](https://github.com/spec-kitty/spec-kitty/issues/5330), [#5329](https://github.com/spec-kitty/spec-kitty/issues/5329) — follow-up issues
- Mission `mixed-lane-authorship-soundness-01M3M7Y0` — spec.md FR-011..FR-013
- [`docs/architecture/status-model.md`](../../architecture/status-model.md) — verdict table
