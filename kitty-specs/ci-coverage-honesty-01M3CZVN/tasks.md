# Tasks: CI Coverage Honesty

**Mission**: ci-coverage-honesty-01M3CZVN | **Branch**: feat/ci-coverage-honesty → main (PR)

Ownership is file-disjoint. The registry (`.github/ci-module-registry.yml`) is owned by exactly one WP (WP02) to avoid parallel-edit collisions; `ci-nightly.yml` by WP03; `release.yml` by WP04. **Green-at-baseline (revised per F17, supersedes red-first):** WP01 lands the guards GREEN at a committed measured baseline; WP02 SHRINKS that baseline via enrolment. No red guard ever reaches `main` (D9). Landing all WPs in one squashed PR is still tidy but no longer a correctness requirement.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Shared guard lib: import-under-root walk on ast_analysis primitives | WP01 | |
| T002 | foreign-coverage guard (per-root floor + baseline ratchet, non-src exempt) | WP01 | |
| T003 | src-reachability guard (fs-walk subpackages + loose modules; exclude data dirs) | WP01 | |
| T004 | phantom-mirror fix in test_gate_selection_authority (default tests/{module} + EXISTS) | WP01 | |
| T005 | seed baseline sidecar with current measured own-root ratios | WP01 | |
| T006 | unit tests for the shared guard lib | WP01 | |
| T007 | agent row: add real own-root test_dir tests/specify_cli/agent_utils | WP02 | |
| T008 | enrol tests/specify_cli/live_work into an existing in-matrix row (no dedicated row); remove out_of_matrix entry | WP02 | |
| T009 | re-measure host row shard timings (capture_shard_timings --module core_misc --write) | WP02 | |
| T010 | enrol dark pkgs (config/calibration/tasks_authoring/bootstrap) into rows; diagnostics = recorded debt | WP02 | |
| T011 | retire dead integration_tests_next tier + repoint test_module_shard_registry guard | WP03 | |
| T012 | update baseline (shrink by 5) + re-run guards/authority/shard-registry green | WP02 | |
| T013 | nightly integration+next lane job (if:always run-all-regardless, dir-based) | WP03 | |
| T014 | add lane to nightly-summary.needs | WP03 | |
| T015 | nightly_escalation.py (open/update/close deduped P0; token-absent degrade) | WP03 | |
| T016 | wire escalation step into each nightly run-all-regardless suite | WP03 | |
| T017 | unit tests for nightly_escalation | WP03 | |
| T018 | release_nightly_gate.py (resolve tag→sha, query/dispatch-by-tag/poll, fail-closed) | WP04 | |
| T019 | release.yml nightly-gate job + build-release needs + actions:write perms | WP04 | |
| T020 | unit tests for release_nightly_gate | WP04 | |

## Work Packages

### WP01 — Coverage-honesty guards + authority fix (green-at-baseline)
- **Goal**: Add the two enforced invariants (foreign-coverage baseline ratchet; src-reachability truly-dark floor + in-matrix-dark baseline) and fix the phantom-mirror authority bug. Guards land GREEN at a committed measured baseline; WP02 shrinks it.
- **Priority**: P1 (foundation) | **FRs**: FR-001, FR-002, FR-003, NFR-002
- **Independent test**: `pytest tests/architectural/test_foreign_coverage_guard.py test_src_reachability_guard.py test_gate_selection_authority.py test_pyproject_shape.py` all GREEN at baseline; negative unit tests prove a new dark package/root fails.
- **Subtasks**: T001–T006
- **Dependencies**: none
- **Risks**: guard speed (NFR-002) — scope scan to resolved dirs; authority test must stay green (C-002).
- Est. ~450 lines.

### WP02 — Registry enrolment (shrinks the baseline)
- **Goal**: Enrol agent_utils dir (ratchet), enrol live_work + 4 dark packages into existing in-matrix rows, re-measure host-row timings, and shrink the baseline by 5 — all within registry+timings+baseline scope. (Dedicated live_work row + tier retirement moved out; diagnostics = recorded debt.)
- **Priority**: P1 | **FRs**: FR-004, FR-005, FR-009, NFR-001, NFR-003
- **Independent test**: after WP02, WP01's guards + `test_module_shard_registry.py` + `test_gate_selection_authority.py` GREEN with the shrunk baseline; guards would fail if the baseline still listed the 5 enrolled packages.
- **Subtasks**: T007, T008, T009, T010, T012
- **Dependencies**: WP01
- **Risks**: no double-run (live_work must leave out_of_matrix same change); measured shard_count (NFR-001).
- Est. ~400 lines.

### WP03 — Nightly integration+next lane + red→P0 escalation
- **Goal**: Run tests/integration + tests/next on the nightly (run-all-regardless); a red suite fails loudly AND opens/updates a deduped priority:P0 issue (closes on green).
- **Priority**: P1 | **FRs**: FR-006, FR-007, NFR-004, NFR-005
- **Independent test**: `pytest tests/ci/test_nightly_escalation.py` green (create/update/close/degrade); nightly lane job present + in nightly-summary.needs.
- **Subtasks**: T011, T013–T017 (T011 = retire dead tier + repoint its guard, lands with the replacement lane)
- **Dependencies**: WP02
- **Risks**: fail-closed token-absent degrade (C-005); measure integration via pytest --durations (tool can't shard non-row dir).
- Est. ~400 lines.

### WP04 — Release gates on green nightly
- **Goal**: release.yml dispatches ci-nightly by the release tag (dedicated actions:write token) and blocks build/publish until green for the exact SHA.
- **Priority**: P1 | **FRs**: FR-008, C-005
- **Independent test**: `pytest tests/ci/test_release_nightly_gate.py` green (green-exists/dispatch-green/dispatch-red/in-flight/token-absent).
- **Subtasks**: T018–T020
- **Dependencies**: WP03 (nightly lane exists)
- **Risks**: workflow_dispatch by tag not SHA; GITHUB_TOKEN won't trigger nested run — needs RELEASE_NIGHTLY_DISPATCH_TOKEN (operator prerequisite, call out in PR body).
- Est. ~350 lines.

## Sequencing

```
WP01 (guards RED) → WP02 (registry greens them) → WP03 (nightly lane+escalation) → WP04 (release gate)
```
Linear dependency chain (registry is a single-owner coordination point). MVP = WP01+WP02 (the coverage-honesty invariants + enrolment).
