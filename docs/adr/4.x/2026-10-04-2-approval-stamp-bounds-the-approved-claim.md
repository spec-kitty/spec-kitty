---
title: 'ADR: the approval stamp bounds what consolidate treats as approved work'
description: 'Consolidate refuses a code lane holding a commit made after its work package was approved; an approval with no stamp refuses until re-reviewed or attested.'
status: Accepted
date: '2026-10-04'
updated: '2026-10-05'
---

**Status:** Accepted

**Date:** 2026-10-04

**Deciders:** Stijn Dejongh (owner). The operator brief for issue #5668 settled the refusal, the attestation and the scope.

**Technical Story:** [#5668](https://github.com/spec-kitty/spec-kitty/issues/5668), Mission `approved-claim-bound-01M444QR`. Reverses two earlier decisions, named under Decision. Related: [#5046](https://github.com/spec-kitty/spec-kitty/issues/5046) and ADR [2026-09-29-1](../3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md).

**Reader:** a maintainer who needs to know why `spec-kitty consolidate` refuses with `LANE_MOVED_AFTER_APPROVAL`, `APPROVAL_STAMP_MISSING` or `APPROVAL_STAMP_NOT_ON_LANE`, and what the rule does not cover. An operator who is looking at one of those refusals should start from the recovery command in the message, and from the changelog entry for #5668.

---

## Context and Problem Statement

`spec-kitty consolidate` landed commits that were made on a lane after the lane's work package was approved, and it printed "Reconciliation verified". Nobody had reviewed those commits.

The issue's reproducer was run before the fix in four combinations: the `lanes` topology and a coordination topology, each with the default squash strategy and with `--strategy merge`. All four exited 0, put the late file on the target and printed the banner.

The cause is how the approved claim is built. The claim builder asks the status snapshot only whether a work package is `approved` or `done`. It then reads the commits of the lane branch as they are at that moment, and treats all of them as approved authorship. The recorded decision was: approved commit SHAs come from lane-branch git tips, never from status rows. A commit added after approval is therefore approved on every axis the reconciliation gate checks.

The information needed to tell the two apart was already recorded. Since 4.0.0rc5 every persisted transition of a lane-mapped work package carries the lane head in `policy_metadata.lane_head`. On the `approved` transition that value is the commit review saw. In the reproducer, WP01's `approved` event named `d0d8b2c6` and the lane tip was `8fc7fb8c`, one commit later. No consumer read the stamp for this purpose.

The closed-world check from ADR 2026-09-29-1 did not catch it either. It runs only on a lane that mixes an approved and a canceled work package, and it returns early for every other lane.

## Decision

**The approval stamp is the one reference for what review approved. A code lane that holds a commit after its approval stamps is refused, and so is an approval that has no stamp.**

### What the stamp is

- The approval stamp is `policy_metadata.lane_head` on a work package's latest non-migration approval event. An approval event is an `approved` transition, or an operator attestation of an approval (see Attestation).
- The `approved -> done` transition is never read. The consolidation records it before the gate, stamped with the tip that is about to land, so reading it would make the landed tip its own bound.
- One reader resolves the stamp: `approval_stamp` in `src/specify_cli/consolidation/approved_bound.py`. It uses the stamp reader that already served canceled work packages, `stamp_of` in `consolidation/wp_attribution.py`. The status package stays free of git access.
- An approval recorded by a release before 4.0.0rc5 carries no stamp.

### The lane check

`approved_bound.check_lane` applies to every code lane that has an approved work package in the claim and is not fully canceled. The commits it examines are those reachable from the lane tip and from none of the covered points. The covered points are:

- the approval stamps of the lane's approved work packages;
- on a mixed lane, the newest stamped event of each canceled work package.

Commits reachable from the claim base or from an anchor are not examined. Merge commits are dropped. Commits that touch only bookkeeping paths are dropped, using the gate's existing definition (`_is_bookkeeping`), so there is one definition. Any other commit that is left refuses with `LANE_MOVED_AFTER_APPROVAL`, naming the lane, the approved work packages, up to three short SHAs and one path.

The walk covers the full commit range, not the first-parent spine. A late commit that arrives through a merge from a branch that is not an anchor is found.

The claim base is the target branch's tip as it was before the run mutated anything; on a resume it is the persisted value. When that value does not resolve, the claim base is the coordination base. `check_lane` itself raises when the claim base or the lane tip does not resolve, and every caller turns that into a refusal; only the claim builder keeps its older tolerance of an unresolvable coordination base, which reads as an empty lane. Anchors are:

- the dependency-lane tips of lanes that are not fully canceled;
- the target's pre-consolidation tip;
- every bounded lane's approval stamps.

Because every bounded lane's approval stamps are anchors, a commit that review approved as part of another lane is not refused on the lane it was first made on. Example: a commit is added to lane A after WP01 was approved. Lane B merges lane A. WP02 on lane B is sent back, reworked and approved again, so its new approval stamp reaches that commit. Lane A is then no longer refused: the commit is inside what review approved for lane B. The dependency-lane tip anchor has the same property for a lane that depends on lane A; lane A itself is still checked against its own stamps in the same run. This is deliberate. Content inside an approval stamp was in a reviewed tip, and the tool's own merge of the mission branch into a stale lane brings in other lanes' reviewed commits, which must not refuse. It also means a fresh run can give a different verdict than the first implementation of this rule did.

The live mission branch is not a reference. An earlier version used it as an anchor. A post-approval commit that had already been merged into the mission branch, for example after an interrupted run that was resumed, then passed. That was found in review and fixed before release.

Two more refusals come from the same check:

- `APPROVAL_STAMP_MISSING`: an approved work package in the claim has no approval stamp. The stamp is never replaced by the lane tip. There is no fallback, in product code or behind a test switch.
- `APPROVAL_STAMP_NOT_ON_LANE`: an approval stamp is neither the lane tip nor one of its ancestors. The lane was rewritten after approval.

A lane with no commit beyond the claim base is not checked, because nothing can land from it. A `done` work package with no `approved` event on such a lane is therefore not refused. This differs from the letter of the Mission's FR-005 and is deliberate.

A commit added to a lane after that lane was already consolidated is also refused, although it never landed. The check cannot tell the two cases apart from the lane alone, and refusing is the safe reading.

### Where it runs

| Entry point | When | Result |
|---|---|---|
| `spec-kitty consolidate` | At claim time, before the pre-mutation snapshot | Exit 1 under the existing claim-time refusal header. No branch or worktree has moved, so there is nothing to roll back. An attestation requested on the same command is already recorded in the status log. |
| `spec-kitty consolidate` | At the reconciliation gate, before "Reconciliation verified" can print | Compares each live lane tip with the tip validated at claim time. The references are the lane tips validated at claim time, plus the mission branch, the target and the coordination base as resolved at claim time. A refusal rolls back through the existing rollback authority. No new restore path exists. |
| `spec-kitty orchestrator-api consolidate-mission` | Before its first lane is consolidated | `PREFLIGHT_FAILED` envelope; the code is in `data.preflight_error_code`. Contract version 1.10.0. This path has no gate re-check because it has no rollback door. |

What the gate re-check adds is narrower than it might look. A commit added to a lane during a run was already failed by the existing content checks as un-attributable, and rolled back, in the plain case. There the re-check replaces a generic failure with the named refusal: the commit, the work package and the remedy. The case it closes is a mission with no coordination branch. There, a late commit on one lane that writes another lane's approved content (same path, identical blob) passed the old gate with exit 0 and the banner.

The re-check never uses a live branch name as a reference. Lanes are consolidated into the mission branch with a no-ff merge, so at gate time the live mission branch reaches every consolidated lane commit. A check against it would pass vacuously.

### Attestation

`spec-kitty consolidate --attest-approved-reviewed <WP> --attest-reason "<why>"` lets an operator who has checked a lane by hand bound an unstamped approval.

- It records a forced operator self-transition in the status log, with `policy_metadata.attestation = "approved_reviewed"`. The lane head at that moment becomes the bound.
- It is accepted only for a work package in the approved claim whose newest approval is not a stamped review approval: an approval with no stamp, or an earlier attestation (see the repeat rule below).
- It never lifts `LANE_MOVED_AFTER_APPROVAL`. A commit made after an attestation is refused like any other post-approval commit, and the only way to approve content is review.
- A repeat attestation is accepted, and recorded again, only while the lane has not moved past the earlier one. Otherwise it is refused and nothing is recorded.
- It is not a review. The hollow-review warning never reads it as the approving review, so it cannot satisfy the independent-review check. It is a forced transition and each attestation adds one to the work package's forced-transition count, which that warning counts, so an attestation can itself bring a work package to the count at which the warning prints.

### Operator guidance

Each refusal prints one short line per refused lane or work package, then one recovery block. The commands in it carry the Mission slug and run as printed. The text names the approval stamp once, as the lane commit recorded when review approved the work package.

- For `LANE_MOVED_AFTER_APPROVAL` the text names up to three late commits and says to see a commit with `git show <sha>`. The recovery is `spec-kitty agent tasks move-task <WP> --to in_progress --mission <slug>` for each work package of the lane, then rework, review and approve again.
- For `APPROVAL_STAMP_NOT_ON_LANE` the recovery is the same move-back command.
- For `APPROVAL_STAMP_MISSING` the text prints one `spec-kitty consolidate --mission <slug> --attest-approved-reviewed <WP> ... --attest-reason "<what you checked>"` command that lists every unstamped work package, and the move-back command for each of them.
- A fix committed to a lane after approval, including a fix folded in after a late review, needs the work package approved again. The refusal does not distinguish a fix from any other late commit.
- `orchestrator-api consolidate-mission` prints the same text and adds that it has no attestation flag: attestation is done with `spec-kitty consolidate` (CLI only).
- `spec-kitty agent tasks move-task` and `spec-kitty agent status emit` print a one-line warning on stderr when an approval was persisted with no stamp for a work package of a code lane, so the operator learns it at approval time and not at `consolidate`. The status pipeline stays free of git access; the shells read the persisted event.

### Mixed lanes

The closed-world refusals of ADR 2026-09-29-1 keep their precedence, codes and texts on a mixed lane. When none of them fires, the bound check still applies, with the canceled work package's newest stamped event as a covered point. An unstamped canceled attestation gives no covered point.

### Reversed decisions

1. **The claim builder's rule that approved commit SHAs come from lane-branch git tips, never status rows.** The commits are still read from git. A status row, the approval stamp, now decides which of them are approved work.
2. **Decision 1 of ADR 2026-09-29-1, "applies only to mixed lanes".** The closed-world check itself still applies only to mixed lanes. What changes is the premise that a lane that is not mixed needs no bound. Every code lane with an approved work package is now bounded. A short dated pointer to this ADR has been added to that ADR.

### Evidence

The reproducer from the issue was run after the fix in the same four combinations. All four refuse at claim time with `LANE_MOVED_AFTER_APPROVAL`, print no banner and leave the late file off the target.

## Considered Options

1. **Land the approved stamp and drop the later commit.** Rejected. Dropping a commit silently hides work from its author, and no other gate verdict does that. Merging the stamp instead of the branch name would also change the physical consolidation for every mission and discard the tool-made merges a lane needs.
2. **Require the lane tip to equal the stamp.** Rejected. It refuses every lane with more than one work package and every resume.
3. **Require tree or blob equality between the lane and the stamp.** Rejected. It refuses any overlapped automatic merge, the "blob equal to neither parent" class already known from #5013.
4. **Put the reader in the status package.** Rejected. The ancestry check needs git, and the status package stays git-free.
5. **Extend the canceled work package resolver.** Rejected. It is scoped to one canceled work package on one mixed lane, and extending it would push it past the complexity ceiling.
6. **Per-work-package windows on every lane (the closed world everywhere).** Deferred. It brings every closed-world anchor hazard to missions with no canceled work package, with unknown real refusals. It would close the first residual below.
7. **Treat a missing stamp as the lane tip.** Rejected. It is fail-open, and it would keep the defect for every mission approved before the stamp existed.
8. **Compare the `done` event's landed-tip stamp with the bound at the gate.** Rejected. It adds a second reader of a different stamp.
9. **Re-run the claim-time check at the gate with live branch names.** Rejected. It passes vacuously, as described above.
10. **Reuse `--attest-canceled-superseded` for approvals.** Rejected. It requires a canceled work package. Storing the attestation outside the status log would create a second authority.
11. **Route the orchestrator code-lane path through the executor.** Out of scope. It is a larger behaviour change with its own rollback questions.

## Consequences

- A post-approval commit goes back for review before it can land. `consolidate` names the commit, the work package and the recovery command, and leaves the target unchanged.
- **Upgrade impact.** A Mission approved by a release before 4.0.0rc5 has no stamps. Its `consolidate` refuses with `APPROVAL_STAMP_MISSING` until each work package is re-reviewed or attested.
- A claim reads the status event log once, now also for a mission that has no mixed lane. An unreadable log refuses.
- Existing refusal codes and texts are unchanged. The three new codes and texts are additions.
- The orchestrator API contract version is 1.10.0, and `data.preflight_error_code` is new on its `PREFLIGHT_FAILED` envelope.
- A fixture-honesty change came with the rule: the shared consolidation fixtures now record approvals after the lane work exists, with real stamps, so the suite can express "after approval".

### Residuals

Each stays open.

- **A commit between two approvals on one lane.** A commit made after WP01's approval and before WP02 is claimed sits under WP02's later bound. Closing it needs per-work-package windows on every lane.
- **Content inside a merge commit.** A merge commit that carries new content of its own is not seen. It is pinned as a strict expected-failure test.
- **A commit made during review.** The stamp is the lane head when the approval was recorded, not the commit the reviewer read.
- **Planning lanes and `single_branch` missions.** They are not stamped and not bounded.
- **The width of the bookkeeping definition.** It covers the repository's `.kittify/` tree and any `kitty-specs/<slug>/` path segment. A post-approval commit confined to those paths is not refused. The bound reuses the gate's definition so there is one authority; narrowing it is a separate change to the existing content checks.
- **`consolidate --dry-run`.** It does not report the new refusals.
- **`orchestrator-api consolidate-mission` has only the up-front check.** A commit hand-merged into the mission branch with the lane reset to its stamp, or a commit that lands between its check and its lane consolidation, is not caught there. `consolidate` fails both.
- **A forced re-approval restamps the lane.** An `approved -> approved` transition forced by anyone records a new approval stamp at the current lane head. The bound is as strong as the review model: the transition is a recorded forced event, and no warning is printed for it today.
- **An approval recorded while the lane branch is missing has no stamp.** It can then be attested, which leaves two recorded operator acts in the log.
- **A repeat attestation on a resume.** If the target already advanced, the repeat attestation measures from the live target tip. The claim check still refuses afterwards.
