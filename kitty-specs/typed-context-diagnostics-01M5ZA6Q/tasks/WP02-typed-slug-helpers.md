---
work_package_id: WP02
title: Typed synthesis slug helpers
dependencies: []
requirement_refs:
- FR-007
- NFR-001
- C-004
planning_base_branch: issue-6460-typed-context-diagnostics
merge_target_branch: issue-6460-typed-context-diagnostics
branch_strategy: Planning artifacts for this mission were generated on issue-6460-typed-context-diagnostics. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6460-typed-context-diagnostics unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-typed-context-diagnostics-01M5ZA6Q
base_commit: cca6002640a3a0c24cec7a5ac65b4b5b2f9242bb
created_at: '2026-10-27T18:43:13.076727+00:00'
subtasks:
- T009
- T010
- T011
phase: Phase 1 - Contract
history:
- at: '2026-10-27T18:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/synthesizer/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/synthesizer/reach_only.py
- tests/charter/synthesizer/test_synthesize_activation_append.py
- tests/charter/synthesizer/test_styleguide_reach_only.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Typed synthesis slug helpers

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address every feedback item; record progress with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

Close #6461 item 3 (FR-007, C-004). The issue names `created_tactic_slugs(reconciliation: object)`; it has since been renamed to `created_slugs_by_kind` and `created_slugs` (`src/charter/activation/synthesizer/reach_only.py:344,349` on origin/main `581b5c46`), both still `object`-typed.

- Both helpers take `reconciliation: ReconciliationDelta | None` (concrete type from `charter.activation.synthesizer.reconcile`).
- No `object`, `Any`, `# type: ignore` or `# noqa` added.
- Missing (`None`) or foreign input (not a `ReconciliationDelta`, e.g. a `SimpleNamespace`) still returns `[]` / an all-empty mapping at runtime (operator note on #6461, `reach_only.py:357-358`).
- `mypy --strict` and ruff clean on the file.

## Context & Constraints

- Sibling mission M2 also edits `reach_only.py` (and `reconcile.py`). Keep the diff to the one import and the two signatures/docstrings; do not reformat or move anything else (C-004).
- The caller `src/specify_cli/cli/commands/charter/synthesize.py:548` passes `getattr(result, "reconciliation", None)` (typed `Any`); leave it unchanged (not owned; it type-checks).
- Charter C-011: the red test is its own commit before the implementation commit.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: issue-6460-typed-context-diagnostics
- **Merge target branch**: issue-6460-typed-context-diagnostics

> Populated by `finalize-tasks`. Use `spec-kitty agent action implement WP02 --agent claude --mission typed-context-diagnostics-01M5ZA6Q`.

## Subtasks & Detailed Guidance

### Subtask T009 – Tidy-first: hoist the deferred import

- `created_slugs` does `from charter.activation.synthesizer.reconcile import ReconciliationDelta  # deferred import`, but the module already imports `reconcile` at top level (`reach_only.py:36`). Move `ReconciliationDelta` into that existing top-level import. Behaviour-preserving; run `tests/charter/synthesizer/test_synthesize_activation_append.py tests/charter/synthesizer/test_styleguide_reach_only.py`; commit separately: `refactor(charter): import ReconciliationDelta at module level in reach_only`.

### Subtask T010 – Red typing test

- In `tests/charter/synthesizer/test_styleguide_reach_only.py`, add a test that pins the public signature: `inspect.signature(created_slugs_by_kind).parameters["reconciliation"].annotation` resolves (via `typing.get_type_hints`) to `ReconciliationDelta | None`, same for `created_slugs`. RED today (`object`). Keep the existing foreign-input assertions (`:462-463`, `test_synthesize_activation_append.py:202-203`) as the positive control for runtime behaviour. Commit: `test(charter): pin the slug helpers' reconciliation parameter type (#6461)`.

### Subtask T011 – Annotate

- Change both signatures to `reconciliation: ReconciliationDelta | None`. Keep the `isinstance` guard so foreign objects still yield `[]` (callers pass an untyped `getattr`). Update the docstring ("empty for a missing or foreign delta"). Existing tests that pass `SimpleNamespace` stay as runtime evidence; if mypy runs on tests and flags them, keep the call but route through a variable typed `Any` with a short comment explaining it exercises the foreign-input guard (no suppression).
- Verify: `uv run --frozen mypy --strict src/charter/activation/synthesizer/reach_only.py`; ruff check + `ruff format --check --force-exclude` on the file.

## Test Strategy

- `uv run --frozen pytest tests/charter/synthesizer -q` (owning directory) + `make test-fast`; record counts via `add-history`.

## Risks & Mitigations

- Merge conflict with M2: minimal diff.

## Review Guidance

- Red→green on T010; no suppressions; foreign-input behaviour unchanged.

## Progress & Status

Use `spec-kitty agent tasks add-history`, `move-task`, `status`; never edit history here.
