---
title: Atomic Work Package Start Lifecycle
description: 'Implementation start emits planned, claimed, and in_progress as one atomic event batch, so a crash mid-sequence can no longer strand a work package in claimed.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-05-01'
---

- `2026-02-09-1-canonical-wp-status-model.md`
- `2026-02-09-3-event-log-merge-semantics.md`
- `2026-04-06-1-wp-state-pattern-for-lane-behavior.md`

---

## Context and Problem Statement

Implementation start is a semantic operation, not just a raw lane edge. Starting
work from `planned` requires two canonical events:

1. `planned -> claimed`
2. `claimed -> in_progress`

Before this ADR, callers emitted those transitions independently. That left
three architectural gaps:

1. A crash or exception between the two writes could strand a WP in `claimed`
   even though implementation had logically started.
2. Retry behavior varied by surface: direct CLI, agent workflow, and
   orchestrator API could disagree on whether same-agent retries were safe or
   conflicting.
3. Presentation treated `claimed` as passive backlog in some views even though
   it is an active ownership state.

Spec Kitty supports 15 coding-agent hosts plus orchestration/API surfaces.
Lifecycle correctness therefore cannot live in a host-specific command wrapper
or in a one-off patch for one agent. All surfaces that begin implementation or
review must apply the same ownership, idempotency, and event-persistence
semantics.

## Decision Drivers

- **Agent-surface parity** — Claude, Codex, OpenCode, Cursor, and all other
  supported coding agents must observe the same lifecycle behavior.
- **Crash consistency** — a logical lifecycle start must not leave a half-started
  event log.
- **Idempotent retry** — a same-actor retry after dispatch or process restart
  should resume; a different actor should see a conflict.
- **Event-log authority** — preserve the append-only status log and the 9-lane
  state machine rather than inventing a bypass.
- **Visible ownership** — `claimed` is active work ownership and must be rendered
  with Doing/progress, not hidden in Planned backlog.

## Considered Options

- **Option 1:** Keep raw transition calls at every caller and document retry rules.
- **Option 2:** Special-case the failing agent workflow path only.
- **Option 3:** Collapse implementation start into a single `planned -> in_progress`
  transition.
- **Option 4:** Move claim ownership to an external lock/control-plane service.
- **Option 5:** Add a shared lifecycle service backed by atomic event batches.

## Decision Outcome

**Chosen option:** "Option 5: shared lifecycle service backed by atomic event
batches", because it preserves the canonical event model while making lifecycle
starts all-or-none and host-independent.

### Implementation Policy

All implementation-start surfaces call a shared lifecycle operation instead of
hand-emitting start transitions:

```text
start_implementation_status(...)
```

All review-start surfaces call:

```text
start_review_status(...)
```

The lifecycle service owns these rules:

1. `planned` implementation start writes `planned -> claimed -> in_progress` as
   one atomic event batch and materializes once.
2. `claimed` by the same actor resumes to `in_progress`.
3. `claimed` or `in_progress` by a different actor raises a claim conflict.
4. `in_progress` by the same actor is a no-op.
5. Review start mirrors the same pattern for `for_review -> in_review`.
6. Raw status emit remains available for explicit low-level transitions, but
   caller surfaces must not reimplement lifecycle-start policy.

Atomic batch persistence appends the full batch to a temporary JSONL file and
then replaces the canonical event log. Reducer ordering is preserved by assigning
deterministically increasing timestamps inside the batch.

### Supersession Analysis

This ADR does **not** supersede the existing status ADRs:

- `2026-02-09-1` remains authoritative for the append-only JSONL event log and
  derived `status.json` snapshot.
- `2026-02-09-3` remains authoritative for merge-time concatenate, dedupe, sort,
  and reduce semantics. This ADR acts earlier, at write time, by making a single
  process's logical start operation atomic before git merge semantics apply.
- `2026-04-06-1` remains authoritative for the 9-lane state model and lane-owned
  behavior. This ADR clarifies which service owns multi-edge lifecycle commands
  that are built from those lane transitions.

The new rule is additive: **semantic lifecycle starts are service-owned; raw
transition validation remains state-machine-owned.**

### Consequences

#### Positive

- Same-agent retries become safe across CLI, workflow, and orchestrator API.
- Different-agent overlap is detected consistently instead of depending on the
  entry point.
- Crash windows no longer expose `planned -> claimed` without the paired
  `claimed -> in_progress` event for new implementation starts.
- `claimed` work is visible as active Doing work, while still preserving the
  separate canonical lane for stale-claim diagnostics and audit.
- The design remains offline-first and git-native.

#### Negative

- Start lifecycle behavior now has a dedicated service layer that callers must
  use correctly.
- Atomic batch writes rewrite the JSONL file through a temp file, which is more
  code than simple append.
- Diff coverage and tests must cover both single-event emit and batch-event emit
  paths.

#### Neutral

- The canonical event sequence remains two events; historical logs and reducers
  do not need migration.
- The low-level status command can still emit individual legal transitions for
  repair, migration, and operator workflows.
- `claimed` remains distinct from `in_progress`; the display change only affects
  progress grouping.

### Confirmation

This decision is valid when:

1. all implementation and review start entry points use the shared lifecycle
   service;
2. same-actor retries are idempotent and different-actor retries conflict;
3. a planned implementation start persists both events or neither event;
4. `claimed` appears with active Doing work in dashboards/boards while stale
   claim diagnostics still see the canonical lane;
5. CI covers batch persistence, lifecycle conflict/no-op paths, dashboard lane
   grouping, and orchestrator API parity.

## Pros and Cons of the Options

### Option 1: Keep raw transition calls at every caller

**Pros:**

- Minimal code movement.
- Preserves every caller's current structure.

**Cons:**

- Keeps lifecycle policy duplicated across host surfaces.
- Leaves retry and conflict semantics dependent on caller ordering.
- Does not close the crash window between start events.

### Option 2: Special-case the failing agent workflow path only

**Pros:**

- Fastest targeted fix for Issue #944.

**Cons:**

- Violates agent-surface parity.
- Leaves orchestrator API and direct CLI with divergent behavior.
- Creates a pattern for host-specific lifecycle exceptions.

### Option 3: Collapse implementation start into one transition

**Pros:**

- Removes the multi-event crash window.

**Cons:**

- Destroys the audit distinction between claim and active implementation.
- Conflicts with the canonical 9-lane state machine.
- Breaks stale-claim diagnostics and existing event history semantics.

### Option 4: External lock/control-plane service

**Pros:**

- Could provide real-time distributed locking across machines.

**Cons:**

- Violates offline-first status authority.
- Makes local CLI correctness depend on network/service availability.
- Duplicates ownership state outside the canonical event log.

### Option 5: Shared lifecycle service backed by atomic event batches

**Pros:**

- Keeps event sourcing and the 9-lane model intact.
- Centralizes lifecycle-start policy for all supported agents and APIs.
- Provides crash consistency for composite start operations.
- Keeps ownership visible and auditable.

**Cons:**

- Adds a service abstraction between callers and raw status emit.
- Requires callers to distinguish semantic lifecycle operations from low-level
  repair transitions.

## More Information

- Issue: [#944](https://github.com/Priivacy-ai/spec-kitty/issues/944)
- Implementation PR: [#946](https://github.com/Priivacy-ai/spec-kitty/pull/946)
- Canonical status model: `2026-02-09-1-canonical-wp-status-model.md`
- Event-log merge semantics: `2026-02-09-3-event-log-merge-semantics.md`
- Current lane model: `2026-04-06-1-wp-state-pattern-for-lane-behavior.md`
