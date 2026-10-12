# Work Packages: Native stale-content refusal enforcement

**Inputs**: Design documents from `/kitty-specs/native-stale-content-refusal-01M4S2CQ/`
**Prerequisites**: plan.md (required), spec.md (user stories), grounding-note.md

**Tests**: Required (ATDD red-first) — the acceptance test is the contract.

**Organization**: One coherent work package. The fix is a single behaviour change across the
shared native completion surface (the marker-gated refusal now runs natively as it already does
on the orchestrator-api path), touching tightly-coupled files that share one test journey. Merging
the two concerns (IC-01 native `next`, IC-02 native finalize) into one WP avoids an artificial
ownership split of the shared `test_planning_client_journey.py` and the shared `design` seam.

## Subtask Format: `[Txxx] [P?] Description`

## Path Conventions

- **Single project**: `src/`, `tests/`.

---

## Work Package WP01: Native completion enforces the API-authored marker-gated refusal (Priority: P1) 🎯 MVP

**Goal**: Move the marker-gated `validate_stage` refusal onto the native completion surfaces —
`spec-kitty next --result success` (via the shared top-layer seam `next_cmd.next_step`) and the
native `agent … finalize-tasks` commands (via the existing `design.validation.finalization_scope`)
— with the orchestrator-api `_completion_gate` removed so there is a single canonical authority.
**Independent Test**: Red-first cases drive the native CLI against an API-authored Mission with
stale/unfinished content and assert the typed `DESIGN_*` refusal — RED on `origin/main`, GREEN on
the fix; non-API-authored Missions and the orchestrator-api journey stay byte-identical.
**Prompt**: `/tasks/WP01-native-completion-marker-gated-refusal.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003

### Included Subtasks

T001 Red-first: add a native `spec-kitty next --result success` stale-content refusal case to `tests/specify_cli/orchestrator_api/test_planning_client_journey.py` (RED on base)
T002 Red-first: add a native `agent … finalize-tasks` stale-content refusal case (RED on base)
T003 Implement the marker-gated completion gate in `src/specify_cli/cli/commands/next_cmd.py::next_step` (result==success, `api_authoring_enabled` + `issued_step_id_for_mission` → `validate_stage` under `authoring_lock`)
T004 Remove the now-redundant `_completion_gate`/`_run_governed` from `src/specify_cli/orchestrator_api/runtime_next.py` (single authority); preserve single-JSON stdout + `RUNTIME_NEXT_FAILED`/`data.reason` mapping
T005 Wrap native `agent mission finalize-tasks` / `agent tasks finalize-tasks` in `design.validation.finalization_scope` when `api_authoring_enabled` (enforces `validate_stage("tasks")`, acquires `authoring_lock`, success-gated receipt re-stamp)
T006 Update `tests/specify_cli/orchestrator_api/test_runtime_next.py` to reflect the gate relocation; add read-only + marker-gate unit assertions in `tests/specify_cli/design/test_design_authoring.py`
T007 Run targeted tests + specific architectural gate files; ruff/format/mypy clean

### Implementation Notes

- Seam placement is `next_cmd.next_step` (top layer), NOT the runtime bridge — `test_layer_rules.py` forbids `runtime → specify_cli.design`. See `grounding-note.md` §3 and C-001.
- Gate fires only for `result == "success"` and only when `api_authoring_enabled` (marker present); the validated stage is the native persisted `issued_step_id`, never a caller-supplied stage.
- `authoring_lock` is reentrant, so the api verb calling `next_step` in-process will not deadlock.

### Dependencies

- None (single WP, starting package).

### Risks & Mitigations

- Root resolution for the marker/receipts in `next_step` (git common dir vs owned checkout) → resolve the same way the rest of `next_step` resolves the mission; pin with tests.
- Dead-symbol gate after removing `_completion_gate` → update references/allowlist if needed.
- Merge-coordination with open PRs #5907 / #5945 on the finalize/runtime-bridge guard surface → keep the diff small, rebase late.

---

## Dependency & Execution Summary

- **Sequence**: WP01 only.
- **MVP Scope**: WP01 is the whole mission.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| FR-005 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red-first native `next` refusal case | WP01 | P1 | No |
| T002 | Red-first native finalize refusal case | WP01 | P1 | No |
| T003 | Gate in `next_cmd.next_step` | WP01 | P1 | No |
| T004 | Remove api `_completion_gate` | WP01 | P1 | No |
| T005 | Wrap native finalize in `finalization_scope` | WP01 | P1 | No |
| T006 | Update/extend tests | WP01 | P1 | No |
| T007 | Targeted tests + gates + lint/type | WP01 | P1 | No |
