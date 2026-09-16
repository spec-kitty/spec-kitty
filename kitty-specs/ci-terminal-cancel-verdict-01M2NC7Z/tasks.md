# Tasks: CI Terminal-Cancel Verdict (infra-error)

**Mission**: `ci-terminal-cancel-verdict-01M2NC7Z` · **Branch**: `fix/ci-terminal-cancel-verdict`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md)

2 WPs, 2 parallel lanes. Subtask completion is event-sourced (`spec-kitty agent tasks mark-status Txxx --status done`); rows are reference rows.

## Subtask Index
| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first classify precedence + release tests (INV-1..5 + full report() strand pin + flips) | WP01 | |
| T002 | Implement infra-error branch (all-completed AND any-cancelled) | WP01 | |
| T003 | comment_body infra-error line + docstring | WP01 | |
| T004 | Migrate test_fleet_main.py (cancelled→infra-error + no P0) | WP01 | |
| T005 | 4a gates (pytest, ruff, format, mypy, terminology) | WP01 | |
| T006 | Red-first stale-running detector tests | WP02 | [P] |
| T007 | Implement find_stale_running + gh-edge main() | WP02 | [P] |
| T008 | New ci-stale-running-sweep.yml (schedule + dispatch, least-priv) | WP02 | [P] |
| T009 | 4b wiring guard + gates (pytest, ruff, format, mypy, actionlint) | WP02 | [P] |

## Work Packages

### WP01 — 4a: infra-error terminal-cancel class
- **Goal**: `classify` gains `infra-error` (releases the head, never-green, never-premature); main coherence free; honesty line + docstring.
- **Priority**: P1 (MVP) · **Prompt**: [tasks/WP01-infra-error-classify.md](./tasks/WP01-infra-error-classify.md) (~200 lines)
- **Requirements**: FR-001..006, FR-009, NFR-001/002/003; C-001/C-002/C-004
- **Subtasks**: T001–T005 · **Independent test**: `pytest tests/ci/test_fleet_verdict.py tests/ci/test_fleet_main.py` — release proven via full report(); invariants green.
- **Dependencies**: none · **Owns**: `scripts/ci/fleet_verdict.py`, `tests/ci/test_fleet_verdict.py`, `tests/ci/test_fleet_main.py`
- **Risks**: precedence premature-fire; never-green; fakeable release test.

### WP02 — 4b: reactive stale-running sweep backstop
- **Goal**: scheduled sweep detects "latest running but runs terminal" and surfaces an idempotent `[ci-sweep]` watch item; never auto-releases.
- **Priority**: P2 · **Prompt**: [tasks/WP02-stale-running-sweep.md](./tasks/WP02-stale-running-sweep.md) (~180 lines)
- **Requirements**: FR-007/008, FR-009, NFR-003/004; C-003
- **Subtasks**: T006–T009 · **Independent test**: `pytest tests/ci/test_stale_running_sweep.py` — detector red-first + wiring guard.
- **Dependencies**: none (imports fleet_verdict read-only; disjoint write-scope) · **Owns**: `scripts/ci/stale_running_sweep.py`, `tests/ci/test_stale_running_sweep.py`, `.github/workflows/ci-stale-running-sweep.yml`
- **Risks**: authority creep (must never release/verdict/re-trigger); false watch items; idempotency.

## Parallelization
WP01 ∥ WP02 — disjoint write-scopes → two lanes, fully parallel.

## MVP
WP01 (4a) is the MVP: it releases the head in-CI and closes #4430's strand class. WP02 (4b) is the backstop for cases where no reporter fired.
