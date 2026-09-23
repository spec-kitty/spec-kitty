# Tasks: Arch/Perf Test-Guard Non-Vacuity Hardening

**Mission**: `test-guard-non-vacuity-hardening-01M37EW8` | **Branch**: `issue-4036-test-guard-non-vacuity-hardening`
**Issues**: #4036, #4105, #4210, #4388, #4408, #4536 — epic #4883

## Dependency Graph
```
WP01 (architectural guards: #4105 #4388 #4408)   — independent
WP02 (perf + support guards: #4210 #4536 #4036)  — independent
```
Both parallel (disjoint edit sets). Only WP02 edits `pytest.ini`/`ci-nightly.yml`; WP01's #4388 only READS `pytest.ini`.

## Subtask Index
| ID | Description | WP |
|----|-------------|----|
| T001 | #4105: frontmatter-scope `is_retired_doc`; drop `kitty-specs/` prefix; fix comment | WP01 |
| T002 | #4388: assert `pytest.ini` has no `python_files` override | WP01 |
| T003 | #4408: `_composite_action_path` normalize/reject `..` + containment check | WP01 |
| T004 | WP01 non-vacuity demos (one per finding, RED-on-base) | WP01 |
| T010 | #4210: additive real-tree walk (preserve pure fn sig) + marker-desc fix + env-scope invariant | WP02 |
| T011 | #4536: min-scanned-file floor + dynamic-import coverage + docstring fix | WP02 |
| T012 | #4036: window-scope the self-test assert + document xdist-straddle | WP02 |
| T013 | WP02 non-vacuity demos (one per finding, RED-on-base; #4036 must prove a real cross-window straddle) | WP02 |

Completion: `spec-kitty agent tasks mark-status Txxx --status done`.

## WP01 — architectural census/coverage guards (#4105 #4388 #4408)
- **Goal**: three disjoint `tests/architectural/` guards go vacuous→discriminating. **Prompt**: [tasks/WP01-architectural-guards.md](./tasks/WP01-architectural-guards.md)
- **Deps**: none. **Requirement refs**: FR-002, FR-004, FR-005, NFR-001, C-001, C-002.

## WP02 — perf + support guards (#4210 #4536 #4036)
- **Goal**: perf-marker + startup-budget + repo-root status guards go vacuous→discriminating (test-infra only). **Prompt**: [tasks/WP02-perf-support-guards.md](./tasks/WP02-perf-support-guards.md)
- **Deps**: none. **Requirement refs**: FR-001, FR-003, FR-006, NFR-001, NFR-003, C-001, C-002, C-003.

## MVP
Either WP alone is a shippable dent; together they close the 6-finding non-vacuity slice.
