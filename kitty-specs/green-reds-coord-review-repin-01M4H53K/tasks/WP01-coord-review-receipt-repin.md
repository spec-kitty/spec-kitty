---
work_package_id: WP01
title: Re-pin coord review receipt to honest [ok]
dependencies: []
requirement_refs:
- FR-001
- NFR-001
- C-001
- C-002
- SC-001
- SC-002
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
phase: Phase 1 - Test remediation
history:
- at: '2026-10-09T20:21:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: tests/characterization/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/characterization/test_trio_json_envelope.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Re-pin coord review receipt to honest [ok]

## Objectives & Success Criteria

- `TestAgentActionReviewTextEnvelope::test_coord_mission_prompt_skeleton` passes, pinning the honest-receipt behavior of `agent action review` on a coordination Mission: exit 1, no raw `Error: [Errno 2]`, `[review] Commits recorded:` present, the recorded coordination commit rendered `[ok]` (the commit is present), and the honest prose `claim was committed; the lane sync after …` disclosed.
- The whole file `tests/characterization/test_trio_json_envelope.py` is green.
- Zero `src/` lines change (NFR-001).

## Context & Constraints

- Grounding + operator-confirmed triage verdict (stale test, test-only fix): `kitty-specs/green-reds-coord-review-repin-01M4H53K/research.md` and `spec.md`.
- Charter: `.kittify/charter/charter.md` Standing Orders #4 (test remediation: stale → re-pin) and #9 (red-main / no green-wash); DIRECTIVE_024 (locality / smallest-viable diff).
- Root cause: the `[refused]` pin encodes pre-#5440 behavior; the honest marker for a committed-and-present coordination commit is `[ok]` (#5440, #5819, #5804). `workflow_executor.py:248-249` deliberately keeps the receipt committed under `TAIL_ALREADY_COMMITTED`.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on the mission branch; completed changes must merge back into `main`.
- **Planning base branch**: main
- **Merge target branch**: main

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

## Subtasks & Detailed Guidance

### Subtask T001 – Re-pin the coord review assertion

- **Purpose**: Correct the stale `[refused]` expectation to the honest current behavior.
- **Steps**: In the coord `test_coord_mission_prompt_skeleton` body, replace `assert "[refused]" in text` with `assert "[ok]" in text`; add `assert "claim was committed; the lane sync after" in text` so the test pins the honest lane-sync-failure prose rather than only a glyph. Keep `assert result.exit_code == 1`, `assert "Error: [Errno 2]" not in text`, and `assert "[review] Commits recorded:" in text`.
- **Files**: `tests/characterization/test_trio_json_envelope.py`.
- **Notes**: Red-first — the assertion is RED under the old expectation (reproduced) and GREEN after.

### Subtask T002 – Update the stale docstring

- **Purpose**: Keep the characterization narrative honest.
- **Steps**: Reword the coord `test_coord_mission_prompt_skeleton` docstring — it currently says "reports the refused coordination branch"; state instead that the recorded coordination commit is reported with the honest `[ok]` marker (the commit is present; the revert is refused under `TAIL_ALREADY_COMMITTED`) while the lane-sync failure is disclosed in prose and the command exits 1.
- **Files**: `tests/characterization/test_trio_json_envelope.py`.

## Test Strategy

- `PWHEADLESS=1 .venv/bin/python -m pytest -n0 -k "TestAgentActionReviewTextEnvelope and test_coord_mission_prompt_skeleton" tests/characterization/test_trio_json_envelope.py` (targeted, red→green).
- `PWHEADLESS=1 .venv/bin/python -m pytest -n0 tests/characterization/test_trio_json_envelope.py` (whole file green).
- `make test-fast` (baseline).

## Risks & Mitigations

- Risk: a future `src/` change makes the revert succeed → the receipt would then legitimately render `[refused]`. Out of scope; the prose assertion keeps the test meaningful either way.

## Review Guidance

- Confirm red→green: the assertion was RED on `main`'s pre-edit expectation and GREEN on the final commit.
- Confirm the diff touches only `tests/characterization/test_trio_json_envelope.py` and zero `src/` lines.

## Activity Log

- 2026-10-09T20:21:00Z – system – Prompt created.
