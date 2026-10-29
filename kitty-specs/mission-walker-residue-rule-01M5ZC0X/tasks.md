# Tasks: Mission walkers share one residue rule

**Mission**: `mission-walker-residue-rule-01M5ZC0X` · **Issue**: #5875 · **Topology**: `single_branch`
**Planning/base branch**: `issue-5875-mission-walker-is-mission-dir` · **Merge target**: `issue-5875-mission-walker-is-mission-dir`

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first selection tests for the new population rule | WP01 | |
| T002 | `is_selectable_mission_dir` + lazy per-walk tracked memo in `mission_resolver.py` | WP01 | |
| T003 | `list_missions_for_selection` filters through the predicate; docstrings (FR-008) | WP01 | |
| T004 | `_list_feature_spec_candidates` uses the same predicate (red-first test) | WP01 | |
| T005 | Update fixtures in other tests that relied on spec.md-only folders being listed | WP01 | |
| T006 | Tidy-first: shared `kitty-specs` child walk helper for the three doctor walkers (behaviour-preserving, own commit) | WP02 | |
| T007 | `residue` identity state: walk-level classification, `summarize`, collisions excluded | WP02 | |
| T008 | `doctor identity` renderer: residue row, section, remedy, JSON, `--fail-on` help | WP02 | |
| T009 | `doctor mission-type` skips residue | WP02 | |
| T010 | Red-first tests for T007–T009 | WP02 | |
| T011 | FR-007 parity case in `tests/context/test_is_mission_dir.py` | WP03 | |
| T012 | CHANGELOG `[Unreleased]` entry | WP03 | [P] |
| T013 | Docs: `doctor identity` states in `docs/api/cli-commands.md` and `docs/migrations/mission-id-canonical-identity.md` | WP03 | [P] |

## WP01 — Read-side predicate and Mission selection (P1)

**Goal**: selection and the agent-side candidates list a `kitty-specs/` child only when a `meta.json` exists on disk and `is_mission_dir` accepts it (FR-001, FR-002, FR-008, NFR-001).
**Independent test**: a fixture with one Mission plus a spec.md-only folder gives selection the Mission only, and the agent candidates agree.
**Prompt**: [tasks/WP01-selection-predicate.md](tasks/WP01-selection-predicate.md)

T001 Red-first selection tests for the new population rule (WP01)
T002 `is_selectable_mission_dir` + lazy per-walk tracked memo in `mission_resolver.py` (WP01)
T003 `list_missions_for_selection` filters through the predicate; docstrings (WP01)
T004 `_list_feature_spec_candidates` uses the same predicate (WP01)
T005 Update fixtures in other tests that relied on spec.md-only folders being listed (WP01)

**Dependencies**: none. **Risks**: test fixtures elsewhere that build spec.md-only Missions.

## WP02 — Doctor walkers: residue state and mission-type skip (P1)

**Goal**: `doctor identity` reports rejected children as `residue` with a remedy and leaves them out of the collision reports. `doctor mission-type` skips them (FR-003 to FR-006, NFR-002).
**Independent test**: `doctor identity --json` on the fixture shows `summary.residue == 1` and `--fail-on residue` exits 1. `audit_mission_types` returns only the Mission.
**Prompt**: [tasks/WP02-doctor-residue-state.md](tasks/WP02-doctor-residue-state.md)

T006 Tidy-first: shared walk helper (WP02)
T007 `residue` identity state (WP02)
T008 `doctor identity` renderer (WP02)
T009 `doctor mission-type` skips residue (WP02)
T010 Red-first tests for T007–T009 (WP02)

**Dependencies**: WP01 (it uses `is_selectable_mission_dir`). **Risks**: an additive JSON contract change, and the `#3194` unstattable-entry posture.

## WP03 — Parity test, changelog and docs (P2)

**Goal**: pin the parity invariant and record the behaviour change (FR-007, FR-009).
**Prompt**: [tasks/WP03-parity-and-docs.md](tasks/WP03-parity-and-docs.md)

T011 FR-007 parity case (WP03)
T012 CHANGELOG `[Unreleased]` entry (WP03)
T013 Docs for `doctor identity` states (WP03)

**Dependencies**: WP01, WP02.
