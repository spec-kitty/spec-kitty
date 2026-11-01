---
title: 'ADR: WP Lane Finite State Machine, the `genesis` lane, and the finalize event-log
  clobber fix'
description: 'Adds a non-display `genesis` lane so seeding a work package becomes a real persisted edge, and stops finalize-tasks overwriting the canonical event log with a stale copy.'
status: Accepted
date: '2026-06-07'
doc_status: active
kind: ADR
updated: '2026-06-07T00:00:00Z'
---

## Context

A newly created coordination-topology mission could not start its implement loop:
`spec-kitty agent action implement WP01` failed with *"WP WP01 has no canonical
status"* even though `finalize-tasks` printed *"13 WPs seeded"*. This reproduced
the [#1589](https://github.com/Priivacy-ai/spec-kitty/issues/1589) "status
split-brain": `tasks status` showed 13 planned, `materialize` showed `0 events
-> 0 WPs`, and `emit … --to planned` was rejected as `planned -> planned`.

Live probing isolated **two independent defects**, both rooted in
under-encapsulation of the WP lane state model:

1. **Finalize clobbers the canonical event log.** `bootstrap_canonical_state`
   correctly seeds lane-state events through the transactional emitter into the
   coordination worktree. But `finalize-tasks` then `shutil.copy2`'d the
   *primary checkout's* stale `status.events.jsonl` + `status.json` (lifecycle
   events only, no lane state) **over** the coord worktree's canonical copies
   before committing — wiping the just-seeded lane state. (Proven: a direct
   `emit` persisted `WP01=claimed`; running `finalize-tasks` reset it to `[]`.)

2. **`genesis`/`planned` conflation makes the seed an implicit no-op.**
   `_derive_from_lane` returned `Lane.PLANNED` for a work package with no
   lane-state events. So the bootstrap "seed" was a `planned -> planned`
   self-transition — semantically a no-op, and indistinguishable from a real
   planned WP. The *write* layer treated "uninitialized" as `planned` (lenient);
   the *read* layer (`implement`/`materialize`/`doctor`) demanded an explicit
   event (strict). Two readers, two truths.

The deeper smell: the lane model had **two parallel sources of transition
truth** — the State-pattern classes in `status/wp_state.py` (`allowed_targets()`)
and a hand-maintained flat `ALLOWED_TRANSITIONS` frozenset in
`status/transitions.py`, kept in lockstep only by an equivalence test. Each
prior incident was patched class-by-class ("whack-a-class"). The operator
directed a proper fix now rather than another patch.

## Decision

### 1. Introduce `Lane.GENESIS` as an explicit, non-display pre-finalize lane

`genesis` is the state of a WP that has been *created* (`WPCreated`) but not yet
seeded into the lane lifecycle. `_derive_from_lane` now returns `GENESIS` (not
`PLANNED`) for a WP with no lane-state events. The bootstrap seed becomes an
**explicit `genesis -> planned` transition** — a real, persisted edge, not a
dropped self-transition. Read and write layers now agree: an unfinalized WP is
`genesis`; a finalized one is `planned`.

`genesis` is **non-display**: it is deliberately *not* in `CANONICAL_LANES`, has
no kanban column, no board-summary key, and weight `0.0`. A `genesis` WP has no
lane events and so never materializes into a snapshot (once seeded it is
`planned`); the lane exists only as the seed's `from_lane` and as the
`_derive_from_lane` result for unseeded WPs. It is accepted by event validation
as a valid `from_lane`.

**Consequent behavioural change (intended):** a WP can no longer be transitioned
straight to `claimed`/`in_progress` from nothing — it must first be seeded
`genesis -> planned` (which `finalize-tasks` does). This is strictly more correct
(you cannot claim an unfinalized WP) and is the explicit contract the operator
requested.

### 2. The WP lane State machine is the single source of transition truth

`status/wp_state.py` (the State pattern, per
[refactoring.guru/design-patterns/state](https://refactoring.guru/design-patterns/state))
is now the **authority** for structural transitions. `ALLOWED_TRANSITIONS` in
`status/transitions.py` is **derived** from the state objects' `allowed_targets()`
rather than hand-maintained, eliminating the dual-source drift the equivalence
test previously papered over. Rich mission guards (actor, subtasks-complete,
review result, done evidence, force) remain layered on top by
`validate_transition` via `_GUARDED_TRANSITIONS` — guard evaluation is a separate
concern from edge existence.

`GenesisState` is a first-class state (`allowed_targets = {planned, canceled}`).

### 3. The FSM exposes a canonical, encapsulated interface

`WPState` gains the operator-specified Finite-State-Machine vocabulary:

- `current_lane -> Lane` — the lane this state represents.
- `may_transition_to(target: Lane) -> bool` — guard-free structural edge check.
- `transition_to(target, ctx) -> WPState` — guarded transition (raises
  `InvalidTransitionError` on a missing edge or rejected guard).

(`lane`, `can_transition_to`, and `transition` are retained as the underlying
mechanics so existing callers are unaffected — this is a behaviour-preserving
refactor for the nine pre-existing lanes.)

### 4. Finalize must not overwrite the coordination event log

`finalize-tasks` no longer copies `status.events.jsonl` / `status.json` from the
primary checkout into the coordination worktree. The canonical event log is
owned by the transactional emitter on the coordination branch; finalize commits
only the other planning artifacts (`tasks.md`, `lanes.json`,
`acceptance-matrix.json`, …). The copy logic is extracted into the testable
`_stage_finalize_artifacts_in_coord_worktree` helper, which skips
`_COORD_OWNED_STATUS_FILES`.

## Consequences

- **Positive:** `#1589` is fixed at the root; the implement loop can start.
  The lane model has one transition authority (no drift). The FSM is explicitly
  testable. `genesis` makes "unfinalized" a first-class, observable state rather
  than an implicit default that silently masquerades as `planned`.
- **Cost:** one extra `Lane` enum member (10 total; 9 active/display + genesis)
  and `~2` derived transition edges. Tests that emitted transitions on an
  unseeded WP now seed `genesis -> planned` first (a `_seed_planned` helper); this
  is a one-line setup addition that makes the previously-implicit step explicit.
- **Trade-off accepted (operator):** slightly more model surface in exchange for
  conceptual clarity, testability, and the elimination of the whack-a-class
  failure mode.
- **Non-goals:** display/kanban changes (genesis is non-display by design).

  > **Revision (DM-01KTH03G, post-initial-draft):** guard unification was
  > originally listed as a non-goal, but the accepted decision moved guards and
  > force handling **into** the `WPState` objects (`guard_for` / `check_transition`);
  > `validate_transition` is now a thin delegator and `_GUARDED_TRANSITIONS` is gone.
  > See `src/specify_cli/status/wp_state.py`.

## Verification

`tests/status/`, `tests/specify_cli/status/`, and all touched cross-cutting test
files (coordination, sync, dashboard, lanes, integration, upgrade) are green;
`ruff` clean and `mypy` neutral (no new errors) on all changed production files.
A dedicated regression test (`test_finalize_coord_staging.py`) pins that finalize
preserves the seeded coordination event log.
