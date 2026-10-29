---
work_package_id: WP01
title: Raise the spec-kitty-events floor to 11.3.0
dependencies: []
requirement_refs:
- FR-001
- FR-002
- C-001
planning_base_branch: issue-6445-decision-significance-adoption
merge_target_branch: issue-6445-decision-significance-adoption
branch_strategy: Planning artifacts for this mission were generated on issue-6445-decision-significance-adoption. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6445-decision-significance-adoption unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-decision-significance-adoption-01M5ZMNH
base_commit: a817c72f345cdb40123fdb622adec5c1454969c9
created_at: '2026-10-27T22:08:11.574293+00:00'
subtasks:
- T001
- T002
- T003
history: []
agent_profile: python-pedro
authoritative_surface: pyproject.toml
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- pyproject.toml
- uv.lock
- tests/architectural/test_pyproject_shape.py
- .kittify/release/shared-package-compatibility.json
role: implementer
tags: []
tracker_refs: []
---

# WP01 — Raise the spec-kitty-events floor to 11.3.0

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Make the declared `spec-kitty-events` range start at 11.3.0, the first published release with the `decision_significance` models and actor-id sentinels WP02 imports, and confirm the 11.3.0 lock (committed before this mission as `cc993d31`, #6602) is consistent.

## Context

- 11.1.0–11.2.1 never reached PyPI (spec-kitty-events#143). A `>=11.2.0` floor would misstate what is installable (see `traces/design-decisions.md` on the coordination branch).
- `tests/architectural/test_pyproject_shape.py` pins the exact range string (line ~28) and flags a range that does not contain `11.0.0` as retired (line ~212).
- Commands: `uv lock` (never hand-edit the lockfile).

### Subtask T001: Red-first — pin the new range

- **Purpose**: the shape test fails until the range moves.
- **Steps**: change the pinned `spec-kitty-events` entry in `test_pyproject_shape.py` to `spec-kitty-events>=11.3.0,<12`, and the retired-range probe from `11.0.0` to `11.3.0`. Run the test; it must fail on the current `pyproject.toml`.
- **Validation**: `pytest tests/architectural/test_pyproject_shape.py` red with the range mismatch.

### Subtask T002: Move the floor

- **Steps**: `pyproject.toml` → `spec-kitty-events>=11.3.0,<12`; `uv lock` (lock content stays 11.3.0; only the specifier metadata changes); `.kittify/release/shared-package-compatibility.json` `cli_range` → `>=11.3.0,<12`, and append to its `resolution_note` why the floor moved.
- **Validation**: `uv lock --check` clean; `git diff uv.lock` shows only the specifier change.

### Subtask T003: Verify the lock refresh (FR-001)

- **Steps**: run `tests/architectural/test_pyproject_shape.py`, `tests/architectural/test_shared_package_boundary.py`, `tests/architectural/test_events_tracker_public_imports.py`, `tests/release/test_check_shared_package_drift.py`, `tests/contract/test_events_envelope_matches_resolved_version.py`.
- **Validation**: all green; record counts.

## Definition of Done

- The range is `>=11.3.0,<12` in `pyproject.toml`, `uv.lock` metadata and the compatibility manifest.
- The five gates above pass. Subtasks recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Risks

- Other tests or docs pin `>=11.0.0`; grep for `11.0.0,<12` and update only the pins of this range (not historical changelog text).

## Reviewer Guidance

- Check the lockfile diff is tool-generated and minimal; check no git pin or path override was added (C-001).

Implement with: `spec-kitty agent action implement WP01 --agent claude --mission decision-significance-adoption-01M5ZMNH`
