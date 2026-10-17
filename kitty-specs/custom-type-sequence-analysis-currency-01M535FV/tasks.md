---
description: "Work package task list for custom-type action-sequence + analysis-currency (Slice 1 of #4983)"
---

# Work Packages: Custom-type action-sequence + analysis-currency generalization

**Inputs**: Design documents from `/kitty-specs/custom-type-sequence-analysis-currency-01M535FV/`
**Prerequisites**: plan.md (required), spec.md (user stories)

**Tests**: Red-first per WP (ATDD-first). One focused test per behaviour (`DIRECTIVE_041`); NFR-001 golden-parity tests are the ratchet, kept green.

**Organization**: Two sibling-disjoint work packages, sequenced WP01 → WP02.

## Path Conventions

- **Single project**: `src/`, `tests/`

---

## Work Package WP01: Custom-type action_sequence resolves from the runtime-DAG shape (Priority: P0)

**Goal**: An activated org-pack-shape custom mission type resolves its full ordered `action_sequence` from its own `missions/<type>/mission-runtime.yaml` steps, via a charter-local reader feeding the existing projection.
**Independent Test**: An activated custom type that ships only `missions/<type>/mission-runtime.yaml` + a bare `mission_types/<type>.yaml` resolves `action_sequence` equal to its declared step list in order; an empty/malformed runtime still raises `MissionTypeEmptyActionSequenceError`; built-in types are byte-identical.
**Prompt**: `/tasks/WP01-custom-type-action-sequence.md`
**Requirement Refs**: FR-001, FR-002, NFR-001, NFR-002, C-001, C-003, SC-001

### Included Subtasks

T001 Add a charter-local runtime-shape step reader in `charter.offering.missions` that parses `missions/<type>/mission-runtime.yaml` (`steps:` → id + declared order) and synthesizes `MissionStep` objects with `in_action_sequence=True`, `sequence_index=<enumerate position>`. Plain YAML parse only — no import of `runtime` (layer chain).
T002 In `mission_type_repository.py::_inject_projected_fields`, fall back to `project_action_sequence(reader(...))` when the dir-per-step projection is empty AND `raw` has no authored `action_sequence`; keep the final `or raw.get("action_sequence")` fallback and the empty→`None` fail-closed path.
T003 [P] Red-first tests in `tests/charter_offering/missions/` for the populated-runtime positive case + the empty/malformed fail-closed control + a built-in no-regression assertion.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Must never fire for built-ins (their dir-per-step projection is non-empty) → assert built-in parity. Charter must not import `runtime` → direct ruamel.yaml parse of id+order only.

---

## Work Package WP02: Analysis-currency gate generalized to any analyze-declaring family (Priority: P0)

**Goal**: For any mission whose resolved runtime DAG declares an `analyze` step, recompute analysis currency at `analyze` and re-issue `analyze` before `implement` on a stale/missing report — decide path and preview path — keyed on the DAG step SET, never `action_sequence` membership.
**Independent Test**: An analyze-declaring non-`software-dev` family computes the currency fact at `analyze` and re-issues `analyze` on a stale report (decide + preview); a no-analyze family is never sent to `analyze`; software-dev/research/documentation/plan decisions are byte-identical.
**Prompt**: `/tasks/WP02-analysis-currency-generalization.md`
**Requirement Refs**: FR-003, FR-004, FR-005, NFR-001, NFR-003, C-002, C-003, SC-002, SC-003

### Included Subtasks

T004 Add `mission_declares_analyze_step(run_dir) -> bool` in `runtime_bridge_cores.py` = `ANALYZE_STEP_ID in {s.id for s in <frozen template>.steps}` (load via the existing frozen-template loader).
T005 `runtime_bridge_io.py:1543` — drop the family clause → `if step_id == ANALYZE_STEP_ID:` (the step is only issued when the runtime declares it).
T006 `runtime_bridge.py:652` (decide path) — replace `ctx.mission_type == MISSION_TYPE_SOFTWARE_DEV` with `mission_declares_analyze_step(ctx.run_dir)`.
T007 `runtime_bridge_query.py:144` (preview path) — same predicate; thread `run_ref.run_dir` into `_build_finalized_override_query_decision`.
T008 [P] Add an analyze-declaring non-software-dev custom scaffold in `tests/runtime/_next_mission_scaffold.py`; red-first tests in `tests/runtime/test_analyze_step.py` for the fact (site 1), decide reissue (site 2), preview reissue (site 3), each with a no-analyze control; keep `test_runtime_seam.py` / `test_next_board_authority.py` green (NFR-001).

### Dependencies

- WP01 (an analyze-declaring custom family must resolve end-to-end for the scaffold).

### Risks & Mitigations

- Key on the DAG step SET, not `action_sequence` (software-dev's sequence has no `analyze` → keying on the sequence would silently drop the gate for the one family that has it). Verified only software-dev declares `analyze` among built-ins → byte-identical for the other three.
