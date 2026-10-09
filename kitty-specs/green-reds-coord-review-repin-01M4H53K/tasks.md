---
description: "Work package task list for the coord review honest-receipt re-pin"
---

# Work Packages: Green the reds — coord review honest-receipt re-pin

**Inputs**: Design documents from `/kitty-specs/green-reds-coord-review-repin-01M4H53K/`
**Prerequisites**: plan.md (required), spec.md (triage verdict + user stories), research.md (grounding)

**Tests**: The deliverable *is* a test re-pin; the ATDD contract is the re-pinned assertion itself.

**Organization**: One work package; the fix is a single-file characterization re-pin.

**Prompt Files**: `/tasks/WP01-coord-review-receipt-repin.md`.

## Subtask Format: `[Txxx] [P?] Description`

- Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Single project**: `tests/` (only `tests/characterization/test_trio_json_envelope.py` is touched).

---

## Work Package WP01: Re-pin coord review receipt to honest `[ok]` (Priority: P1) 🎯 MVP

**Goal**: Re-pin `TestAgentActionReviewTextEnvelope::test_coord_mission_prompt_skeleton` to the honest-receipt behavior so #5928 / #5948 go green with no product change.
**Independent Test**: `PWHEADLESS=1 .venv/bin/python -m pytest -n0 -k "TestAgentActionReviewTextEnvelope and test_coord_mission_prompt_skeleton" tests/characterization/test_trio_json_envelope.py` — RED under the old `[refused]` expectation, GREEN after the re-pin.
**Prompt**: `/tasks/WP01-coord-review-receipt-repin.md`
**Requirement Refs**: FR-001, NFR-001, C-001, C-002, SC-001, SC-002

### Included Subtasks

T001 Re-pin the coord review assertion in `tests/characterization/test_trio_json_envelope.py`: replace `assert "[refused]" in text` with `assert "[ok]" in text`, and add an assertion pinning the honest lane-sync-failure prose (`claim was committed; the lane sync after`). Keep exit-1 / no-`[Errno 2]` / `[review] Commits recorded:`.
T002 Update the now-stale docstring of the coord `test_coord_mission_prompt_skeleton` (it says "reports the refused coordination branch") to describe the honest-receipt behavior.

### Implementation Notes

- No `src/` change. Red-first: confirm RED on the pre-edit expectation first (already reproduced), then GREEN.
- Validate the full file (`tests/characterization/test_trio_json_envelope.py`) plus `make test-fast`.

### Dependencies

- None (single package).

### Risks & Mitigations

- Risk: flipping only the glyph without pinning meaning → mitigate by adding the prose assertion (T001) so the test pins the honest-failure behavior, not just a string.

---

## Dependency & Execution Summary

- **Sequence**: WP01 only.
- **MVP Scope**: WP01 is the entire mission.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| NFR-001 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| SC-001 | WP01 |
| SC-002 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Re-pin assertion to `[ok]` + honest prose | WP01 | P1 | No |
| T002 | Update stale docstring | WP01 | P1 | No |
