---
title: WP Lifecycle State Machine
description: Introduced a guarded lane transition matrix with claimed, blocked, and canceled states so concurrent agents could not jump straight from planned to done.
status: Superseded
date: '2026-02-09'
doc_status: superseded
kind: ADR
updated: '2026-02-09T00:00:00Z'
---

> Superseded by `2026-04-03-2-review-approval-and-integration-completion-are-distinct.md`,
> which is itself partially superseded by `2026-04-06-1-wp-state-pattern-for-lane-behavior.md`.
> `2026-04-06-1` is the current authority for the full 9-lane state machine.
>
> This ADR encoded a 7-lane model with `for_review -> done` as reviewer approval.
> The current lifecycle separates reviewer approval (`approved`) from integrated
> completion (`done`), promotes `in_review` to a first-class 9th lane, and
> encapsulates all lane behavior in the `WPState` ABC.

## Context and Problem Statement

The current WP lifecycle uses an implicit 4-lane model (`planned`, `doing`, `for_review`, `done`) with no formal transition validation or guard conditions. Any lane can be written directly, enabling invalid jumps (e.g., `planned` → `done` without review). There is no blocked or canceled state, no ownership tracking beyond "doing", and no forced-transition audit trail.

The state machine operates on events from the canonical append-only event log defined in ADR 2026-02-09-1. Each state transition corresponds to an event appended to the log.

## Decision Drivers

* **Multi-agent conflict prevention** — Multiple agents claiming or working the same WP must be detected
* **Review authority** — Reviewer rollback must be enforceable, not silently overridden
* **Blocked work visibility** — Stalled work must be surfaced, not hidden in "doing"
* **Evidence-based transitions** — Guard conditions must enforce proof at each transition
* **Deterministic replay** — A fixed state machine enables automated merge validation

## Considered Options

* **Option 1:** Keep current 4-lane model with added validation
* **Option 2:** 7-lane state machine with strict transition matrix
* **Option 3:** Full kanban with unlimited custom columns
* **Option 4:** Simple binary (open/closed) with tags

## Decision Outcome

**Chosen option:** "Option 2: 7-lane state machine with strict transition matrix", because it adds explicit ownership tracking (`claimed`), blocked work visibility (`blocked`), clean lifecycle termination (`canceled`), and mandatory guard conditions — all required for safe concurrent multi-agent work.

### Implementation

**Lanes:** `planned` → `claimed` → `in_progress` → `for_review` → `done` (plus `blocked` and `canceled`)

**Allowed transitions (9 total):**
1. `planned → claimed` — Agent declares intent to work
2. `claimed → in_progress` — Work actively begins (workspace context established)
3. `in_progress → for_review` — Implementation complete, submitted for review
4. `for_review → done` — Reviewer approves (terminal)
5. `for_review → in_progress` — Changes requested by reviewer
6. `in_progress → planned` — Abandon/reassign (mandatory reason)
7. `any → blocked` — External blocker identified
8. `blocked → in_progress` — Blocker resolved
9. `any (except done) → canceled` — WP abandoned or superseded (terminal)

**Guard conditions (6):**
1. `planned → claimed`: Assignee must be set; no conflicting active claim
2. `claimed → in_progress`: Active workspace context must be established
3. `in_progress → for_review`: Required subtasks complete OR force flag with reason
4. `for_review → done`: Reviewer identity and approval evidence required (per ADR 2026-02-09-4)
5. `for_review → in_progress`: Review feedback reference required
6. Any forced transition: Actor identity and reason are mandatory

### Consequences

#### Positive

* Explicit ownership tracking — `claimed` prevents phantom progress and concurrent claim conflicts
* Blocked state surfaces stalled work — no more hidden "doing" with no progress
* Guard conditions enforce evidence at every transition
* Forced transitions are always auditable (actor + reason recorded)
* Terminal `done` prevents accidental regression
* Deterministic replay — fixed state machine enables merge validation (ADR 2026-02-09-3)

#### Negative

* More states = more complexity (7 lanes, 9 transitions vs 4 lanes, ~4 transitions)
* Migration required for existing WPs (`doing` → `in_progress`)
* Guard conditions add friction to rapid prototyping
* Learning curve for new contributors

#### Neutral

* Force-with-reason escape valve allows legitimate overrides while maintaining audit trail
* `status doctor` command provides automated detection of stale claims and orphan contexts

### Confirmation

* CI validation: every merge triggers a transition validity scan against the state machine
* Migration: `doing` maps to `in_progress`; other lanes map 1:1
* Operational playbooks (PRD Section 13) cover common scenarios

## Pros and Cons of the Options

### Keep current 4-lane model with added validation

Retain `planned`, `doing`, `for_review`, `done` but add transition validation.

**Pros:**

* No migration required
* Simpler mental model — fewer states
* Backward-compatible with all existing tooling

**Cons:**

* Cannot distinguish `claimed` from active work — phantom ownership undetectable
* Cannot represent `blocked` — stalled work invisible
* Cannot represent `canceled` — abandoned WPs linger indefinitely
* Weaker guard conditions (no workspace context check, no claim uniqueness)

### Full kanban with unlimited custom columns

Allow projects to define arbitrary lane names and transition rules.

**Pros:**

* Maximum flexibility — teams define their own workflow
* Supports domain-specific states (e.g., "testing", "staging", "deployed")

**Cons:**

* No standard transition validation possible
* Complexity explosion — custom lanes require custom guards, merge semantics, CI rules
* Deterministic merge requires a known, fixed state machine
* Interoperability between projects breaks if lane names differ

### Simple binary (open/closed) with tags

Two states (`open`/`closed`) with free-form tags for substates.

**Pros:**

* Minimal state machine — only one transition to validate
* Tags provide flexibility without schema changes

**Cons:**

* No transition validation — tags are unstructured
* Tags don't compose into deterministic state
* Merge semantics for tag sets are undefined

## More Information

**Related ADRs:**
* ADR 2026-02-09-1 (Canonical WP Status Model) — state machine consumes events from this log
* ADR 2026-02-09-3 (Event-Log Merge Semantics) — replays events through this state machine
* ADR 2026-02-09-4 (Cross-Repo Evidence Completion) — evidence payloads satisfy guard conditions

**References:**
* Harel Statecharts — https://www.wisdom.weizmann.ac.il/~dharel/SCANNED.PAPERS/Statecharts.pdf
* XState Documentation — https://xstate.js.org/docs/
* PRD: Feature Status State Model Remediation (Sections 7, 8, 13, 14)
