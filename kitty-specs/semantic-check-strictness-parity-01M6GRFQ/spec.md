# Mission Specification: Semantic-check strictness parity

**Mission Branch**: `issue-7065-semantic-check-strictness`
**Created**: 2026-11-03
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#7065 — "Semantic-check events publish a forced 'medium' strictness before the generation gate resolves the configured value"

## Problem

`emit_semantic_check_evaluated` (`src/glossary/events.py:655`) substitutes the policy
value `"medium"` whenever the caller did not pass `effective_strictness` and the
execution context does not carry one. It then derives `blocked` with a coarse
`len(conflicts) > 0 and effective_strictness != "off"` test.

The semantic-check middleware (`SemanticCheckMiddleware`, layer 2 of
`create_standard_pipeline`) emits that event *before* `GenerationGateMiddleware`
(layer 4) resolves strictness from the four-tier precedence chain — global
`.kittify/config.yaml`, mission, step, runtime `--strictness`. The gate then stores
the real value on the context, but the persisted event is never repaired. The
glossary CLI (`specify_cli glossary conflicts --strictness <value>`) and any replay
consumer read the event, not the context, so auditing and filtering diverge from the
policy the gate actually enforced.

Two disagreements are observable:

1. **Strictness.** A configured `off` or `max`, or a runtime override, is recorded as
   `medium`.
2. **Blocking.** The gate blocks via `should_block()`: `off` never blocks, `medium`
   blocks only on a high-severity conflict, `max` blocks on any conflict. The event's
   `blocked` is true for *any* conflict under any non-`off` strictness, so a `medium`
   run that proceeds is recorded as blocked, and a `max` run is recorded as `medium`.

### Terms

- **Strictness** in this repository has exactly three values — `off`, `medium`, `max`
  (`glossary.strictness.Strictness`, enforced by the `spec_kitty_events`
  `GlossaryStrictness` contract). The issue's "high"/"low" refer to conflict
  *severity* (`Severity.HIGH/MEDIUM/LOW`), not to strictness. This mission aligns the
  event with the real three-value policy.
- **Effective strictness** is the value produced by `resolve_strictness()` after the
  precedence chain, i.e. what the gate enforces.
- **Parity** means the persisted `SemanticCheckEvaluated` event carries the same
  `effective_strictness`, and the same `blocked` decision, that the generation gate
  derives for the same conflicts and policy.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The event records the policy the gate enforced (Priority: P1)

An operator configures `glossary.strictness: off` (or `max`, or passes
`--strictness`). A step runs the glossary pipeline. The `SemanticCheckEvaluated`
event that the run persists states the strictness the gate used and the blocking
decision the gate took, so `spec-kitty glossary conflicts --strictness off` and a
replayed event log describe the run that happened.

**Why this priority**: This is the defect in #7065 — the recorded state is wrong, and
every downstream consumer that reads the event inherits the error.

**Independent Test**: With `glossary.strictness: off` in `.kittify/config.yaml` and a
high-severity conflict, the emitted event has `effective_strictness == "off"` and
`blocked is False`; the generation gate applied to the same context resolves
`Strictness.OFF` and does not block.

**Acceptance Scenarios**:

1. **Given** a repo configured `strictness: off` and a high-severity conflict, **When**
   the semantic-check middleware emits `SemanticCheckEvaluated`, **Then**
   `effective_strictness` is `"off"` and `blocked` is `false`.
2. **Given** a repo configured `strictness: max` and a low-severity conflict, **When**
   the event is emitted, **Then** `effective_strictness` is `"max"` and `blocked` is
   `true` (where the gate also blocks).
3. **Given** default policy (`medium`) and a medium-severity conflict that the gate
   lets through, **When** the event is emitted, **Then** `blocked` is `false` — the
   event does not claim a block the gate did not apply.
4. **Given** a runtime `--strictness off` override and a repo configured `max`,
   **When** the pipeline emits the event, **Then** the event records `"off"` and the
   gate resolves `Strictness.OFF` for the same run.

### User Story 2 - One resolution path, no second source of truth (Priority: P2)

A maintainer changing the precedence chain edits one function, and the emitter, the
middleware and the gate cannot drift apart again.

**Why this priority**: #7065's root cause is a duplicated precedence decision; a fix
that re-implements the chain in the emitter would leave the same class of defect.

