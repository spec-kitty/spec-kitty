---
work_package_id: WP01
title: Canonical WPStatusChanged payload builder
dependencies: []
requirement_refs:
- FR-001
- FR-003
- C-001
- C-002
- C-003
- NFR-002
- SC-002
planning_base_branch: issue-6449-migration-dry-run-payload-authority
merge_target_branch: issue-6449-migration-dry-run-payload-authority
branch_strategy: Planning artifacts for this mission were generated on issue-6449-migration-dry-run-payload-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6449-migration-dry-run-payload-authority unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Canonical builder
history:
- at: '2026-10-31T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- src/specify_cli/status/wire_payload.py
- tests/status/test_wire_payload.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/wire_payload.py
- src/specify_cli/status/__init__.py
- tests/status/test_wire_payload.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6449'
---

# Work Package Prompt: WP01 – Canonical WPStatusChanged payload builder

## ⚡ Do This First: Load Agent Profile

Load the agent profile in the frontmatter before parsing the rest of this prompt.

- **Profile**: `python-pedro` (`spec-kitty agent profile show python-pedro`)
- **Role**: `implementer`
- **Agent/tool**: `pi`

If the profile cannot be loaded, run `spec-kitty agent profile list` and select the
best match for `task_type: implement` on `authoritative_surface: src/specify_cli/status/`.

---

## Objective

Add ONE canonical constructor for the `WPStatusChanged` envelope payload, built
through `spec_kitty_events.status.StatusTransitionPayload`, and export it on the
`specify_cli.status` facade so `migration/mission_state.py` (WP02) stops
hand-shaping the dict. The expected outcome is a builder that:

- produces exactly the contract key set with the documented null policy,
- carries `mission_id` when the event has one and never invents `summary`,
- raises `pydantic.ValidationError` when the payload violates the model, and
- has a test-enforced ratchet that a new model field cannot be silently dropped.

## Context & Constraints

- Read: `kitty-specs/migration-dry-run-payload-authority-01M68JCJ/plan.md`
  (design decisions 1–3), `contracts/wp-status-changed-payload.md` (key set, null
  policy, drift ratchet), `data-model.md`, `research.md`.
- Precedent to mirror: `src/specify_cli/core/mission_payload.py`
  (`build_mission_created_payload`) uses the model plus
  `specify_cli.core.payload_shaping.apply_keep_none_fields`.
- Layer rules: CORE only. Do not import `specify_cli.sync`, `tracker` or any
  hosted surface (`tests/architectural/test_integration_boundary.py`).
- Facade rule: `tests/architectural/test_status_module_boundary.py` (SR-2) forbids
  any module outside `specify_cli.status` importing a `status.*` submodule, so the
  new symbols must appear in `status/__init__.py`'s `__all__`.
- Dead-symbol gate: every public name needs a `src/` caller; WP02 is that caller,
  so do not leave a name only reachable from tests.
- No new dependency: `spec-kitty-events>=11.3.0,<12` already ships
  `StatusTransitionPayload`.

## Branch Strategy

- **Planning base branch**: `issue-6449-migration-dry-run-payload-authority`
- **Merge target branch**: `issue-6449-migration-dry-run-payload-authority`

## Subtasks & Detailed Guidance

### Subtask T001 – Key-set and null-policy unit test (red first)

- **Purpose**: pin the wire shape before the builder exists.
- **Steps**: create `tests/status/test_wire_payload.py`. Build a representative
  `StatusEvent` (claimed -> in_progress, `mission_id` set, `reason`/`review_ref`/
  `evidence` unset) with `specify_cli.status.build_status_event` and assert the
  builder's output keys are exactly
  `{mission_slug, mission_id, wp_id, from_lane, to_lane, actor, force, reason, execution_mode, review_ref, evidence}`
  with `reason`/`review_ref`/`evidence` present as `None`, `mission_id` carried,
  `summary` absent. Add the legacy variant (no `mission_id`) asserting the key is
  absent, not `None`.
- **Files**: `tests/status/test_wire_payload.py`
- **Notes**: assert with `json.dumps(..., sort_keys=True)` byte comparison where
  the expectation is a literal — this is a `canonical-event-exempt(comparison)`
  case if the lint flags the literal.

### Subtask T002 – Model-field coverage ratchet

- **Purpose**: a new field on the contract model must fail a test instead of being
  silently dropped (the defect that dropped `mission_id`).
