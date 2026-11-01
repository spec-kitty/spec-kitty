---
title: 'ADR: a work package leaves review or approval only through a verdict or a noted force'
description: 'The transition pipeline refuses a forced exit from in_review or approved that carries no verdict and no note, on every surface; migration actors are exempt.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-10-07'
updated: '2026-10-07'
---

**Status:** Accepted

**Date:** 2026-10-07

**Deciders:** Stijn Dejongh (repository owner).

**Technical Story:** #5446 (`agent action implement` pulled a work package out of review with exit 0 and a made-up reason); the forced-approval restamp narrowing is #5721. Related: #5340, #5668, ADR [2026-10-04-5](2026-10-04-5-approval-stamp-bounds-the-approved-claim.md).

**Reader:** a maintainer changing the status transition pipeline, a transition surface (`move-task`, `agent status emit`, `orchestrator-api transition`, `agent action implement`) or the review-state readers.

---

## Context and Problem Statement

A work package in `in_review` or `approved` holds a reviewer's claim or verdict. Before this change, `agent action implement <WP> --agent <other>` force-moved such a package to `in_progress` for any agent, with the reason "Re-implementing after review feedback". Nothing in that event was a review outcome. The first fix guarded only the `implement` path, so `move-task --force`, `agent status emit --force` and the `orchestrator-api` transition verbs could still take a package out of review with no verdict and no explanation. `move-task` also minted a `changes_requested` review result for any `in_review` exit that was not an approval, so a forced `--to blocked` carried a verdict nobody gave.

## Decision

1. **One rule, in the one pipeline.** `status/transition_pipeline.prepare_transition` refuses a transition when all of these hold: it is forced, its from-lane is `in_review` or `approved`, it carries no `review_result`, and its reason is blank. The refusal is a `TransitionError` that names `FORCE_NOTE_REQUIRED` and `FORCE_NOTE_HINT`. The FSM already requires a non-blank reason for any force (`WPState._check_force`), so on `agent status emit` and `orchestrator-api` a bare force was already refused with a generic message; the leak was `move-task`, which filled the reason (`Force move to <lane>`) and, for an `in_review` exit, a `changes_requested` verdict itself. The pipeline rule gives the exit its own named refusal and no longer lets a synthesized reason stand for a note. The pipeline stays git-free, so every surface that emits a transition gets the rule and renders the refusal in its own shape (exit 1 for `move-task` and `agent status emit`, a `TRANSITION_REJECTED` envelope for `orchestrator-api`).
2. **A verdict is the only other way out.** A transition that records a `review_result` is the verdict and needs no note. `move-task` mints a rejection result only for the rework edges (`-> planned`, `-> in_progress`), never for another exit, and it passes a bare `--force` out of those lanes to the pipeline with no reason, so the pipeline sees what the operator actually supplied.
3. **Migration actors are exempt.** An actor starting with `migration:` (`MIGRATION_ACTOR_PREFIX`, now defined in `status` and imported by the consolidation attribution code) reconstructs state; it is not an operator act.
4. **Implementer-of-record withdrawal stays on the `implement` path.** Only the work package's implementer of record may withdraw an unclaimed `for_review` submission, and that check needs the event log, the caller's actor and the claim holder, so it remains in `status/work_package_lifecycle.py` (`_review_lane_exit_reason`). `for_review` is not a verdict-gated lane, so the pipeline rule does not apply to it. An unforced `implement` on `in_review` or `approved` is still refused there as a claim conflict naming the reviewer, or with the rework route.
5. **A cleared review-result slot is "no verdict on record".** The reducer writes `review_result: null` when a package leaves `in_review` with no verdict. `ReviewResultLookup.cleared_without_verdict` is true only for that raw `None`; the readers treat it like an absent slot, so the next review approves normally. A malformed value (not an object, or an object that does not parse) keeps failing closed with a message that names a route that works.
6. **A forced approval is a review only when a review backs it (#5721).** A forced move into `approved` restamps the consolidation bound only as an approved-reviewed attestation, an arbiter override, or a hop out of `in_review` that carries an approved `review_result` after an unforced move into `in_review`. Two routes into that set stay open, both recorded operator acts: moving the package unforced into `in_review` and then forcing it to `approved` with a synthesized approved result, and a reject followed by a forced arbiter-override approval.

## Considered Options

1. **Pipeline rule (chosen).** One place, one refusal, every surface.
2. **Per-surface checks.** Rejected: that is how `implement` was fixed first and the other three surfaces stayed open.
3. **Refuse every forced exit from review.** Rejected: an operator with a real reason (an unavailable reviewer, a damaged claim) needs the override; the note makes it auditable.
4. **Move the implementer-of-record check into the pipeline as well.** Rejected: it needs implement-path context, and the pipeline reads no log.

## Consequences

- `move-task <WP> --to <lane> --force` out of `in_review` or `approved` needs `--note`; `agent status emit` needs `--reason`; `orchestrator-api transition` needs `--note`. Without it nothing is written.
- A forced `approved -> done` is also a forced exit from `approved` and needs a note.
- An unforced `move-task` out of `in_review` to a lane other than `planned`, `in_progress` or an approval no longer gets a minted `changes_requested` result; the FSM refuses it for want of a review result, and the route is `--force --note`.
- The rule judges the request, not the log: a reason of any non-blank text satisfies it. The note is evidence for the audit trail, not a check that the reason is true.
- Reversible only by a new decision; the cross-surface test in `tests/specify_cli/cli/commands/agent/test_approval_after_forced_review_exit.py` fails when any surface bypasses the pipeline rule.
