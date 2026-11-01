---
title: WP State Pattern for Lane Behavior
description: 'Replaces the flat transition matrix and procedural guard dispatcher with nine frozen lane-state classes that own their own targets, guards, and display buckets.'
status: Accepted
date: '2026-04-06'
doc_status: active
kind: ADR
updated: '2026-04-06T00:00:00Z'
---

## Context and Problem Statement

The spec-kitty work-package lifecycle previously used an 8-lane state machine implemented as a flat transition matrix (`ALLOWED_TRANSITIONS` frozenset) and a procedural guard dispatcher (`_run_guard()`). This ADR promotes `in_review` to a first-class 9th lane (see Decision below). Research (mission 065 Finding 3) identified:

- **358 lane string literals** scattered across 46 files
- **3 duplicated `LANES` tuples** in separate modules
- **Procedural guard dispatch** via a chain of `elif` branches — adding a new guard requires modifying the dispatcher, not the state that owns the behavior
- **`in_review` treated as an alias** for `for_review`, creating a concurrency blind spot: multiple agents cannot distinguish "awaiting review" from "review actively in progress"

The question: how should lane-specific behavior (allowed targets, guard conditions, terminal/blocked classification, display metadata) be colocated with the lane identity?

## Decision Drivers

- **Colocate behavior with identity**: each lane should own its allowed transitions, guards, and display metadata
- **Preserve existing API**: `validate_transition()` and `ALLOWED_TRANSITIONS` must remain accessible for non-migrated consumers (Strangler Fig)
- **Promote `in_review`**: resolve the concurrency blind spot by making `in_review` a first-class 9th lane
- **Type safety**: enable exhaustive match checking — adding a 10th lane should cause compile-time failures if behavior is missing
- **Value-object semantics**: states are immutable, equal by attributes, and cheap to construct (< 1 ms)

## Considered Options

- **Option 1: ABC + frozen dataclass** (State Pattern)
- **Option 2: Protocol-based structural typing**
- **Option 3: Extend `Lane(StrEnum)` with methods**
- **Option 4: Dictionary-of-functions dispatch table**

## Decision Outcome

**Chosen option:** "ABC + frozen dataclass" (Option 1), because it colocates behavior with state identity while preserving shared default implementations (`transition()`, `is_terminal`, `is_blocked`) that concrete classes inherit. The ABC approach enables property-test equivalence proofs against the existing transition matrix, and frozen dataclass semantics guarantee immutability and value equality.

### Consequences

#### Positive

- Each of the 9 lane states owns its `allowed_targets()`, `can_transition_to()`, guards, `progress_bucket()`, and `display_category()` — no more procedural dispatch
- Property tests prove 100% equivalence with `ALLOWED_TRANSITIONS` and `_run_guard()` — no behavioral drift
- `in_review` promoted from alias to first-class lane with `InReviewState`, resolving the concurrency blind spot for parallel review workflows
- `TransitionContext` frozen dataclass replaces the 8-argument kwargs bag in guard evaluation
- Old API preserved via Strangler Fig: `validate_transition()` continues to work for non-migrated consumers (WP06 handles migration)

#### Negative

- Adds 9 small classes + 1 ABC + 1 dataclass — moderate code surface increase
- Two parallel representations of transition logic exist during migration (Strangler Fig period) — resolved when WP06 migrates consumers
- `ReviewResult` introduces a new type that existing event-log readers do not yet produce — forward-compatible but requires WP06 for full integration

#### Neutral

- `doing` alias continues to resolve at the `wp_state_for()` boundary — no `DoingState` class exists
- `adr-template.md` in root `architecture/` is the template reference; this ADR follows the `2.x/adr/` naming convention

### Confirmation

- Property tests (T025, T026) prove equivalence with existing `ALLOWED_TRANSITIONS` and `_run_guard()` for all 9 lanes
- Full test suite passes with zero regressions (8632 baseline tests)
- Type checks (`mypy`) pass with the new types
- `WPState` instantiation benchmarks < 1 ms

## Pros and Cons of the Options

### Option 1: ABC + frozen dataclass (State Pattern)

Concrete `WPState` subclasses (one per lane) inherit from a frozen ABC dataclass. Each class implements `allowed_targets()`, `can_transition_to()`, `progress_bucket()`, and `display_category()`. A shared `transition()` method in the ABC delegates to `can_transition_to()` and the `wp_state_for()` factory.

**Pros:**

- Shared default behavior (`transition()`, `is_terminal=False`, `is_blocked=False`) without repetition
- Exhaustive pattern: adding a lane without a concrete class is a `ValueError` at the factory
- Frozen dataclass gives value-object semantics for free
- Guards live on the state that owns them — Open/Closed Principle

**Cons:**

- 9 classes is moderate boilerplate (mitigated by each being < 30 lines)
- ABC cannot enforce that subclasses are also `@dataclass(frozen=True)` at the type level

### Option 2: Protocol-based structural typing

Define a `WPState` Protocol; each lane implements it independently.

**Pros:**

- No inheritance hierarchy — fully structural
- Compatible with any class shape

**Cons:**

- No shared default implementations — `transition()`, `is_terminal`, `is_blocked` must be repeated in every class
- Cannot provide a base `transition()` that delegates to `can_transition_to()` — each class must implement the full contract independently
- Duck typing makes exhaustiveness harder to verify statically

### Option 3: Extend `Lane(StrEnum)` with methods

Add `allowed_targets()`, `is_terminal`, etc. directly as methods on the `Lane` enum.

**Pros:**

- No new classes — reuses the existing enum
- Single place for lane identity + behavior

**Cons:**

- Violates SRP: `Lane` is an identity type; adding transition logic, guard evaluation, and display metadata turns it into a God Object
- Enum methods cannot have per-member state or complex guard logic without becoming a giant switch statement — the same scatter problem in a different shape
- `TransitionContext` would still be needed but would not benefit from polymorphic dispatch

### Option 4: Dictionary-of-functions dispatch table

Replace `_run_guard()` with `GUARDS: dict[tuple[str, str], Callable]`.

**Pros:**

- Minimal structural change — same flat approach, slightly more organized
- Easy to add new guards

**Cons:**

- Does not colocate allowed targets, terminal/blocked classification, or display metadata with the lane
- Same scatter problem with different syntax — behavior is still separated from identity
- No type-safe exhaustiveness guarantee

## More Information

- **`in_review` promotion rationale**: The former `LANE_ALIASES["in_review"] = "for_review"` mapping collapsed two distinct workflow states into one. In parallel execution, `for_review` should mean "queued for review" (no reviewer has claimed it) while `in_review` means "review actively in progress by a specific reviewer." This is directly analogous to the `planned` → `claimed` → `in_progress` progression for implementation. The `(for_review, in_review)` transition carries an actor-required guard with conflict detection, preventing two reviewers from simultaneously claiming the same WP. This supersedes the approach in `2026-04-03-2-review-approval-and-integration-completion-are-distinct.md`.
- **Transition changes**: `for_review` outbound is narrowed to `{in_review, blocked, canceled}`. The former `for_review → {approved, done, in_progress, planned}` transitions move to `in_review` as the source. All outbound transitions from `in_review` require a `ReviewResult` in the `TransitionContext`.
- **Related mission artifacts**: `data-model.md` (WPState/TransitionContext design), `research.md` Finding 3 (Lane Logic Scatter), `plan.md` WP05 section.