- **Steps**: assert
  `set(wire_payload._EVENT_FIELD_ATTRS) | wire_payload._PRODUCER_SUPPLIED_FIELDS == set(StatusTransitionPayload.model_fields)`,
  and separately assert `_PRODUCER_SUPPLIED_FIELDS == {"summary"}` so the
  exclusion cannot grow silently.
- **Files**: `tests/status/test_wire_payload.py`
- **Notes**: import the model field set from `spec_kitty_events.status`, never from
  a copy.

### Subtask T003 – Implement `status/wire_payload.py`

- **Purpose**: the one authority.
- **Steps**:
  ```python
  _KEEP_NONE_FIELDS = ("reason", "review_ref", "evidence")
  _PRODUCER_SUPPLIED_FIELDS = frozenset({"summary"})
  _EVENT_FIELD_ATTRS = {
      "mission_slug": "mission_slug", "mission_id": "mission_id",
      "wp_id": "wp_id", "from_lane": "from_lane", "to_lane": "to_lane",
      "actor": "actor", "force": "force", "reason": "reason",
      "execution_mode": "execution_mode", "review_ref": "review_ref",
      "evidence": "evidence",
  }

  def build_wp_status_changed_payload(**fields) -> dict[str, Any]:
      return apply_keep_none_fields(
          StatusTransitionPayload(**fields), keep_none_fields=_KEEP_NONE_FIELDS
      )

  def build_status_event_payload(event: StatusEvent, *, overrides=None) -> dict[str, Any]:
      ...
  ```
  `build_status_event_payload` validates `overrides` keys against
  `StatusTransitionPayload.model_fields` (raise `ValueError` on an unknown key),
  renders lanes with `str()`, renders evidence with
  `event.evidence.to_dict() if event.evidence else None`, passes `actor` verbatim,
  and forwards producer-supplied overrides (`summary` allowed but never set here).
- **Files**: `src/specify_cli/status/wire_payload.py`
- **Notes**: docstring must state why the null policy keeps three explicit nulls
  (3.0.0 conformance fixture + real row) and why local-only `StatusEvent` fields
  (`policy_metadata`, `review_result`, `reason_source`) are not passed.

### Subtask T004 – Promote onto the facade

- **Purpose**: make it reachable without breaking SR-2.
- **Steps**: import `build_status_event_payload` (and
  `build_wp_status_changed_payload`) from `.wire_payload` in
  `src/specify_cli/status/__init__.py` and add both to `__all__`, with a short
  comment naming #6449 (the canonical-producer single-authority reason).
- **Files**: `src/specify_cli/status/__init__.py`
- **Notes**: keep the import block's existing style; run
  `uv run pytest tests/architectural/test_status_module_boundary.py -q`.

### Subtask T005 – Rejection and override-validation tests

- **Purpose**: prove the model, not a dict literal, decides validity.
- **Steps**: assert a `force=True` transition with an empty/absent reason raises
  `pydantic.ValidationError`; assert `to_lane="approved"` with `evidence=None`
  raises; assert an unknown override key (`{"from_lane": ..., "summry": "typo"}`)
  raises `ValueError`; assert the well-formed control on the same fixture builds.
- **Files**: `tests/status/test_wire_payload.py`
- **Notes**: pair each refusal with the positive control from T001 (non-vacuity).

## Test Strategy

- `uv run pytest tests/status/test_wire_payload.py -q`
- `uv run pytest tests/architectural/test_status_module_boundary.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_integration_boundary.py -q`
- `uv run ruff check src/specify_cli/status/wire_payload.py tests/status/test_wire_payload.py`
- `uv run mypy src/specify_cli/status/wire_payload.py` (repo-configured typing gate)

## Definition of Done

- T001/T002/T005 were RED before T003 and are GREEN after it.
- The builder is exported on the facade; the architectural gates above pass.
- No INTEGRATION import and no new dependency.
- Diff-cover on the new module's lines is 100%.

## Risks & Mitigations

- Null-policy drift → T001 pins keys and nulls byte-for-byte.
- Facade churn → add exactly the two symbols the migration needs.

## Review Guidance

- Confirm the five test names in `tests/status/test_wire_payload.py` map to
  T001/T002/T005, and that the ratchet test reads the model's own field set.
- Confirm `apply_keep_none_fields` is reused, not re-implemented.

## Progress & Status

Record progress with `spec-kitty agent tasks mark-status <Txxx> --status done` and
`spec-kitty agent tasks add-history WP01 --note "..."`.
