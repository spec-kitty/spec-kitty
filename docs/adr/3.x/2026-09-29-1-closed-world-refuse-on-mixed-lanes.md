---
title: 'ADR: a mixed lane refuses commits outside every WP work window, with an operator-attested override'
description: 'Consolidation REFUSEs a mixed lane carrying a content commit no WP window owns (closed world), with an operator-attested override as the escape hatch.'
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

## Amendment 2026-10-03 — fully-canceled dependency lanes (#5569)

The residual "a fully-canceled dependency lane's content" is closed. The lane
allocator fast-forwards a dependency lane into its dependent lane, so the
canceled lane's commits sit on the dependent lane's first-parent spine. They are
now subtracted from the dependency-tip exemption (`never_exempt`). A
fully-canceled dependency lane whose branch is deleted or unreadable REFUSEs at
claim time, because its commits can no longer be enumerated; a canceled lane
that no other lane depends on stays tolerated. The remaining strict-`xfail`
residuals drop from five to four.

## Follow-up 2026-10-04 — superseded exemption, unstamped REFUSE and a stable code (#5613)

The 2026-10-03 amendment subtracted every commit of a fully-canceled dependency
lane from the approved claim. Three refinements, none of which runs for a
mission where no approved lane carries such a commit
(`reconciliation._resolve_canceled_dependency_lanes`):

- **Superseded exemption.** A canceled commit stays in the claim when, on every
  approved lane that carries it (a *carrier* lane), a newer, non-canceled,
  non-merge commit touched each of its content paths again
  (`wp_attribution.canceled_spine_content`). Nothing of such a commit is the
  lane's final state, so nothing of it ships. This removes an over-refusal under
  `--strategy merge`. A carrier whose spine cannot be read supersedes nothing.
  Supersession is per path, as on a mixed lane: an approved WP that touches a
  canceled WP's file supersedes the whole path.
- **Unstamped REFUSE and its attestation lift.** A canceled dependency WP with a
  closed work window that carries no `lane_head` stamp has no attribution
  evidence. The claim REFUSEs before any mutation and names the override. This
  covers a mission created before the stamps and a modern mission whose
  best-effort stamp capture failed. `--attest-canceled-superseded <WP>` lifts
  this refusal only, per attested WP, and only while
  `canceled_attestation.OVERRIDABLE_REASONS` lists `no_stamp`. The attestation
  takes no commit out of the subtracted set. An unreadable event log still
  REFUSEs and is not overridable.
- **Stable code.** Content of the canceled lane that is still live on a carrier
  lane and present on the target (and that the pre-consolidation target did not
  already hold) FAILs with `CANCELED_REACHABLE_VIA_DEPENDENCY`
  (`Divergence.canceled_reachable_via_dependency`). The clause names the canceled
  WPs, the canceled lane, the carrier lane and the path, and is rendered
  alongside the strategy axis's own clause.
- **The FAIL is never attest-liftable.** It is computed over all of the canceled
  lane's own commits, attested or not, for a stamped and for an unstamped WP
  alike. The decision above stands: an attestation covers attribution evidence,
  never content that would ship.

The count of strict-`xfail` residuals stays at four.

## Follow-up 2026-10-05: every code lane is now bounded by its approval stamp (#5668)

Decision 1 above says the closed-world check "applies only to mixed lanes; lanes
that are not mixed are unchanged". That sentence describes the closed-world check
and stays true of it. It no longer implies that a lane that is not mixed needs no
bound. ADR [2026-10-04-3](../4.x/2026-10-04-3-approval-stamp-bounds-the-approved-claim.md)
bounds every code lane that has an approved work package by that work package's
approval stamp, and refuses a commit made after it with
`LANE_MOVED_AFTER_APPROVAL`. On a mixed lane the refusals decided here keep their
precedence, codes and texts, and the new check also runs when one of them fires: it is then evaluated and printed in the same message. The
decisions above are unchanged.

## Amendment 2026-10-05: the attestation does not cover a commit of the approval-stamp bound (#5720)

FR-012 stands as decided: an `--attest-canceled-superseded` attestation's own
`lane_head` stamp is a closed-world anchor, so lane commits up to it are exempt
from the closed-world refusal and a later straggler is still refused. The
attestation says that a canceled work package's content is absent or
superseded. It does not say that anyone reviewed the other commits on the lane.

ADR [2026-10-04-3](../4.x/2026-10-04-3-approval-stamp-bounds-the-approved-claim.md)
bounds every code lane by its approved work packages' approval stamps. Its first
version read the attestation's stamp as a covered point of that bound too, so an
attestation let a commit made after an approved work package's approval land
with exit 0, and so did any other later event of the canceled work package. The
owner ruled on [#5720](https://github.com/spec-kitty/spec-kitty/issues/5720)
that the bound wins, and that it exempts nothing. On a lane that also holds a
canceled work package, nothing covers a commit for that bound: no commit the
canceled-work attribution of this ADR assigns to the canceled work package, no
status move of it, no attestation. Three narrower rules that left the canceled
work package's own commits out of the bound each let a commit land unreviewed
(ADR 2026-10-04-3, "Mixed lanes"). A commit made after an approved work
package's approval needs that work package approved again, with or without the
attestation, whoever made it. The canceled-content checks of this ADR then judge
the lane the reviewer saw, and still fail the run when canceled work would ship.

Both refusals can apply to the same lane. The claim then names both in its first
message (ADR 2026-10-04-3, "Operator guidance"), and the operator does both: the
attestation lifts the closed-world refusal, and approving the work package again
lifts the bound. Neither lifts the other, and the order does not matter. The
decisions above are otherwise unchanged.
