# Tasks: Harden the mission-type capability contract

**Mission**: `mission-type-capability-hardening-01M6BTT4` · **Branch**: `issue-6330-run-dir-threading` (planning base and merge target)
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Failing test: a custom WP-driven family still gates when the planning dir name is not the mission handle, with `run_dir` threaded | WP01 | |
| T002 | Failing test: the production dispatch path (`_dispatch_via_composition`) forwards the caller's run directory | WP01 | |
| T003 | `gather_artifact_presence` + `_wp_driven_fact`: `run_dir` wins, explicit `mission_slug` fallback, no implicit `feature_dir.name` | WP01 | |
| T004 | Thread `run_dir` through `_check_cli_guards`, `_check_composed_action_guard`, `_dispatch_via_composition` and the `ctx` call sites | WP01 | |
| T005 | Repoint the existing wp_driven guard helper at the run it already holds; keep the non-WP-driven control green | WP01 | [P] |
| T006 | Failing test: a raising `requires_substantive_spec` resolution logs one WARNING and still returns the built-in default | WP02 | |
| T007 | Make the fail-open observable in `requires_substantive_spec_for` without changing the returned value | WP02 | |
| T008 | Failing parity test: a curated-away type reports DTO `wp_driven=False` while the guard gates from the frozen DAG | WP02 | |
| T009 | Document `ResolvedMissionType.wp_driven` as advisory; add the `[Unreleased]` changelog entry | WP02 | [P] |

## Phase 1 — Runtime fact (the fail-open)

### WP01 — Thread the run directory into the WP-driven fact

**Goal**: the `wp_driven` fact is decided by the run the caller already resolved; `feature_dir.name` is no longer a mission handle anywhere on this path. **Priority**: P1. **Prompt**: [tasks/WP01-run-dir-threading.md](tasks/WP01-run-dir-threading.md)
**Independent test**: `tests/runtime/test_wp_driven_guard.py` — a custom family whose planning directory is renamed away from the mission slug still returns the pending-WP guard failure, and the production dispatch path forwards the run.

T001 Failing test: a custom WP-driven family still gates when the planning dir name is not the mission handle, with `run_dir` threaded (WP01)
T002 Failing test: the production dispatch path (`_dispatch_via_composition`) forwards the caller's run directory (WP01)
T003 `gather_artifact_presence` + `_wp_driven_fact`: `run_dir` wins, explicit `mission_slug` fallback, no implicit `feature_dir.name` (WP01)
T004 Thread `run_dir` through `_check_cli_guards`, `_check_composed_action_guard`, `_dispatch_via_composition` and the `ctx` call sites (WP01)
T005 Repoint the existing wp_driven guard helper at the run it already holds; keep the non-WP-driven control green (WP01)

Dependencies: none. Risk: a hidden caller depends on the implicit fallback — mitigated by threading both production call sites in the same WP and the grep evidence in `research.md`.

## Phase 2 — Charter facet (observability and the advisory contract)

### WP02 — Observable substantive-gate fallback and the advisory `wp_driven` contract

**Goal**: a resolution failure for `requires_substantive_spec` is logged instead of silent, and the charter-vs-runtime split of authority for `wp_driven` is documented and pinned. **Priority**: P2. **Prompt**: [tasks/WP02-substantive-gate-observability.md](tasks/WP02-substantive-gate-observability.md)
**Independent test**: `tests/charter/test_resolved_mission_type_context.py` (the log assertion) and `tests/runtime/test_wp_driven_parity.py` (the curated-away fixture).

T006 Failing test: a raising `requires_substantive_spec` resolution logs one WARNING and still returns the built-in default (WP02)
T007 Make the fail-open observable in `requires_substantive_spec_for` without changing the returned value (WP02)
T008 Failing parity test: a curated-away type reports DTO `wp_driven=False` while the guard gates from the frozen DAG (WP02)
T009 Document `ResolvedMissionType.wp_driven` as advisory; add the `[Unreleased]` changelog entry (WP02)

Dependencies: none — it touches the charter activation module and its own test files, disjoint from WP01's runtime bridge files.

## Verification of the integrated diff

Not a work package: the review round over the combined diff runs the focused suites
(`tests/runtime/test_wp_driven_guard.py`, `tests/runtime/test_wp_driven_parity.py`,
`tests/charter/test_resolved_mission_type_context.py`,
`tests/runtime/test_artifact_presence_placement.py`,
`tests/runtime/next/test_cli_guard_family.py`, `tests/runtime/test_cli_guard_family.py`) and
proves non-vacuity by reverting each half of the fix in turn (the corresponding test must go
red each time).

## Parallelization

WP01 and WP02 own disjoint files (`src/runtime/next/*` + `tests/runtime/test_wp_driven_guard.py` versus `src/charter/activation/mission_type_profiles.py` + `tests/charter/*` + a new parity test module), so they run in parallel lanes; the combined diff is verified in the review round described above.

## MVP

WP01 alone closes the fail-open the issue is actually about; WP02 is the observability and contract-clarity half. Both are in scope for this mission.
