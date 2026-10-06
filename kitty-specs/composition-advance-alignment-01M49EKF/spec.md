# Mission Specification: Align the composition-backed run advance with the engine advance

**Mission Branch**: `issue-2562-composition-advance-alignment` (stacked on `issue-2560-runtime-bridge-query-seam`, PR #5834)
**Created**: 2026-10-06
**Status**: Draft
**Input**: GitHub issue #2562, the operator ruling in the dispatch for mission 3 of 3 (#2561 → #2560 → #2562) and in the #2562 claim comment, and `GROUNDING.md` §"#2562 design-spike finding" on `origin/spike/runtime-bridge-grounding-2560-2562`.

## Intent Summary

- **Primary actor**: an operator running `spec-kitty next` on a Mission whose current step is dispatched through step-contract composition (any built-in `software-dev` action, or a custom Mission step with an `agent_profile` / `contract_ref` binding). Secondary actor: a maintainer changing how a run advances.
- **Trigger**: after a successful composed action the run advances through a second, adapter-owned planner (`plan_composition_advance` + `advance_run_state_after_composition`). That planner runs only `apply_result` + `plan_next`. The engine's own advance (`plan_advance`) also evaluates audit significance (the `SignificanceEvaluated` event, the `significance:audit:<step>` record and the LOW-band auto-proceed re-plan) and records the RACI binding of the step it issues (`raci:<step>`). A composition-backed run therefore carries neither record, so a later answer to an audit gate is validated without its significance band and without its RACI source.
- **Outcome**: a composition-backed advance records exactly what the engine's advance records for the same run state. Both advances plan through the engine's single planning authority and commit through the engine's single commit path, built from shared per-event primitives. The composition path keeps its retrospective gate, emitter seeding, single-dispatch invariant and plan-first refusal.
- **Invariant**: a composition-backed action never re-enters the legacy DAG dispatch handler (FR-001 of `phase6-composition-stabilization`), and nothing is written before the caller's WP-iteration workspace resolution succeeds (FR-008 of `owned-checkout-lifecycle-authority`).
- **Boundary**: `src/runtime/next/` (including `_internal_runtime/`), its tests and the CHANGELOG. Out of scope: #5817 (order-dependent test pollution), #5835 (the `status_phase` P0), making the underscore seam API public, and mission-create, consolidation and lanes code.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A composition-backed advance records the issued step's RACI binding (Priority: P1)

An operator completes `specify` on a `software-dev` Mission. `spec-kitty next --result success` dispatches the action through composition and issues `plan`. The run state now holds the same `raci:plan` binding the engine's own advance would have recorded, so a later answer to an input decision on `plan` carries the binding's `raci_source` / `override_reason` in its decision record.

**Why this priority**: it affects every composition-backed advance that issues a step, which is every built-in `software-dev` advance.

**Independent Test**: drive a real run to `specify`, advance it through `decide_next_via_runtime` with the composed action's executor stubbed. Advance a byte-identical twin run through the engine's `next_step`. Compare the recorded `raci:plan` entries.

**Acceptance Scenarios**:

1. **Given** a `software-dev` run whose issued step is `specify`, **When** `decide_next_via_runtime(..., "success", ...)` advances it through composition, **Then** `state.json` `decisions["raci:plan"]` exists and equals the entry the engine's `next_step` records for the same twin run.
2. **Given** the same advance, **When** the run events are read, **Then** the composition run's event types and payloads, ignoring timestamps, equal the twin's.

### User Story 2 - A composition-backed advance into an audit gate evaluates its significance (Priority: P1)

An operator's Mission template places a blocking audit step with a `significance` block after a composed step. When the composed step completes, the run records the `SignificanceEvaluated` event and the `significance:audit:<step>` and `raci:<audit-step>` records. MEDIUM offers the soft-gate options. HIGH keeps approve/reject. LOW auto-proceeds past the gate and issues the next step. These are the same outcomes the engine's advance produces.

**Why this priority**: without it an audit gate reached through composition ignores its declared significance. A LOW gate blocks a human it should not block, and a MEDIUM gate offers the wrong options.

**Independent Test**: same twin-run comparison as User Story 1, with the frozen template carrying an audit step whose dimension scores select each band.

**Acceptance Scenarios**:

1. **Given** a HIGH-band audit gate after `specify`, **When** the composition advance completes `specify`, **Then** one `SignificanceEvaluated` event is appended, `decisions["significance:audit:<id>"]` and `decisions["raci:<id>"]` are recorded, the returned Decision is `decision_required` with options `approve` / `reject`, and the event payloads and decisions equal the engine twin's.
2. **Given** a MEDIUM-band gate, **When** the same advance runs, **Then** the returned Decision's options are `decide_solo`, `open_stand_up` and `defer`, as on the engine path.
3. **Given** a LOW-band gate, **When** the same advance runs, **Then** the audit step is added to `completed_steps`, no `DecisionInputRequested` is emitted for it, and the next step is issued, as on the engine path.

### User Story 3 - The composition path keeps its own guarantees (Priority: P1)

A maintainer relies on the composition path's existing guarantees. It never re-enters the legacy dispatch. A WP-iteration plan handed over without its workspace resolution is refused before any write. The terminal advance runs the retrospective gate around `MissionRunCompleted` (blocking capture first, non-blocking capture after). The emitter is seeded from the run snapshot before anything is emitted. In addition, a plan the run has moved past is refused, writing nothing.

**Why this priority**: the gap is closed by routing the composition path through the engine; the guarantees the separate path existed for must survive the routing.

**Independent Test**: the existing guarantee tests (single-dispatch, FR-008 refusal, strict and default retrospective ordering, seeding) keep every assertion. The adapter unit tests in `tests/runtime/test_bridge_engine.py` and `tests/runtime/test_bridge_decision_log_flush.py` stub the old planner seam (`_planner.plan_next` with an `object()` template), which the engine's `plan_advance` does not read. They are re-seamed onto a real minimal frozen template, with no assertion removed or weakened, and each re-seam is listed in the PR (squad finding, 2026-10-06). A new test covers the stale-plan refusal on the composition path.

**Acceptance Scenarios**:

1. **Given** a composed action succeeds, **When** the advance runs, **Then** `runtime_next_step` is never called.
2. **Given** a WP-iteration plan and no `wp_resolution`, **When** `advance_run_state_after_composition` is called, **Then** it raises `ValueError` and neither `state.json` nor `run.events.jsonl` changes.
3. **Given** a strict (blocking) retrospective policy and a terminal advance, **When** the advance runs, **Then** the blocking capture runs before `MissionRunCompleted` is appended. Under the default policy the capture runs after it.
4. **Given** a plan computed from a snapshot the run has since moved past, **When** the composition commit runs, **Then** it raises `StaleAdvancePlan`, nothing is written, the bridge returns its `blocked` Decision (EDGE-003), and the legacy `runtime_next_step` is never called (unlike the legacy path's stale-plan fallback, which would break the single-dispatch invariant).

### User Story 4 - One event-recording implementation (Priority: P2)

A maintainer changing the payload of one run event (step auto-completed, significance evaluated, step issued, decision input requested with its first-occurrence dedupe, run completed) changes it in one engine function, and both advances pick it up.

**Why this priority**: removes the byte-for-byte duplication the issue names. Behaviour-preserving.

**Independent Test**: the adapter module defines no event-payload construction of its own (AST check), and the engine path's event tests stay green unchanged.

**Acceptance Scenarios**:

1. **Given** the adapter module, **When** it is parsed, **Then** it constructs none of `NextStepAutoCompletedPayload`, `NextStepIssuedPayload`, `DecisionInputRequestedPayload`, `MissionRunCompletedPayload` or `DecisionRequest`.

### User Story 5 - No complexity suppression left in the engine (Priority: P3)

A maintainer reading `provide_decision_answer` finds it split into helpers at complexity ≤ 15 with no `# noqa: C901`, and with unchanged behaviour.

**Independent Test**: characterisation tests over every answer branch (input, LLM delegation, audit approve/reject, MEDIUM soft-gate decide_solo/stand-up/defer, HIGH, authority denials) pass before and after; ruff's C901 at 15 passes with the suppression removed.

**Acceptance Scenarios**:

1. **Given** the engine module, **When** ruff runs with the project's complexity ceiling, **Then** no function exceeds 15 and the module has no `noqa: C901`.

### Edge Cases

- A composition advance whose plan completes no step (nothing was issued) emits no `NextStepAutoCompleted` and no `MissionRunCompleted`, as today.
- A re-poll that plans an already-pending decision emits no second `DecisionInputRequested` (the first-occurrence dedupe moves into the shared primitive unchanged).
- A blocking retrospective capture that raises leaves the run as today: the step-completed event is appended and `state.json` is not written. The raised error still surfaces as the bridge's `blocked` Decision.
- An existing persisted composition-backed run that has no `raci:` or `significance:` records keeps working: the records appear only for steps issued after the upgrade, and `provide_decision_answer` already treats a missing record as "no RACI source / no significance band".
- A step id the frozen template does not define (a synthetic planner decision) records no `raci:` entry, as on the engine path.
- A malformed `significance` block or an unresolvable band cutoff in the policy now fails the composition plan the way it already fails the engine plan; the bridge reports it as its `blocked` Decision (EDGE-003). Today the composition path ignores the block.
- A LOW-band re-plan can issue a WP-iteration step. The bridge resolves that step's workspace from the plan's final decision (after the re-plan), so the FR-008 refusal and resolution target the step that is actually issued.
- A LOW-band re-plan that reaches the end of the template is terminal with a completed step, so the retrospective gate and `MissionRunCompleted` run, as on the engine path.
- **Residual (recorded, not fixed):** a run persisted while paused at a MEDIUM-declared gate before this change holds an approve/reject request and no `significance:` record. The composition path runs only after a composed action completes, never on a re-poll of a pending decision, so this mission does not re-evaluate such a gate. If the engine path re-plans it, the existing engine behaviour applies.
- `DecisionGitLog` commits a sanitised `DecisionInputRequested` to `kitty-specs/<mission>/decisions.events.jsonl`. On composition-backed runs reaching a MEDIUM gate it now logs the soft-gate options, and a LOW gate logs no request. The content changes; the schema does not.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | RACI binding recorded on a composition advance | As an operator, I want a composition-backed advance that issues a step to record `decisions["raci:<step>"]` exactly as the engine's `next_step` records it for the same run state, so that answers on that step carry their RACI source. | High | Open | [build] | no — red-first twin-run test through `decide_next_via_runtime` fails today (no `raci:plan`) |
| FR-002 | Audit significance evaluated on a composition advance | As an operator, I want a composition-backed advance that reaches a blocking audit step with a `significance` block to append the `SignificanceEvaluated` event and record `significance:audit:<id>` and `raci:<id>` exactly as the engine does, with the MEDIUM soft-gate options and the HIGH approve/reject options, so that the gate honours its declared band. | High | Open | [build] | no — red-first twin-run tests for HIGH and MEDIUM fail today (no event, no records, wrong MEDIUM options) |
| FR-003 | LOW-band auto-proceed on a composition advance | As an operator, I want a LOW-band audit gate reached through composition to auto-complete and the next step to be issued, as on the engine path, so that a low-significance gate does not block a human. | High | Open | [build] | no — red-first twin-run test fails today (composition stops at the gate) |
| FR-004 | One planning authority | As a maintainer, I want the composition advance to plan through the engine's `plan_advance` rather than a parallel `apply_result` + `plan_next` planner, with the adapter's own composition planner and plan type removed (no forwarding wrapper), so that a future planning change reaches both advances. | High | Open | [build] | no — an AST check fails if the adapter defines a composition planner or calls `apply_result`, and the bridge's composition planning call is the engine adapter's `plan_advance` |
| FR-005 | One commit path from shared primitives | As a maintainer, I want the per-event recording (step auto-completed, significance evaluated, step issued, decision input requested with first-occurrence dedupe, run completed) defined once in the engine and used by both advances, so that payloads cannot drift. | Medium | Open | [build] | no — AST check: the adapter constructs none of the payload classes listed in User Story 4 |
| FR-006 | Single-dispatch invariant kept | As a maintainer, I want a composition-backed action never to re-enter the legacy DAG dispatch handler, so that the action is not dispatched twice. | High | Open | [ratchet] | yes — pinned by the existing parametrised single-dispatch test; paired with FR-001 on the same fixture, which fails on a no-op |
| FR-007 | Plan-first refusal kept | As a maintainer, I want a WP-iteration plan without its `wp_resolution` refused with `ValueError` before any write, so that the run cannot wedge on an unresolvable workspace. | High | Open | [ratchet] | yes — pinned by the existing refusal test; paired with FR-001 |
| FR-008 | Retrospective gate kept | As an operator, I want the terminal composition advance to run the blocking capture before `MissionRunCompleted` and the non-blocking capture after it, and to raise the policy error under a strict policy, so that completion stays gated as configured. The engine owns emitting `MissionRunCompleted`; the adapter supplies only a pre-completion guard that can abort, and runs the non-blocking capture after the commit returns. | High | Open | [ratchet] | yes — pinned by the existing strict/default/policy-error tests; paired with FR-001 |
| FR-009 | Emitter seeding kept | As a maintainer, I want the composition advance to seed the emitter from the run snapshot before emitting, so that producer state stays consistent. | Medium | Open | [ratchet] | yes — pinned by the existing seeding tests plus a call-order assertion; paired with FR-001 |
| FR-010 | Stale plan refused | As a maintainer, I want a composition commit whose plan's source snapshot no longer matches the persisted run to raise `StaleAdvancePlan` and write nothing, surfaced by the bridge as its `blocked` Decision, so that a plan never overwrites newer progress. | Medium | Open | [build] | no — new test mutates `state.json` between plan and commit and asserts the refusal; fails today (the adapter commits blindly) |
| FR-011 | `provide_decision_answer` within the complexity ceiling | As a maintainer, I want `provide_decision_answer` split by behaviour-preserving extraction to complexity ≤ 15 with its `# noqa: C901` removed, so that the engine carries no complexity suppression. | Low | Open | [build] | no — ruff C901 fails if the suppression is removed without the split; characterisation tests pin behaviour |
| FR-012 | Changelog records the run-state change | As an operator, I want a CHANGELOG `[Unreleased]` entry stating that composition-backed runs now record `SignificanceEvaluated` events and `raci:` / `significance:` decisions, that a MEDIUM gate offers the soft-gate options and a LOW gate auto-proceeds, and that a malformed significance block now blocks the composition advance, so that the change to recorded run state is visible. | Medium | Open | [build] | no — the entry is reviewed in the diff |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Complexity | Every function touched or added in `src/runtime/next/` has cyclomatic complexity ≤ 15 (ruff C901 at the project ceiling), with zero new `noqa` suppressions. | Maintainability | High | Open |
| NFR-002 | Type checking | mypy over `src/runtime/next/` reports no more than the 21 errors present on the base; none in touched lines. | Maintainability | High | Open |
| NFR-003 | Regression surface | The runtime_bridge test surface (every test file referencing `runtime_bridge`, plus `tests/runtime`, `tests/next`, `tests/specify_cli/next`) passes with 0 new failures against the base. | Reliability | High | Open |
| NFR-004 | Gates | `tests/runtime/test_bridge_engine.py`, `tests/architectural/test_runtime_emitter_seam.py`, `tests/architectural/test_layer_rules.py`, `tests/architectural/test_no_dead_symbols.py` and `tests/runtime/test_bridge_no_compat_delegates.py` pass, with no allowlist growth. | Architecture | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Scope | Changes stay inside `src/runtime/next/` (including `_internal_runtime/`), its tests and `docs/changelog/CHANGELOG.md`. | Technical | High | Open |
| C-002 | Engine-private access concentrated | Only `runtime_bridge_engine` may import or attribute-access `_internal_runtime.engine` / `_internal_runtime.planner` (the arch guard in `tests/runtime/test_bridge_engine.py`). | Technical | High | Open |
| C-003 | No forwarders, no back-edges | No new forwarding delegate and no `runtime_bridge_*` → `runtime_bridge` import (mission 2's layout gate). | Technical | High | Open |
| C-004 | Red-first | The FR-001/FR-002/FR-003/FR-010 acceptance tests are committed failing before the change that turns them green, through the pre-existing entry point `decide_next_via_runtime`. | Process | High | Open |
| C-005 | No external contract change | Event types, payload schemas (`spec_kitty_events`) and the `Decision` shape are unchanged; only which events and decision records a composition-backed run carries changes. If closing the gap would need an external contract change or break existing persisted runs, stop and report to the orchestrator. | Technical | High | Open |

### Key Entities

- **Advance plan**: the engine's pure description of one advance — the source snapshot, the result-applied snapshot (with significance and RACI records folded in), the next decision, the completed step id and the optional significance event.
- **Run state (`state.json`)**: the persisted snapshot; its `decisions` map gains `raci:<step>` and `significance:audit:<step>` entries on composition-backed runs.
- **Run event log (`run.events.jsonl`)**: gains `SignificanceEvaluated` events on composition-backed runs reaching a significance-declaring audit gate.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For the twin-run fixtures (step issue; HIGH, MEDIUM and LOW audit gates), the composition-backed advance and the engine advance produce equal `decisions` maps and equal event sequences, ignoring timestamps — 4 of 4 fixtures match. — [build] · no-op passable: no
- **SC-002**: The adapter module contains 0 constructions of run-event payload classes and 0 calls to `plan_next` / `apply_result` for the composition plan. — [build] · no-op passable: no
- **SC-003**: The engine module contains 0 `noqa: C901` suppressions. — [build] · no-op passable: no
- **SC-004**: The runtime_bridge regression surface shows 0 new failures against the base. — [ratchet] · no-op passable: yes (paired with SC-001)

## Assumptions

- The built-in `software-dev` template has no audit steps, so the significance change reaches operators only through custom or overridden templates that combine a composed step with a significance-declaring audit step. The RACI change reaches every composition-backed advance that issues a step.
- `provide_decision_answer` already reads `raci:` and `significance:` records when present and tolerates their absence, so persisted runs need no migration.
