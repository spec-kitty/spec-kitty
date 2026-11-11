# Tasks: Coordination doctor scope and decisions runtime lock hygiene

**Mission**: doctor-scope-lock-hygiene-01M75NSF · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red tests: `--fix` scope refusal, `--mission` scoping (incl. strand), branch-only discovery | WP01 | |
| T002 | `--all-missions` option, scope gate, conflict refusal | WP01 | |
| T003 | Scope the stranded-revert check/fixer to `--mission` | WP01 | |
| T004 | Discovery records: coord-worktree-held + branch-only Missions (placement seam reader) | WP01 | |
| T005 | Remedy strings name `--mission`; existing tests updated; walker allowlist drain | WP01 | |
| T006 | Red tests: lock excluded after a real decision write; `spec-commit` naming the lock refuses; label words | WP02 | [P] |
| T007 | Ensure the common-dir `info/exclude` pattern before acquiring the decisions lock | WP02 | [P] |
| T008 | `safe_commit` path policy refuses staging the lock (index-only removal exempt) | WP02 | [P] |
| T009 | Reset-obstruction label in words | WP02 | [P] |
| T010 | Lane / coordination worktree pins (#7498 gap 1 and 2) | WP02 | [P] |

## WP01 – `doctor coordination` acts only on the Missions named (#7552)

- **Goal**: FR-001..FR-007. **Priority**: P1. **Independent test**: two-Mission fixture; `--fix --mission A` leaves B
  byte-identical; branch-only Mission found and materialized.
- **Prompt**: [tasks/WP01-doctor-coordination-scope.md](tasks/WP01-doctor-coordination-scope.md)
- **Dependencies**: none

T001 Red tests: `--fix` scope refusal, `--mission` scoping (incl. strand), branch-only discovery (WP01)
T002 `--all-missions` option, scope gate, conflict refusal (WP01)
T003 Scope the stranded-revert check/fixer to `--mission` (WP01)
T004 Discovery records: coord-worktree-held + branch-only Missions (placement seam reader) (WP01)
T005 Remedy strings name `--mission`; existing tests updated; walker allowlist drain (WP01)

## WP02 – The decisions runtime lock is never dirt and never committed (#7498)

- **Goal**: FR-008..FR-011. **Priority**: P1. **Independent test**: after a real decision write, `git status` lists no
  lock in any checkout role; `spec-commit` naming the lock refuses and commits nothing.
- **Prompt**: [tasks/WP02-decisions-runtime-lock-hygiene.md](tasks/WP02-decisions-runtime-lock-hygiene.md)
- **Dependencies**: none

T006 Red tests: lock excluded after a real decision write; `spec-commit` naming the lock refuses; label words (WP02)
T007 Ensure the common-dir `info/exclude` pattern before acquiring the decisions lock (WP02)
T008 `safe_commit` path policy refuses staging the lock (index-only removal exempt) (WP02)
T009 Reset-obstruction label in words (WP02)
T010 Lane / coordination worktree pins (#7498 gap 1 and 2) (WP02)

## Parallelism

WP01 and WP02 share no file and can run in parallel.
