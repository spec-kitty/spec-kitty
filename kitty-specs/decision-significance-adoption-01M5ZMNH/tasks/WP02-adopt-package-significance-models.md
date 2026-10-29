---
work_package_id: WP02
title: Adopt the package decision-significance models and actor-id sentinels
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-002
- C-003
- C-004
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6445-decision-significance-adoption
merge_target_branch: issue-6445-decision-significance-adoption
branch_strategy: Planning artifacts for this mission were generated on issue-6445-decision-significance-adoption. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6445-decision-significance-adoption unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-decision-significance-adoption-01M5ZMNH
base_commit: 4332e05bf9aa5b5e945db677240fdac906246ad4
created_at: '2026-10-27T22:25:21.608541+00:00'
subtasks:
- T004
- T005
- T006
- T007
- T008
history: []
agent_profile: python-pedro
authoritative_surface: src/runtime/next/_internal_runtime/
create_intent:
- tests/next/test_decision_significance_adoption.py
execution_mode: code_change
model: ''
owned_files:
- src/runtime/next/_internal_runtime/schema.py
- src/runtime/next/_internal_runtime/significance.py
- src/runtime/next/_internal_runtime/raci.py
- src/runtime/next/_internal_runtime/engine.py
- src/runtime/next/_internal_runtime/events.py
- src/runtime/next/runtime_bridge_retrospective.py
- src/specify_cli/events/decision_log.py
- tests/next/test_internal_runtime_coverage.py
- tests/next/test_decision_significance_adoption.py
- tests/runtime/test_bridge_engine.py
- tests/specify_cli/events/test_decision_log.py
role: implementer
tags: []
tracker_refs: []
---

# WP02 — Adopt the package decision-significance models and actor-id sentinels

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Delete core's local `SignificanceEvaluatedPayload`, `TimeoutExpiredPayload` and `ResolvedRACIBinding`, use `spec_kitty_events.decision_significance` instead, and make every resolved or persisted RACI role carry an actor id per the operator ruling on #6445.

## Context

- Design (plan.md "Design"; operator Decision Moment `01M5ZMPA58JS7K7S4S40CH7H1M`): split authoring and resolved types.
  - `schema.RACIRoleBinding` → `RACIRoleSpec` (authoring; `actor_id` optional), still used by `RACIAssignment`.
  - Resolved and persisted roles use the package `RaciRoleBinding` / `ResolvedRaciSnapshot`.
- Sentinel mapping (operator ruling 2026-10-19 on #6445): an unresolved human → `HUMAN_IN_CHARGE_ACTOR_ID`; an unresolved llm or service → `UNKNOWN_ACTOR_ID`. Import both from `spec_kitty_events`; never hard-code the strings.
- Input-based resolution runs first (FR-005): `_resolve_actor` / `_resolve_actor_optional` still look up `mission_owner_id` / `agent_id` / `service_id`; responsible/accountable keep the fail-closed escalation inside `resolve_raci`.
- Do not add an append path (C-002); `_record_significance` keeps its interim append. Do not touch `src/specify_cli/decisions/` (C-004, mission M4).
- Current line refs: `engine.py:356-362`, `414-421` (fallbacks), `488-491` (persistence), `824` (soft gate); `raci.py:27-68` (`infer_raci`), `199-265` (resolution helpers).

### Subtask T004: Red-first acceptance tests

- **Purpose**: fail on today's code through the existing entry points.
- **Steps**: new `tests/next/test_decision_significance_adoption.py`:
  1. `infer_raci` for a prompt step, an advisory audit and a blocking audit returns a package `ResolvedRaciSnapshot` whose every role (R, A, C, I) has the sentinel for its type.
  2. `resolve_raci` with `mission_owner_id` and `agent_id` inputs records those ids (not sentinels); with an explicit RACI whose consulted human and informed llm cannot resolve, they get `human-in-charge` / `UNKNOWN`.
  3. A runtime audit-gate run (reuse the fixtures in `tests/next/test_internal_runtime_coverage.py`) writes a `SignificanceEvaluated` row that `spec_kitty_events.conformance.validate_event(..., "SignificanceEvaluated")` accepts.
  4. The medium-band soft gate answered by an actor with no id records `soft_gate:<id>` with a sentinel actor id.
  5. `runtime.next._internal_runtime.significance` and `.schema` no longer define the deleted classes (`hasattr` checks).
- **Validation**: all five fail on the current tree for the expected reason.

### Subtask T005: Schema and significance models

- **Steps**: rename `RACIRoleBinding` → `RACIRoleSpec` in `schema.py` (`RACIAssignment` uses it); delete `ResolvedRACIBinding`. In `significance.py` delete `SignificanceEvaluatedPayload` and `TimeoutExpiredPayload`; `SoftGateDecision.actor`, `.participants` and `DimensionScoreOverride.overridden_by` take the package `RaciRoleBinding`. Keep `RACIEscalationPayload` local.

### Subtask T006: Resolution and sentinels

- **Steps**: in `raci.py` add `bind_actor(actor_type, actor_id) -> RaciRoleBinding` (blank or `None` id → sentinel by type). `resolve_raci` returns `ResolvedRaciSnapshot`; `_resolve_actor` returns a package binding; `_resolve_actor_optional` returns `bind_actor(...)` on a failed lookup. Factor the inferred `RACIAssignment` + rule into a private helper used by both `resolve_raci` and `infer_raci`; `infer_raci` maps every role through `bind_actor`.
- **Validation**: T004 tests 1–2 green; complexity ≤ 15.

### Subtask T007: Engine, emitter and adapters

- **Steps**: `engine.py` imports the package `SignificanceEvaluatedPayload` and builds the service actor with the package binding; the soft gate uses `bind_actor(actor_type, actor.actor_id)`. `events.py` Protocol and `NullEmitter` take the package payload types (`DecisionTimeoutExpiredPayload` for the timeout hook). Update typing in `specify_cli/events/decision_log.py` and `runtime_bridge_retrospective.py`.
- **Validation**: T004 tests 3–5 green; `mypy --strict` on touched files clean.

### Subtask T008: Existing tests and blast radius

- **Steps**: update `tests/next/test_internal_runtime_coverage.py`, `tests/runtime/test_bridge_engine.py`, `tests/specify_cli/events/test_decision_log.py` for the renamed and replaced types (re-pin provenance error wording to the package's messages; keep each test's intent). Run `tests/next tests/runtime tests/specify_cli/runtime tests/specify_cli/events tests/decisions tests/specify_cli/decisions`, the three architectural gates, and `make test-fast`.
- **Validation**: green; ruff check, `ruff format --check --force-exclude`, mypy clean on touched files.

## Definition of Done

- No local definition of the three deleted models remains; every resolved or persisted RACI role carries an id; the audit-gate row validates with the package.
- T004 tests were red first and are green now; blast radius green with counts recorded. Subtasks recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Risks

- A test constructs a resolved binding without an id on purpose (e.g. asserting `None` survives): re-pin it to the sentinel, citing the ruling.
- `RACIRoleSpec` must stay importable where templates are parsed; YAML keys are unchanged.

## Reviewer Guidance

- Confirm input-based resolution is unchanged when inputs are present (FR-005) and the fail-closed escalation for R/A still raises inside `resolve_raci`.
- Confirm the sentinels come from the package and no new append path was added.

Implement with: `spec-kitty agent action implement WP02 --agent claude --mission decision-significance-adoption-01M5ZMNH`
