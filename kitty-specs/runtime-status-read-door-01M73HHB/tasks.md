# Work Packages: Runtime status readers through the read door

**Inputs**: Design documents from `kitty-specs/runtime-status-read-door-01M73HHB/`
**Prerequisites**: plan.md, spec.md, research.md (R-1 to R-8), data-model.md, contracts/next-materialization-report.md, quickstart.md, research/ (grounding notes and repro scripts)

**Tests**: required. Every behaviour change lands red-first (C-002); the tidy-first WPs carry characterisation and parity tests.

**Organization**: subtasks (`Txxx`) roll up into six work packages. Record subtask completion with `spec-kitty agent tasks mark-status <Txxx> --status done`. These rows are references, not checkboxes.

**Gate ledger** (single-door allowlist, `tests/architectural/test_status_read_single_door.py` + `tests/architectural/_baselines.yaml`): it starts at 41 entries and 42 live hits. Each WP that removes an entry also lowers `_LIVE_HIT_FLOOR` and the baseline count in the same commit. End state: 33 entries, 33 hits.

| After | Entries | Live hits |
|---|---|---|
| WP01-WP03 | 41 | 42 |
| WP04 | 37 | 38 |
| WP05 | 34 | 34 |
| WP06 | 33 | 33 |

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files).

---

## Work Package WP01: Board status value and parity (Priority: P1)

**Goal**: add one immutable board-status value, built once from a status read door surface (lanes, per-WP states, log present, weighted progress, source), with a parity test proving it matches today's readers on every real log. No call site changes (tidy-first).
**Independent Test**: `tests/runtime/next/test_board_status.py` passes. It covers the builder on path and ref surfaces, parity with `get_all_wp_lanes` / `materialize_snapshot` across every `kitty-specs/*/status.events.jsonl`, and corrupt-line behaviour.
**Prompt**: `tasks/WP01-board-status-value.md`
**Requirement Refs**: FR-008, NFR-001, NFR-002, C-001, C-003

### Included Subtasks

T001 Define the frozen BoardStatus value in a new module `src/runtime/next/board_status.py`
T002 Build it from a door surface in one read and one reduction (`board_status_from_surface`)
T003 Path adapter `board_status_from_dir` for the outside callers and tests (same reduction)
T004 [P] Parity test over every repo status log: lanes and weighted % equal today's readers
T005 [P] Edge tests: no log, empty log, corrupt line (lanes raise, weighted degrades), ref surface

### Dependencies

- None.

### Risks & Mitigations

- Reducer parity: `materialize_snapshot` reduces through `reduce_shared_state`. The parity test is the guard (research R-2).

---

## Work Package WP02: Door finds owned coordination Missions; ADR amendment (Priority: P1)

**Goal**: `resolve_status_read(owned=...)` for a coordination topology locates the Mission and its `meta.json` through the owned checkout, and probes coordination state under the repository root. A Mission that exists only in the owned checkout resolves. ADR `2026-11-06-2` is amended for DM-1 (query and progress read the committed branch; an advancing dispatch refuses).
**Independent Test**: new red-first tests in `tests/status/test_read_surface_owned_coordination.py`. An owned-only coordination Mission resolves through the door (red today); materialized, empty and unmaterialized give `coord_worktree` / `coord_branch_ref` / `coord_branch_ref`; deleted still raises.
**Prompt**: `tasks/WP02-door-owned-coordination-entry.md`
**Requirement Refs**: FR-007, FR-012, C-001, C-002

### Included Subtasks

T006 Red test: owned-only coordination Mission resolves through `resolve_status_read(owned=)`
T007 Thread the owned PRIMARY anchor through the door's decision for coordination topologies
T008 [P] Tests for the owned coordination states (materialized, empty, unmaterialized, deleted, landed)
T009 ADR `2026-11-06-2` amendment: DM-1 split (query and progress read the ref; dispatch refuses)
T010 Run the door's own suites (`tests/status/`) and record counts

### Dependencies

- None (can run beside WP01).

---

## Work Package WP03: Board helpers accept the board status (Priority: P1)

**Goal**: the board and progress helpers in `discovery.py` and `decision.py` take the board-status value (`board=`), with their `status_dir=` / Path forms kept as thin adapters that build a board through WP01's adapter. Behaviour is unchanged and no call site changes (tidy-first).
**Independent Test**: existing helper suites pass unchanged (`tests/next/test_decision_unit.py`, `tests/next/test_next_claimable_payload.py`, `tests/integration/test_next_preview_primary_routing.py`, `tests/specify_cli/status/test_progress_integration.py`), and new tests prove `board=` and Path forms agree on the same fixture.
**Prompt**: `tasks/WP03-board-helpers-take-board.md`
**Requirement Refs**: FR-008, NFR-001, NFR-004, C-003

### Included Subtasks

T011 `preview_claimable_wp` / `_load_wp_states` accept `board=` (discovery.py); Path form adapts
T012 `_compute_wp_progress` / `_find_first_wp_by_lane` / `_get_wp_lanes` accept `board=` (decision.py); Path form adapts
T013 Weighted progress comes from the board (no second `materialize_snapshot` read on the board path)
T014 [P] Equivalence tests: `board=` vs Path on the same fixtures, including genesis and corrupt-log behaviour
T015 Run the helper suites and record counts

