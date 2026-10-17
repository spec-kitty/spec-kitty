# Tasks: Owned issue-verdict authority (#6320)

**Mission**: `owned-issue-verdict-authority-01M55KGY`
**Topology**: `single_branch` (WPs run sequentially in the write checkout)
**Planning base / merge target**: `kitty-base-6320`

Subtask completion is event-sourced — record with
`spec-kitty agent tasks mark-status Txxx --status done`. The rows below are references, not checkboxes.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Thread `owned` through `resolve_write_target_or_degrade` | WP01 | |
| T002 | Owned-aware `_mission_meta_exists` | WP01 | |
| T003 | Owned param on `assert_coord_write_materialized` + `establish_coord_write_location` passthrough | WP01 | |
| T004 | Owned passthrough on `resolve_for_write` | WP01 | |
| T005 | Red-first unit test: owned-only mission resolves; unresolved owned fact still refuses | WP01 | |
| T006 | Byte-identity test for the 3 unrelated gate callers | WP01 | |
| T007 | Add `--owned-checkout` option to `issue_verdict_command` | WP02 | |
| T008 | Resolve ownership once in `do_issue_verdict`; pass owned to the gate call | WP02 | |
| T009 | Thread owned through `_resolve_write_dir` | WP02 | |
| T010 | Thread owned through the coord-owned read + migration path | WP02 | |
| T011 | Forward owned into `write_issue_matrix` | WP02 | |
| T012 | Red-first integration test (owned `--owned-checkout` + flagless adoption + fail-closed control) | WP02 | |
| T013 | p0-repro test (`p0_repro(issue=6320)`) | WP02 | |
| T014 | Changelog Fixed entry for #6320 | WP03 | |
| T015 | Document `issue-verdict --owned-checkout` in agent-subcommands.md | WP03 | |

## Work Packages

### WP01 — Write-target gate owned-awareness

- **Goal**: Make the fail-closed write-target gate (`mission_runtime.write_target_degrade` + `coordination.surface_resolver.resolve_for_write`) recognize an owned-only mission given the owned fact, keeping its three unrelated callers byte-identical.
- **Priority**: P1 (foundation). **Dependencies**: none.
- **Requirements**: FR-002, FR-005, NFR-001, NFR-002.
- **Independent test**: unit tests in `tests/mission_runtime/test_write_target_degrade_owned_6320.py`.
- **Subtasks**: T001, T002, T003, T004, T005, T006.
- **Prompt**: `tasks/WP01-write-target-gate-owned-awareness.md`.

### WP02 — issue-verdict command wiring, coord-owned read path, and red-first proof

- **Goal**: Wire `--owned-checkout` into `issue-verdict`, resolve ownership once (mirror #6023), and thread the owned fact through resolution, the write dir, the coord-owned read/migration path, and the locked writer.
- **Priority**: P1
- **Dependencies**: WP01
- **Requirements**: FR-001, FR-003, FR-004, FR-006, NFR-001, C-001, C-002, C-003.
- **Independent test**: `tests/integration/test_owned_issue_verdict_authority_6320.py` (+ p0-repro).
- **Subtasks**: T007, T008, T009, T010, T011, T012, T013.
- **Prompt**: `tasks/WP02-issue-verdict-command-and-read-path.md`.

### WP03 — Deliverable hygiene: changelog + CLI reference

- **Goal**: Record the user-facing change (changelog) and document the new CLI option.
- **Priority**: P2
- **Dependencies**: WP02
- **Requirements**: SC-001, SC-002.
- **Independent test**: changelog-style + docs-freshness gates.
- **Subtasks**: T014, T015.
- **Prompt**: `tasks/WP03-deliverable-hygiene.md`.

## MVP

WP01 + WP02 deliver the headline capability (owned verdict recorded). WP03 is deliverable hygiene.
