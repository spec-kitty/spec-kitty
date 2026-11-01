---
title: Review Approval and Integration Completion Are Distinct
description: 'Splits reviewer sign-off from completion by adding an approved lane, so done means integrated with acceptance evidence recorded, not merely reviewed.'
status: Superseded
doc_status: superseded
kind: ADR
date: '2026-04-03'
---

> **Partial supersession (2026-04-06):** The core decision of this ADR — adding an explicit `approved` lane and separating reviewer approval from integration-complete — remains in force. However, the `in_review` lane promotion section is superseded by `2026-04-06-1-wp-state-pattern-for-lane-behavior.md`, which promotes `in_review` from an alias for `for_review` to a first-class 9th lane with its own concrete `WPState` class and conflict-detection guard. The transition model in the *Decision Outcome* section below reflects the pre-`in_review`-promotion design; see `2026-04-06-1` for the current canonical transition set.

---

## Context and Problem Statement

Spec Kitty's current 2.x lifecycle model still encodes `for_review -> done` as
"reviewer approves". That makes `done` mean "review passed". But the newer
command/runtime direction and the actual product requirement are stricter:
`done` must mean "integrated and acceptance-complete", not merely "a reviewer
liked the branch diff".

This semantic gap produced contradictory behavior:

1. prompts and reviewers could treat approval as completion,
2. merge/integration logic needed `done` to mean the work was actually integrated,
3. feature acceptance could be declared complete while forbidden fallback paths
   still existed in the integrated product.

Feature `028-saas-active-projects-shell` exposed the consequence: work package
review was treated as effectively terminal even though the integrated feature
still violated the user journey.

## Decision Drivers

* **Semantic clarity** — `done` must have one meaning everywhere.
* **Review/integration separation** — reviewer approval and integrated feature
  completion are different events.
* **Merge safety** — the state model must not imply that branch-level review is
  equivalent to product-level completion.
* **Evidence alignment** — review evidence and integration evidence should not
  be conflated into one transition.
* **Command parity** — prompts, `next`, review flows, and merge guards must use
  the same lifecycle semantics.

## Considered Options

* **Option 1:** Keep `done` meaning "review approved" and encode integration elsewhere
* **Option 2:** Keep the 7-lane model but add extra completion metadata flags
* **Option 3:** Add an explicit `approved` lane before `done`

## Decision Outcome

**Chosen option: Option 3**, because the lifecycle needs an explicit state for
"review approved but not yet integration-complete".

### Core Decision

The canonical WP lanes become:

`planned -> claimed -> in_progress -> for_review -> approved -> done`

plus `blocked` and `canceled`.

### State Semantics

1. `for_review` means implementation is ready for reviewer inspection.
2. `approved` means reviewer approval has been granted for the current
   implementation.
3. `done` means the work is integrated into the mission integration branch and
   the required acceptance evidence has been recorded.

### Transition Model

At minimum, the following transitions are canonical:

1. `in_progress -> for_review` — implementation complete, evidence ready
2. `for_review -> approved` — reviewer approval
3. `for_review -> in_progress` — changes requested
4. `approved -> done` — integration-complete and accepted
5. `approved -> in_progress` — integration or acceptance uncovered required rework

### Evidence Split

Evidence requirements are split by transition:

1. `in_progress -> for_review` requires implementation evidence
   (artifacts/tests/verification needed for review).
2. `for_review -> approved` requires review evidence
   (reviewer identity, verdict, and reference).
3. `approved -> done` requires integration and acceptance evidence
   (mission-branch integration proof and acceptance proof).

No single event is allowed to claim both review approval and integration-complete
status unless the system can prove both happened in the same operation.

## Consequences

### Positive

* `done` now means one thing everywhere: integrated and accepted.
* Review approval becomes visible and auditable as its own state.
* Feature-level acceptance can fail after branch review without violating the
  lifecycle model.
* Evidence becomes easier to reason about because review evidence and acceptance
  evidence are attached to different transitions.

### Negative

* State-machine complexity increases from seven lanes to eight.
* Existing docs, prompts, guards, and tests that assume `for_review -> done`
  must be migrated.
* Historical tooling that equates "approved" with "done" needs explicit repair.

### Neutral

* The append-only event log remains the canonical state authority.
* Existing blocked/canceled semantics remain unchanged.

### Confirmation

This decision is validated when:

1. no prompt or command instructs `for_review -> done` as mere approval,
2. reviewer approval is represented as `approved`,
3. `done` transitions require integration/acceptance evidence,
4. integrated feature acceptance failures can reopen work from `approved`
   without breaking lifecycle semantics.

## Pros and Cons of the Options

### Option 1: Keep `done` meaning review-approved

Treat reviewer approval as completion and keep integration as a separate informal
concept.

**Pros:**

* No lane migration required.
* Existing tooling keeps working in the short term.

**Cons:**

* `done` continues to mean different things in different parts of the system.
* Review approval and integrated completion remain conflated.
* The Feature 028 acceptance failure class remains structurally possible.

### Option 2: Keep seven lanes, add metadata flags

Use side metadata to distinguish "approved" from "integrated".

**Pros:**

* Avoids introducing another visible lane.
* Smaller migration surface for UIs that render lane chips.

**Cons:**

* Hidden state is harder to reason about than explicit lanes.
* Merge and review semantics become harder to validate deterministically.
* Encourages drift between lane rendering and actual completion meaning.

### Option 3: Add explicit `approved` lane

Use a distinct lane for reviewer approval before final integrated completion.

**Pros:**

* Makes the lifecycle honest and explicit.
* Aligns prompts, guards, and acceptance behavior.
* Allows reviewer approval to be preserved even if integration acceptance fails.

**Cons:**

* Requires lane/state migration work.
* UIs and reports must learn one more visible state.

## More Information

**Supersedes:**
* `2026-02-09-2-wp-lifecycle-state-machine.md`
* `2026-02-09-4-cross-repo-evidence-completion.md`

**Partially superseded by:**
* `2026-04-06-1-wp-state-pattern-for-lane-behavior.md` — supersedes the `in_review`-as-alias approach; `in_review` is now a first-class lane

**Interprets alongside:**
* `2026-02-09-3-event-log-merge-semantics.md` — rollback-aware merge semantics
  remain in force, but reviewer-forward progress is now `for_review -> approved`
  rather than `for_review -> done`.
* `architecture/adrs/2026-03-09-1-prompts-do-not-discover-context-commands-do.md`

**Related ADRs:**
* `2026-04-03-1-execution-lanes-own-worktrees-and-mission-branches.md`
* `2026-04-03-3-feature-acceptance-runs-on-the-integrated-mission-branch.md`