### Dependencies

- Depends on WP01.

---

## Work Package WP04: Board and query read the door; fixes #7507 (Priority: P1) 🎯 MVP

**Goal**: `_resolve_wp_board_action`, `query_current_state` and `_build_finalized_override_query_decision` read the door once per decision and pass the board status to every helper. The unmaterialized block is decided from the surface source, and the owned policy follows DM-1. #7507 is fixed red-first. Allowlist 41 → 37.
**Independent Test**: a new red-first test proves `query_current_state` on an empty or unmaterialized coordination worktree reports WP01 next, 1 planned / 1 for review, 30.0%. The board selector's named block for direct callers is unchanged. The gate passes at 37.
**Prompt**: `tasks/WP04-board-and-query-read-the-door.md`
**Requirement Refs**: FR-001, FR-002, FR-005, FR-006, FR-008, FR-011, NFR-003, C-002, SC-001, SC-004

### Included Subtasks

T016 Red test: #7507 cells through `query_current_state` and the board selector (empty, unmaterialized; materialized control)
T017 Red test: owned coordination query reads the committed branch (empty, unmaterialized); owned dispatch keeps `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`
T018 `decision_mapping.py`: one door read in `_resolve_wp_board_action`; the helpers there take `board=`; block from surface source
T019 `runtime_bridge_query.py`: `query_current_state` and the finalized-override query read the door once
T020 Re-pin the mechanism pins this move makes stale (named list), keeping their domain assertions
T021 Gate: remove the 4 entries; floor 42 → 38, baseline 41 → 37
T022 Run the board/query/owned suites + gate and record counts

### Dependencies

- Depends on WP02, WP03.

---

## Work Package WP05: Explicit placement seam for artifact presence; bootstrap reads the door (Priority: P2)

**Goal**: `gather_artifact_presence` / `guard_failure_artifact_paths` receive the placement seam instead of reverse-mapping a status directory. `_with_guard_failure_paths` passes it. `_dn_bootstrap` takes its Mission directory from PRIMARY metadata and its board from the door, read after the decision-log wrap, so advancing progress is true. Allowlist 37 → 34.
**Independent Test**: guard-failure paths are unchanged on every existing fixture; owned O8 refusals are unchanged; advancing `next` on an empty or unmaterialized coordination worktree reports the real progress (red-first). The gate passes at 34.
**Prompt**: `tasks/WP05-explicit-seam-and-bootstrap.md`
**Requirement Refs**: FR-001, FR-006, FR-010, FR-011, NFR-003, C-002

### Included Subtasks

T023 Characterisation: pin today's guard-failure paths and artifact-presence answers (non-owned, owned, coordination)
T024 `runtime_bridge_io.py`: `gather_artifact_presence` / `guard_failure_artifact_paths` take `seam=`; remove `_artifact_presence_seam`
T025 Callers pass the seam: `runtime_bridge.py`, `runtime_bridge_composition.py`, `acceptance/non_wp_runtime.py`, and `decision._with_guard_failure_paths` (out-of-map edit)
T026 Red test, then fix: `_dn_bootstrap` reads the door after the wrap; advancing progress true for empty and unmaterialized; owned arm keeps O8
T027 Gate: remove 3 entries; floor 38 → 34, baseline 37 → 34 (out-of-map gate edit)
T028 Run the bootstrap/presence/owned suites + gate and record counts

### Dependencies

- Depends on WP04.

---

## Work Package WP06: MissionNextInvoked via the write seam; report the bootstrap materialization (Priority: P2)

**Goal**: the `MissionNextInvoked` row is written through the status write seam, proven by a read-after-write test. An advancing `next` whose bootstrap materialized or restored the coordination worktree reports it in one line and with `remediation` in `--json` (contract `next-materialization-report.md`). Allowlist 34 → 33.
**Independent Test**: red-first tests show the report on empty and unmaterialized cells, and its absence on materialized, query and deleted-branch runs. The `MissionNextInvoked` row is readable after the write. The gate passes at 33.
**Prompt**: `tasks/WP06-lifecycle-write-and-materialization-report.md`
**Requirement Refs**: FR-003, FR-004, FR-009, FR-011, C-004, C-005, C-006, SC-002, SC-003, SC-005

### Included Subtasks

T029 Red test, then fix: `emit_mission_next_invoked` writes through the write seam (read-after-write, coordination cells)
T030 Red test: advancing `next` reports the materialization (line + JSON) on empty and unmaterialized worktrees
T031 Detect the bootstrap materialization in the decision-log wrap and carry it on the decision
T032 Render: one human line in `next_cmd.py`; `remediation` key in `Decision.to_dict` (out-of-map edit), only when set
T033 [P] Negative tests: materialized, query mode, deleted branch, non-coordination Mission never report
T034 Gate: remove the last runtime entry; floor 34 → 33, baseline 34 → 33 (out-of-map gate edit); `make test-fast`

### Dependencies

- Depends on WP05.