**Independent Test**: The semantic-check middleware and the gate call the same
`resolve_context_strictness` helper; a test that changes only the helper's inputs
(global config, mission, step, runtime) observes both paths change together.

**Acceptance Scenarios**:

1. **Given** the shared helper, **When** only the global config strictness changes,
   **Then** both the emitted event and the gate's resolved value change identically.
2. **Given** a context carrying `mission_strictness`, **When** the event is emitted,
   **Then** the mission override is applied as the gate applies it.

### Edge Cases

- Context types that do not declare `effective_strictness` (Protocol-style contexts
  that only receive `setattr`) must still emit a valid event.
- `effective_strictness` may arrive as a `Strictness` enum or as a plain string; both
  must serialize to the contract's string value.
- A caller that passes `effective_strictness` explicitly keeps that value; the emitter
  must not overwrite it.
- No repository config present: the safe default stays `medium` (the gate's own
  documented default), not a silent substitution.
- Clarification (layer 3) can resolve conflicts between the check and the gate. The
  event's `blocked` therefore records the gate's decision for the conflicts present at
  **check time**; the mission documents this and does not claim otherwise.
- A refused event write returns `None` and writes nothing (existing behaviour must be
  preserved).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Event carries resolved strictness | As an operator, I want `SemanticCheckEvaluated.effective_strictness` to be the gate's resolved value so that the log describes the run. | High | Open | [build] | no — positive `off` and `max` fixtures pin non-default values |
| FR-002 | Event `blocked` matches `should_block` | As an operator, I want `blocked` derived from the same predicate the gate uses so that the event never claims a block the gate did not apply. | High | Open | [build] | no — the medium-severity/`medium` fixture asserts `False` against a `True` baseline |
| FR-003 | Single strictness resolution | As a maintainer, I want one `resolve_context_strictness` helper used by the emitter, the middleware and the gate so that the precedence chain cannot drift. | High | Open | [ratchet] | no — a same-fixture test compares both paths |
| FR-004 | Runtime override reaches the check | As a CLI user, I want `--strictness` to reach the semantic-check emission so that a runtime override is reflected in the event. | Medium | Open | [build] | no — a runtime `off` over a configured `max` proves precedence |
| FR-005 | No policy constant in the emitter | As a maintainer, I want the `or "medium"` fallback removed so that no policy value is invented at the write boundary. | High | Open | [ratchet] | no — source-level and behavioural assertions |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Contract conformance | Every emitted event still validates through `spec_kitty_events.persistence.build_record` (strictness ∈ {off, medium, max}). | Compatibility | High | Open |
| NFR-002 | No new failure mode | An unresolvable or malformed strictness falls back to the gate's documented `medium` default rather than raising during emission. | Reliability | High | Open |
| NFR-003 | Test cost | The mission's tests stay in the `fast` pytest marker; no new heavy-suite dependency. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| C-001 | Emitter signature stays compatible | Existing callers pass `context`, `conflicts`, `repo_root`; new parameters are keyword with defaults. | Technical | High | Open |
| C-002 | No contract change | `spec_kitty_events` payloads and the `Strictness` enum are not modified; this is a producer-side fix. | Technical | High | Open |
| C-003 | Gate behaviour unchanged | The gate must resolve and block exactly as before; the mission changes where the value is shared, not what it decides. | Technical | High | Open |

### Key Entities

- **SemanticCheckEvaluated event**: persisted record of one semantic check —
  `effective_strictness`, `blocked`, `recommended_action`, `findings`, severity.
- **Effective strictness**: the resolved `Strictness` from global → mission → step →
  runtime precedence.
- **Generation gate**: layer 4 middleware that applies `should_block` to the resolved
  strictness.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A pipeline run configured `strictness: off` with a high-severity conflict persists an event with `effective_strictness == "off"` and `blocked is False`, and the gate resolves `Strictness.OFF`. — [build] · no-op passable: no
- **SC-002**: A pipeline run with a runtime `--strictness off` over a configured `max` persists `"off"`, proving runtime precedence reaches the event. — [build] · no-op passable: no
- **SC-003**: Zero call sites of the literal `"medium"` fallback remain in `emit_semantic_check_evaluated`, verified by source assertion. — [ratchet] · no-op passable: no
- **SC-004**: `tests/agent/glossary/` runs green with no skipped or xfail-ed test added by this mission. — [ratchet] · no-op passable: no
