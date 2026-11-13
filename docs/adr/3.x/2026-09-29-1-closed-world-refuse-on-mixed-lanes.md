---
title: 'ADR: a mixed lane refuses commits outside every WP work window, with an operator-attested override'
description: 'Consolidation REFUSEs a mixed lane carrying a content commit no WP window owns (closed world), with an operator-attested override as the escape hatch.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-09-29'
updated: '2026-11-12T00:00:00Z'
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
  `--strategy merge`. A carrier whose spine cannot be read supersedes nothing
  (and, since #6313, REFUSEs; see Follow-up 2026-10-27).
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
bound. ADR [2026-10-04-5](../4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md)
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

ADR [2026-10-04-5](../4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md)
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
(ADR 2026-10-04-5, "Mixed lanes"). A commit made after an approved work
package's approval needs that work package approved again, with or without the
attestation, whoever made it. The canceled-content checks of this ADR then judge
the lane the reviewer saw, and still fail the run when canceled work would ship.

Both refusals can apply to the same lane. The claim then names both in its first
message (ADR 2026-10-04-5, "Operator guidance"), and the operator does both: the
attestation lifts the closed-world refusal, and approving the work package again
lifts the bound. Neither lifts the other, and the order does not matter. The
decisions above are otherwise unchanged.

## Follow-up 2026-10-16: a canceled dependency lane that never started (#5937)

The 2026-10-03 amendment REFUSEs a fully-canceled dependency lane whose branch
is deleted or unreadable. One exception: a missing branch is tolerated when the
status event log proves the lane never started, that is, every work package of
the lane was canceled from `planned` or `blocked` and none ever moved into any
other lane than `planned`, `blocked` or `canceled`
(`wp_attribution.lane_never_started`). Such a lane never had a branch, so none
of its commits can be on a dependent lane's spine. An unreadable or incomplete
event log, a lane-tip ref still recorded for the branch, and an existing branch
whose range cannot be read keep refusing. The decisions above are otherwise
unchanged.

## Amendment 2026-10-22: canceled content is judged line by line (#6309)

Both canceled-content checks (the mixed-lane check and the canceled-dependency
check) ask the same question: does a canceled commit's change still live in the
lane's final state for a path that a surviving commit touched later? #5932
answered it with an all-lines test. The change counted as gone unless every line
the canceled commit added was still present. That left three ways for rejected
work to ship at exit 0:

- a surviving commit that kept two of three canceled lines laundered the two;
- a canceled deletion (it added nothing) read as gone whenever a surviving commit
  touched the file;
- a surviving commit that renamed the file left the canceled content at a path
  nothing checked.

The operator ruled on #6309 as follows.

1. **A kept line is canceled content.** A non-blank line that `git blame`
   still attributes to a canceled commit means the change survives, and the gate
   FAILs. This applies even when a surviving commit rewrote the rest of the hunk,
   including when the only kept line is a signature such as `def wp01() -> int:`.
   No line rule can tell such a signature from the two kept lines of #6309,
   because blame attributes both the same way. Blank, whitespace-only and
   punctuation-only lines (`}`, `),`) are ignored, so a full rewrite that happens
   to keep one of them is not flagged. Blame runs with `-w`, so re-indenting or
   converting to CRLF keeps the line's author. It runs with `-M`, so moving a
   longer line inside the file keeps it too. A line that a surviving commit
   removed and later re-added belongs to that commit. The #5932 all-lines test
   remains a second way to flag a change as surviving, so nothing it caught is
   lost.
2. **A deletion stays in effect unless it is undone or reworked.** The deletion
   is placed in the final state by the nearest lines around it that survive. A
   `--reverse` blame finds those lines. The deletion is over in two cases:
   - its lines are back in that spot;
   - a surviving commit rewrote the spot, so the spot holds non-blank lines and
     no canceled commit wrote any of them. For example, a canceled change from
     `value = 1` to `value = 2`, followed by an approved change to
     `value = 3`, is approved work.

   Only lines written after the canceled commit count as being in the spot.
   An original line that survives untouched is never rework, even when moving
   a neighbouring line stretches the spot over it.

   An empty spot keeps the deletion in effect. This covers the case raised in
   the #6310 review: a canceled WP removes an auth check, an approved WP appends
   elsewhere, and the gate now FAILs. Adding the same line somewhere else does
   not undo the deletion.
3. **A rename is followed.** When the path is gone from the final state, a
   rename of it is found with no rename limit (`diff.renameLimit=0`). The
   content is then judged at the new path. `CanceledPathState.path` and
   `CanceledDependencyContent.path` name the new path, which is where the
   target is compared and what the verdict prints. The old path is carried as
   `renamed_from`, and the verdict shows it as "(renamed from '…')". A path
   renamed to more than one target REFUSEs, because which copy carries the
   content is ambiguous.

**Fail-closed and bounded.** Any git error or unparseable output raises
`GitProbeError`, which the callers already map onto REFUSE. Blame is limited to
history after the oldest canceled commit. Each walk makes one forward blame per
path, however many canceled commits touched it. One reverse blame and one diff
are added per canceled commit that removed lines that are not blank. The
rename lookup diffs the range from the newest canceled commit to the lane tip
with no rename limit, so its cost grows with the files added and deleted in that
range. It runs only when the path is gone from the final state. The blame
and diff reads live in `kernel.git.blame`, which pins `diff.algorithm=myers` and
turns off textconv and external diff drivers. The attribution rules live in
`specify_cli.consolidation.line_attribution`, which replaces
`git_probes.canceled_content_survives`.

**Verdicts that change.**

| Case | Before | After |
|------|--------|-------|
| A survivor keeps some canceled lines and drops others (former residual 8) | PASS | FAIL |
| A survivor rewrites a canceled file but keeps a non-blank canceled line, such as a signature | PASS | FAIL |
| A survivor re-indents canceled lines or converts them to CRLF | PASS | FAIL |
| A canceled deletion stays in effect under a later approved edit | PASS | FAIL |
| A canceled deletion's line is re-added elsewhere | PASS | FAIL |
| A survivor renames the canceled path and keeps the content | PASS | FAIL, naming the new path |
| A survivor rewrites the canceled change itself (`1 → 2 → 3`) | PASS | PASS |
| A full rewrite that shares only blank or punctuation lines | PASS | PASS |
| A survivor reverts the canceled commit, or removes and re-adds lines itself | PASS | PASS |

The dependency-lane fixture whose approved WP "overwrote" WP01's file kept
WP01's signature line. Under this ruling that line is canceled content, so the
fixture now rewrites both lines. The test it supports still checks that a
superseded canceled commit stays in the carrier's authorship without its blob.

**Residuals (strict `xfail`).** Two are pinned in
`tests/consolidation/test_canceled_line_attribution_6309.py`:

- approved lines inserted exactly where a canceled deletion was count as
  reworking that spot, so the deletion reads as superseded;
- canceled content that a surviving commit copied into another file is not
  followed.

Two more are documented here without a pin:

- a short line (below git's `-M` threshold) moved within the file is followed
  only by the all-lines test, that is, only when every canceled line survives;
- a rename whose old path is then re-created is judged at the re-created path.

Content resolved inside a merge commit stays the existing residual. The
decisions above are otherwise unchanged.

## Follow-up 2026-10-27: an unreadable carrier spine REFUSEs (#6313)

The 2026-10-04 follow-up let a `GitProbeError` on a carrier lane's spine
(`wp_attribution.canceled_spine_content`) subtract the carried canceled commits
and record no content. That was not the stricter verdict. The canceled lines
stay in the carrier's authored blobs, so the squash blob-attribution axis passed
and canceled content could ship at exit 0. It also contradicted this record's
own rule that the callers map `GitProbeError` onto REFUSE.

`reconciliation._carried_dependency_content` now REFUSEs before any mutation
with reason `spine_unreadable`, the same reason a mixed lane uses for an
unreadable spine. The refusal names every canceled WP of every fully-canceled
lane an unreadable carrier holds, once each, with the unreadable carriers that
hold it. The recovery names the carrier: repair its branch, or, when the error
reports a path renamed to more than one path (a deterministic `GitProbeError`
from line attribution), keep only one of those renames on the carrier, then
re-run. `canceled_attestation.OVERRIDABLE_REASONS` still omits
`spine_unreadable` (operator ruling of 2026-10-27, recorded on #6313), so
`--attest-canceled-superseded` does not lift it. The rule is the same on both
axes.

Residuals: `_lane_first_parent_spine` and `_lane_tip_commits` still read an
unreadable lane as empty. An approved lane whose spine read fails that way is
not seen as a carrier, so this refusal does not fire for it. Its authored set is
then empty, so the blob-attribution axis is expected to fail it rather than pass
it (not pinned by a test). The mixed-lane recovery for `spine_unreadable` does
not name the ambiguous-rename fix either.

## Amendment 2026-10-31: an operator-declared dependency ref is inherited history (#6771)

A lane that merges an external dependency branch's newer head (`git merge --no-ff <dep>`,
reviewed on the merged tree) brings that branch's commits into the closed-world window. No
work package's window owns them, so the landing was refused as `un-attributable`, and
`--dry-run` previewed green. Structure cannot tell that merge from a removed work package
riding a carrier lane (#4945), so the operator declares the ref:
`spec-kitty consolidate --dependency-ref <ref>` (repeatable, CLI only).

- **Meaning.** The declared ref's commits in the window (`window_base..ref`) are inherited
  history, never attributed to a work package. They join the content that predates the
  window on the closed-world axis and on the squash blob and deletion axes, which read the
  same final per-path state the lane authorship uses. An undeclared restack still refuses.
- **Verification, before any branch moves (`reconciliation.resolve_external_dependency_refs`).**
  Each ref must resolve and be reachable from the mission branch or a lane branch. It is
  refused when it is named inside the Mission's own branch namespace, when its window holds a
  commit on a lane's or the mission branch's first-parent spine, when its window holds a
  `lane_head` stamp ANY work package recorded in the status log (canceled and removed ones
  included), or when its window holds the recorded work tip of a Mission lane branch
  (`refs/spec-kitty/lane-tip/*`). The last three make the guard independent of the CURRENT
  `lanes.json`: a removed work package's lane branch is deleted and unlisted, which is
  exactly the shape that would otherwise exempt it. A lane branch that exists but whose spine
  cannot be read refuses. A guard failure exempts nothing.
- **Pinned at claim.** The first claim build resolves each ref to a SHA and records
  `ConsolidationState.dependency_ref_pins`. The gate and a `--resume` verify that commit; a
  name that now resolves elsewhere refuses naming both SHAs (`DEPENDENCY_REF_MOVED`), and a
  deleted name does not unpin a commit that still exists. A record written before pins
  existed holds names only and is pinned on first use. A `--resume` that restates a
  different set refuses (`DEPENDENCY_REF_SET_CHANGED`): the record is the audit trail.
- **Not read by other axes.** The approved bound (#5668) and the canceled-content axes do not
  read the declaration: a dependency merged into a lane after review approved it still
  refuses `LANE_MOVED_AFTER_APPROVAL`, and canceled content is still judged line by line.
- **CLI only.** `orchestrator-api consolidate-mission` has no way to declare a ref, so an
  undeclared restack fails closed there.
- **`--dry-run`** now builds the full claim and runs the closed-world scan over the refs the
  landing would introduce, so it reports claim-time refusals (a mis-declared ref, an
  unevaluable claim) instead of previewing green. It unions the recorded declaration with
  the command line, as a re-run would.
- **Residual.** The guard detects Mission work only through what the Mission left behind.
  A raw-SHA declaration skips the namespace-name guard, because a SHA carries no branch name.
  A removed work package that left no `lane_head` stamp, no lane-tip ref and no namespaced
  branch cannot be detected: the operator's declaration is then the only authority.
  Recorded stamps and lane tips are matched against the first-parent history back to the
  window base, so a lane merged at an earlier commit than its later stamped tip is caught.


## Amendment 2026-11-07: a lane's own dependency merges are its work (#7307)

The implement allocator merges each declared dependency lane into a dependent lane before
that lane's first claim (`Merge dependency lane X into Y`, `lanes/worktree_allocator.py`).
Two rules of the closed-world scan (`MergeOutcomeVerifier._unattributable_in`) then read that
merge as content that belongs to no approved work package: the #5968 own-base bound drops it
from the lane's authorship because it precedes the first claim stamp, and a merge was skipped
only when its default `git show` (`--cc`) patch-id was empty, which is false for a clean merge
whose parents both touched one region.

- **A merge is judged by what it adds beyond its parents.** `git_probes.merge_own_changed_paths`
  runs `git show --remerge-diff --name-only`: the paths where the recorded merge differs from
  git's own re-merge of its parents. No such path, or only bookkeeping paths, means the merge
  carries no content of its own, and its parents' commits are judged on their own. A
  resolution is content, also one that kept one side (an empty `--cc` diff, which the old skip
  let through).
- **A lane's own reviewed dependency merge is attributed to that lane.** A first-parent spine
  commit of an approved lane whose every non-first parent is reachable from a declared
  dependency lane (`depends_on_lanes`) that is not fully canceled is added to the authorship by
  SHA (`wp_attribution.lane_dependency_merges`), past the own-base bound, but only when an
  approval stamp of one of the lane's approved work packages reaches it: it was in a reviewed
  tip. Only the SHA: its blobs stay the dependency's, so the #5968 squash bound is unchanged.
- **A merge after the approval is not reviewed work (closed in review).** The approved bound
  (#5668) skips merge commits, so a dependency merge made after the approval, with content
  folded in, would have shipped unreviewed under the SHA exemption. Every merge on an approved
  code lane's spine that no approval stamp reaches is left out of that lane's authorship
  (`reconciliation._drop_unreviewed_merges`), for the SHA, patch-id and blob axes alike. The
  verifier then judges it by its remerge-diff: a clean one carries nothing, one with its own
  content FAILs, under merge, rebase and squash. A canceled WP's stamp never counts.
- **Still refused.** A merge with a resolution of its own that is not a lane's own dependency
  merge, and any foreign commit, stay un-attributable and FAIL.
- **Fail-closed.** `--remerge-diff` needs git 2.36 or newer. An older or unreadable git, or a
  `git show` error, raises `GitProbeError` and the gate REFUSEs, as the squash axis does on git
  older than 2.38.
- **Unchanged.** The approved bound (#5668) already drops merge commits; the mixed-lane work
  windows already skip merges; the canceled-content axes are not touched.

## Amendment 2026-11-08: work-package windows are recorded at the opening transition (#7403)

Work-package windows are recorded at the opening transition, and on `--resume` one frozen
claim-time anchor set feeds the closed-world anchors; see
`2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition`. The lane anchor
(`first_governed_open_stamp`, where `blocked` counts as an opener) stays as a named window
variant there, so no closed-world verdict changes through the window model itself.

## Amendment 2026-11-12: history from before the Mission is not Mission work (#7560)

**Context.** Every reconciliation window starts at the window base, the target's tip before
the run. On a fork, the local target can lack the commit the Mission branch was cut from: the
Mission started from an upstream pin plus a fork overlay, or from a `--pr-bound` start branch
the target never received. The history between the target and that commit then sat inside
every window. In the first report, a lane merged an upstream commit `U`; `consolidate --strategy
merge --dependency-ref U` refused with `DEPENDENCY_REF_COVERS_MISSION_WORK`, because the
missing upstream history sat on the Mission branch's first-parent spine. In the second report,
no lane merged anything: a plain run reported that history as un-attributable content and
deletions, and a declared run named the Mission base's own parent as Mission work.

**Decision.** History from before the Mission was created is not Mission work, on every
window axis (operator rulings, Decision Moments `01M78XBQS8NE8PPMSTZHMDJ610`,
`01M78XBWYTWJ6TZJVF4GWQMCQF` and `01M78XC2CJVH9ZXR0WB92NWYG5`).

- **The Mission base** is the commit the Mission branch was cut from
  (`consolidation/mission_base.py::resolve_mission_base`). It is not the claim base and not a
  lane creation base. It is resolved in a fixed order:
  1. **Recorded.** `meta.json` `mission_base_sha`, written once where the Mission branch is
     created: the topic or protected mint, and the coordination-branch create (a reused
     coordination branch records nothing). It is used only when it is a full lowercase object
     id (40 or 64 hex characters) equal to what `rev-parse --verify <value>^{commit}` prints,
     so a branch name, `HEAD`, a short sha or a tag object is never a recorded base; when it
     names a commit in this clone that is an ancestor of, or equal to, the Mission's *origin*
     (the first parent of the commit the derivation below finds), so neither a Mission commit
     nor a side branch merged into the Mission branch after it started qualifies, and without
     an origin the value is not used; and
     when the Mission directory is not reachable from it (`git log -1 --full-history <base> --
     kitty-specs/<slug>/` is empty), because a base the Mission directory is reachable from
     sits at or above the Mission's start. A value that fails a check is ignored, with its
     reason, and the derivation runs. Beyond those checks the value is trusted as tool-written.
  2. **Derived**, for a Mission without a usable recorded value: the first parent of the
     earliest commit on the Mission branch's first-parent history that adds a file under
     `kitty-specs/<slug>/`, checked the same way (on the branch, Mission directory not
     reachable). When that commit brought the directory in by
     a rename git detects (`git mv kitty-specs/<old> kitty-specs/<slug>`), its parent can sit
     above work done under the old name, so the base is unavailable instead.
     A derived base is reported (note line, provenance) but exempts nothing: it is the first
     parent of the first scaffold commit, not the cut point, so a code commit made on the Mission
     branch before the scaffold sits in `window_base..base` and topology cannot tell it from
     fork history. Exempting it would pass Mission-authored content as pre-Mission (fail-open).
     A Mission created before the base was recorded opts in by recording `mission_base_sha` in
     its `meta.json` (validated like any recorded base).
  3. **Unavailable.** No base, and today's bound applies: the window base alone. A git probe
     failure lands here too; a base is never guessed.
- **Pre-Mission history** is `rev-list window_base..mission_base` for a **recorded** base
  (empty for a derived or unavailable one). It is empty whenever the
  target already reaches the Mission base, which is the ordinary case, so every existing
  verdict is unchanged there. A range that holds a `lane_head` stamp any work package of the
  Mission recorded, or a recorded lane work tip in the Mission's branch namespace, holds
  Mission work: the base sits above the Mission's start, so the whole range is dropped and the
  base is unavailable (an unreadable status log or lane-tip listing does the same).
- **Where it counts.** Pre-Mission history has the standing of content already on the target:
  - the closed-world scan (fresh run, gate and `--dry-run`) exempts its commits by exact SHA,
    and so does the patch-id window of the excluded-commit check (a canceled work package's
    commit reaching the target under a new SHA): a pre-Mission commit's patch-id no longer
    counts there;
  - the squash blob and deletion axes exempt its exact final `(path, blob)` pairs and the
    paths it last deleted, for the paths the pre-Mission range touched, read from the Mission base's own tree;
  - the #6771 declaration guard leaves its commits out of the Mission-spine walk and the
    recorded-tip walk, so a fork's pin can be declared.
- **Unchanged.** A declared ref's own window stays `window_base..ref`; it is not cut at the
  Mission base. The approved bound (#5668) and the mixed-lane canceled-content axes (per-path
  state and line attribution, #6309) do not read the Mission base. Everything the Mission
  authored or carried after its base (commits on the Mission branch, lane spines,
  `lane_head` stamps, recorded lane tips) refuses exactly as before. No refusal code is added
  or changed. The protected single_branch authorship window
  (`lanes/single_branch_landing.py::authorship_window`, `merge-base(target, mission_branch)`) is
  a second, older Mission-start resolver and is left as it is: it only widens which first-parent
  commits count as the lane's own authorship (a fork's pre-Mission history can read as lane
  authorship there, never as exempt content), it takes no `meta.json`, and the mint records the
  target's tip as the base, which is that merge-base unless the target has moved on since. A
  known residual, not a second exemption; routing it through `resolve_mission_base` is follow-up
  work.
- **Resolved per claim build.** The base is resolved each time the claim is built (the claim
  and the gate's rebuild), with no new consolidation record field. It is not frozen with the
  claim-time anchors because each input is stable for the run: the recorded value is write-once
  in `meta.json`, and its validation reads the Mission branch's first-parent history at and
  below the scaffold commit, which a consolidation (it only adds commits above the lanes' work)
  and a rollback (it restores to a recorded tip) leave as they are. The range is anchored to the
  window base, which the record persists. In the recorded case one
  resolution and its range cost six git calls; a non-empty range adds one status-log read and
  one lane-tip listing.
- **Note line.** A run and `--dry-run` print one note (never under `--json`) when pre-Mission
  history is non-empty, naming the base, its provenance and the commit count, or when the base
  is unavailable, naming the reason. A probe failure is shown as "a git probe failed", without
  git's own output. The note is silent when the Mission branch itself does not resolve. The
  note decides on the base's typed reason (`MissionBaseReason`), never on the reason's text.

**Consequences.**

- On a fork, content that predates the Mission lands without a work package attributing it.
  That is the operator ruling: it was never Mission work.
- It fails closed. An unavailable base, or a probe failure while reading pre-Mission history,
  exempts nothing and leaves today's bound in force.
- A derived base reads history the operator can edit. Changing that history is a recorded
  operator act, as with the declared ref.

**Residuals.**

- The derivation follows git's rename detection only (`kernel.git`, git's default rename
  limit). A hand copy that keeps its source, a move edited past git's 50% similarity
  threshold, a rename inside a commit with more candidate paths than the rename limit, and a
  copy whose source is deleted in a later commit are not detected. The derived base can then sit above earlier Mission work,
  which takes an operator act to arrange. A recorded base is unaffected.
- A hand-edited recorded base is anchored to the Mission's origin, so it can only name history
  the Mission started from. It inherits the derivation's residuals above: where the origin
  itself sits above earlier Mission work, so can a recorded base. The guard against Mission
  work in the pre-Mission range reads recorded facts only (stamps and lane work tips).
- A rebased Mission branch whose first-parent history no longer carries the scaffold commit
  derives no base and falls back to today's bound.
- The exemption is by exact SHA, so a re-lettered copy of a pre-Mission commit (a new SHA with
  the same patch, for example after a rebase) is still judged as window content. This is
  fail-closed.
