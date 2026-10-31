---
description: "Work package task list for remove-decisions-mission-dir-01M6695J"
---

# Work Packages: Remove the read-side decisions service._mission_dir

**Inputs**: `kitty-specs/remove-decisions-mission-dir-01M6695J/` (spec.md, plan.md, research.md, reasons-canvas.md)
**Prerequisites**: plan.md (required), spec.md (user stories), research.md

**Tests**: This is a dead-code removal with a red-first invariant guard; the
test work is part of the single work package (see T001).

**Organization**: One work package; the mission is a single-concern change
(IC-01 in plan.md).

## Subtask Format: `[Txxx] [P?] Description`

- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`

---

## Work Package WP01: Remove the dead read-side `_mission_dir` and pin the write-side-only invariant (Priority: P1) 🎯 MVP

**Goal**: Delete `src/specify_cli/decisions/service.py::_mission_dir` (caller-less since #6762), remove its two orphaned leniency pins, re-point stale docstrings, and add the red-first STATUS_STATE-access guard.
**Independent Test**: On the planning base the new guard test fails (the read-side `read_dir(STATUS_STATE)` call exists); on the WP head it passes, `grep -c "_mission_dir" src/specify_cli/decisions/service.py` returns 0, and the targeted suites plus the three architectural gates are green.
**Prompt**: `/tasks/WP01-remove-dead-read-side-mission-dir.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, C-001, C-002, C-003

### Included Subtasks

T001 Add the red-first guard test `tests/specify_cli/decisions/test_service_status_state_access.py` asserting `decisions/service.py` holds no read-side `placement_seam(...).read_dir(MissionArtifactKind.STATUS_STATE)` call; commit it first and prove it RED on the planning base
T002 Delete `_mission_dir` (definition + docstring) from `src/specify_cli/decisions/service.py`; prove the guard from T001 now GREEN
T003 Re-point every remaining docstring/comment in `src/specify_cli/decisions/service.py` that names `_mission_dir` (`_resolve_mission_id` comment, `_write_mission_dir` docstring, `_ledger_dir` docstring, `open_decision` and terminal-write comments), and update the WP06 ledger row for `decisions/service.py` in `docs/development/reference/read-side-seam-classification.md` to record the site's removal (#6766, following the ledger's "(removed, #NNNN)" row convention) — spec-squad finding
T004 Delete the two orphaned pins in `tests/specify_cli/test_read_seam_leniency.py` and correct its module-docstring site ledger (the "``decisions/service.py`` (1)" migrate-fail-loud entry leaves with the helper; also fix the docstring's wrong ledger path, `docs/development/read-side-seam-classification.md` → `docs/development/reference/read-side-seam-classification.md`) — spec-squad finding. Discovered red-first during T006: the two lockstep pins in `tests/decisions/test_decisions_reconciler.py` (`test_service_and_doctor_resolve_ledger_dir_in_lockstep` and its `_under_coord_topology` variant) also anchor on the deleted helper — they stay live but resolve the events dir through `placement_seam(...).read_dir(STATUS_STATE)` directly (discovered amendment; same WP)
T005 Add the `[Unreleased]` changelog entry in `docs/changelog/CHANGELOG.md` (bold impact-first lead with `(#6766)`, before/after, under 1,200 characters)
T006 Run the validation surface: `tests/decisions/`, `tests/specify_cli/decisions/`, `tests/specify_cli/test_read_seam_leniency.py`, `tests/architectural/test_no_dead_symbols.py`, `tests/architectural/test_no_read_side_bypass.py`, `tests/architectural/test_no_write_side_rederivation.py`, plus ruff check, `ruff format --check --force-exclude`, and mypy on the touched files; record commands + counts

### Implementation Notes

- Red-first order is mandatory (charter ATDD-First Discipline): T001 lands as
  its own commit before any removal commit; the reviewer verifies red on the
  planning base and green on the WP head.
- `src/specify_cli/decisions/emit.py` and its live `_mission_dir` are out of
  scope (C-001); `_PRE_SPLIT_QUALNAMES` in
  `tests/architectural/test_no_write_side_rederivation.py` is a red-at-base
  mapping keyed off the census pair and stays as-is.
- No gate suppression, no allowlist additions (C-002). Never run a full heavy
  suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
- Classify any red against the merge base before chasing it (AGENTS.md
  baseline-red gotcha: pre-existing P0 reds, CI-environment failures,
  stale-install/stale-venv false reds are not yours; a pre-existing red with
  no tracker issue gets one filed, per the Pre-existing Failure Reporting
  Rule).

### Parallel Opportunities

- None; the package is strictly sequential (T001 → T002 → T003/T004 → T005 → T006).

### Dependencies

- None (starting package).

### Risks & Mitigations

- Hidden references beyond the surveyed set → repo-wide grep for
  `service._mission_dir` and `decisions.service import` plus the full module
  suites.
- Guard test over-constrains future legitimate reads → the guard asserts the
  standing invariant by file-scoped source contract; a future change that
  legitimately needs a read-side STATUS_STATE read updates the guard with
  rationale in the same PR.

---

## Dependency & Execution Summary

- **Sequence**: WP01 only.
- **Parallelization**: none.
- **MVP Scope**: WP01 is the whole mission.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red-first STATUS_STATE-access guard test | WP01 | P1 | No |
| T002 | Delete `_mission_dir` from service.py | WP01 | P1 | No |
| T003 | Re-point stale docstrings/comments | WP01 | P1 | No |
| T004 | Drop orphaned leniency pins + ledger docstring | WP01 | P1 | No |
| T005 | Changelog entry | WP01 | P1 | No |
| T006 | Validation surface run | WP01 | P1 | No |
