---
title: Event-Log Merge Semantics for Concurrent Agents
description: Reconciles divergent status logs by concatenating, deduplicating, and replaying events with rollback-aware precedence, so a reviewer's rejection is never overwritten.
status: Accepted
date: '2026-02-09'
---

## Context and Problem Statement

Multiple agents — human developers, AI agents (Claude, Codex), and CI systems — may concurrently modify WP status in different git branches. Each branch contains its own copy of the canonical event log (ADR 2026-02-09-1). When branches merge, the event logs must be reconciled into a single consistent state.

The current system has no formal merge semantics for status. A naive "most done wins" strategy can override a valid review rollback. For example: Branch A's reviewer moves a WP from `for_review` → `in_progress` (changes requested), while Branch B concurrently moves the same WP from `for_review` → `done`. Naive merge: "done" wins — **but the reviewer's rollback is lost**.

## Decision Drivers

* **Deterministic merge** — Same inputs must always produce the same merged state
* **Reviewer authority** — Review rollback must outrank concurrent forward progress
* **Invalid transition detection** — Post-merge validation must flag illegal state sequences
* **Agent-count agnostic** — Must scale from 2 branches to 20+
* **Audit trail preservation** — All events from all branches must be retained

## Considered Options

* **Option 1:** Last-writer-wins by timestamp
* **Option 2:** Monotonic "most-advanced-lane-wins"
* **Option 3:** Concatenate-dedupe-sort-reduce with rollback-aware precedence
* **Option 4:** Manual conflict resolution (human decides)

## Decision Outcome

**Chosen option:** "Option 3: Concatenate-dedupe-sort-reduce with rollback-aware precedence", because it provides deterministic merges, preserves reviewer authority, catches invalid transitions, and scales to any number of concurrent agents.

### Implementation

**4-step merge algorithm:**

1. **Concatenate**: Combine event logs from both branches into a single stream
2. **Deduplicate**: Remove duplicate events by `event_id` (same event from common ancestor appears in both)
3. **Sort**: Order by deterministic key — primary: `logical_clock` (Lamport), secondary: `at` (UTC timestamp), tertiary: `event_id` (ULID, lexicographic tiebreaker)
4. **Reduce**: Replay sorted events through the state machine (ADR 2026-02-09-2) to compute current state; invalid transitions are flagged

**Rollback-aware precedence:** An explicit reviewer rollback (`for_review → in_progress` with `review_ref` populated) outranks a concurrent forward progression (`for_review → done` without `review_ref`). This is a semantic rule: review feedback is authoritative.

**Invalid transition handling:** Events producing invalid transitions after merge are flagged as validation errors, reported in CI output, and never silently ignored.

**Explicit rejection:** The monotonic "most-advanced-lane-wins" strategy is explicitly rejected — PRD Section 2 identifies this as a failure mode, not a solution.

### Consequences

#### Positive

* Deterministic — same inputs always produce the same merged state, regardless of merge order
* Reviewer authority preserved — explicit rollback with `review_ref` outranks concurrent forward progress
* Invalid transitions caught — post-merge validation flags illegal state sequences in CI
* Scales to any number of agents — algorithm is agent-count-agnostic
* Audit trail preserved — all events from all branches retained in the merged log

#### Negative

* Algorithm complexity — concatenate-dedupe-sort-reduce is more complex than simple last-write-wins
* Requires sortable keys — all events must have logical clock or timestamp
* Post-merge validation adds CI time (linear in event count)
* Two conflicting forced transitions may still require manual resolution

#### Neutral

* Sort is O(n log n), reduce is O(n) — manageable for typical event log sizes (< 1000 events per feature)
* `status emit` ticks the logical clock on every event, so sortable keys are always present
* Manual fallback exists for truly unresolvable conflicts (the exception, not the rule)

### Confirmation

* CI check: every merge triggers transition validity scan against the state machine
* CI check: materialized state must match reducer output
* Edge case: conflicting forced transitions flag for human resolution

## Pros and Cons of the Options

### Last-writer-wins by timestamp

When events conflict, the event with the latest timestamp wins. No semantic awareness.

**Pros:**

* Simple to implement — compare timestamps, keep latest
* No need to understand event semantics
* Works for any event type without special cases

**Cons:**

* Timestamps can be skewed across machines (clock drift, timezone errors)
* Race conditions produce non-deterministic results
* No semantic awareness — review rollback and forward completion treated identically
* Reviewer authority lost when completion timestamp is later

### Monotonic "most-advanced-lane-wins"

The event moving the WP to a "more advanced" lane wins. Lane ordering: planned < claimed < in_progress < for_review < done.

**Pros:**

* Deterministic — lane ordering is fixed
* Matches intuition that work should move toward completion

**Cons:**

* **This IS the failure mode identified in PRD Section 2** — "monotonic conflict resolution: 'most done wins' can override valid review rollback"
* Destroys reviewer authority
* Hides regressions — quality issues surfaced in review are overwritten by forward progress
* Cannot represent legitimate state reversals

### Manual conflict resolution (human decides)

Present event log conflicts to a human for manual resolution, similar to git merge conflict markers.

**Pros:**

* Always correct when the human is attentive
* Handles edge cases no automated rule can cover
* Familiar pattern for developers

**Cons:**

* Blocks CI and automation — merge cannot complete without human intervention
* Doesn't scale to multi-agent workflows with frequent merges
* Requires human to understand event log semantics (high cognitive load)
* Introduces delays in integration velocity

## Reconciliation note — terminus merge/reconciliation gate (terminus-merge-integrity, 2026-09)

The terminus reconciliation gate (`merge/reconciliation.py::MergeOutcomeVerifier` / `build_approved_wp_set`, mission *terminus-merge-integrity*) sources its approved/canceled **WP-membership** claim through the **Lamport** reduction wrapper this ADR mandates (`status.reducer.materialize` / `reduce_shared_state`, `status/reducer.py:371`) — never the wall-clock LWW `reduce_parsed`. This is what makes the gate's own claim honor the reviewer-authority / causal-precedence guarantee above: a wall-clock-later approval cannot green-wash a causally-earlier committed rejection *in the gate's claim*.

This ADR's chosen algorithm (Option 3, Lamport-primary) is therefore honored by the **Lamport** reducer only. A **second**, non-conformant reducer still ships in the codebase — the wall-clock LWW `reduce_parsed` (`spec_kitty_events.diary`, sorts `(at, event_id)`) — and its split-brain (a later wall-clock event overriding a causally-earlier one, exactly the "Last-writer-wins by timestamp" failure mode this ADR **rejected**) is **not** resolved by the terminus-merge-integrity mission. It is tracked as a **separate, open** sibling mission, **#4990**, which requires a `spec_kitty_events` change (the shared-package boundary / C-002 keeps it out of the terminus scope). Until #4990 lands, do not treat this ADR as fully enforced across *both* reducers — only the Lamport `materialize` path and the terminus gate that consumes it conform.

## More Information

**Related ADRs:**
* ADR 2026-02-09-1 (Canonical WP Status Model) — event log format this algorithm operates on
* ADR 2026-02-09-2 (WP Lifecycle State Machine) — state machine used for the reduce step
* ADR 2026-02-09-4 (Cross-Repo Evidence Completion) — reconciliation events appended to the same log

**References:**
* CRDTs and Convergent Replicated Data Types — https://crdt.tech/
* Lamport Clocks — https://lamport.azurewebsites.net/pubs/time-clocks.pdf
* Git Merge Strategies — https://git-scm.com/docs/merge-strategies
* PRD: Feature Status State Model Remediation (Sections 2, 9, 12.1.2, 12.1.4)
