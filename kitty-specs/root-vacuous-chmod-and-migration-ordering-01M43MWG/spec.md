# Mission Specification: Root-vacuous chmod tests + TestOrdering isolation

**Mission Branch**: `claude/happy-rubin-aq1qc6`
**Created**: 2026-10-04
**Status**: Draft
**Input**: Operator brief: deliver #5654 and #5186 as one small governed mission (the WP04 slice of canceled mission `friction-remediation-01M43DRV`).

## Context

Two P3 test-quality defects:

- **#5654.** Some tests make a path unwritable with `chmod`. Root ignores mode bits, so as uid 0 such a test can pass while its refusal branch never runs. Mission `regression-slice-cleanup-01M42WCF` (PR #5656) added `tests/_support/eacces.py` (`deny_open_in`, `deny_path_method`) to inject `PermissionError` at the I/O seam instead.
  - The three read-only `.gitignore` sites the issue names are **not** vacuous as root. `write_gitignore_text` checks the owner-write mode bit explicitly, so the refusal fires for every uid. This mission records a planted-break proof and changes no test.
  - The encoding-sanitizer and mission-events sites already inject at the seam on `main` (commit `e5831e7c`). This mission records a planted-break proof for each.
  - `tests/specify_cli/readiness/test_upgrade_ux_migration.py::TestStoreUnreachable` is vacuous. It makes a directory `0o555` and asserts only that the runner "returns normally". As root the history write succeeds, so the best-effort branch is never exercised.
  - Campsite: `GitignoreManager._atomic_write` has no caller in `src/`. Two tests still name it.
- **#5186.** `TestOrdering` in `tests/specify_cli/upgrade/migrations/test_provision_kitty_env.py` asserts that `3.2.7_heal_provenance_paths` is registered. The module never imports that migration, so the test passes only when an earlier test in the same process registered it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Denied-write tests bite for every uid (Priority: P1)

A maintainer runs the suite as root (CI containers, cloud sessions). Every denied-write test exercises the refusal branch it names, so a regression that swallows the error turns the test red.

**Why this priority**: A test that passes vacuously as root hides real regressions in the error paths it claims to cover.

**Independent Test**: Plant a break in the product's error handling, run the test as root, and see it go red. Revert the break.

**Acceptance Scenarios**:

1. **Given** the history-db open is denied at the seam, **When** the upgrade runner runs, **Then** it returns normally, records no history row, and the denial reached the handled branch.
2. **Given** `write_gitignore_text`'s mode check is removed, **When** the three read-only `.gitignore` tests run as root, **Then** all three fail.

### User Story 2 - TestOrdering is order-independent (Priority: P1)

A maintainer runs `TestOrdering` alone, with `-p no:randomly`, or after a test that calls `MigrationRegistry.clear()`. It passes every time and still pins "both migrations registered exactly once".

**Independent Test**: `pytest ...test_provision_kitty_env.py::TestOrdering -p no:randomly` is green on its own.

### Edge Cases

- A test that runs earlier calls `MigrationRegistry.clear()`. A top-level import is not enough because a cleared registry stays cleared. The fixture must rediscover each time the class runs.
- `auto_discover_migrations()` called twice must not raise a duplicate-ID error. Its reload path handles that.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | History-db denial injected at the seam | As a maintainer, I want `TestStoreUnreachable` to deny the history-db open at the seam and assert the handled path, so that it is not vacuous as root. | High | Open | [build] | no — red against a planted break that stops swallowing the store error |
| FR-002 | Read-only gitignore sites proven non-vacuous | As a maintainer, I want a recorded planted-break proof that the three read-only `.gitignore` tests go red as root, so that no needless conversion lands. | Medium | Open | [folded] | yes — proof only, recorded in the PR; no test change |
| FR-003 | Already-converted sites proven non-vacuous | As a maintainer, I want a planted-break proof for the encoding and mission-events seam tests, so that the earlier conversion is verified. | Medium | Open | [folded] | yes — proof only, recorded in the PR |
| FR-004 | Dead `_atomic_write` deleted | As a maintainer, I want `GitignoreManager._atomic_write` removed and the tests that name it retargeted to the live writer, so that no test covers dead code. | Medium | Open | [build] | no — the retargeted symlink-race test goes red against a planted break in `write_gitignore_text` |
| FR-005 | TestOrdering rediscovers migrations | As a maintainer, I want `TestOrdering` to call `auto_discover_migrations()` in a class-scoped autouse fixture, so that it passes in isolation and in any order. | High | Open | [build] | no — red when run alone before the fix |
| FR-006 | Follow-up issue for remaining chmod tests | As a maintainer, I want an issue listing the remaining root-skipped chmod tests, so that the rest of the class is tracked. | Low | Open | [folded] | yes — tracker artefact |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Root and non-root verdicts match | Every test this mission touches gives the same verdict as uid 0 and as a regular user: 0 root-only skips are added. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Reuse the eacces helpers | Use `tests/_support/eacces.py` (`deny_open_in` / `deny_path_method`); do not duplicate them. | Technical | High | Open |
| C-002 | Planted breaks never committed | Every planted break is reverted and never committed. | Technical | High | Open |
| C-003 | No top-level heal import | Do not fix #5186 with a module-level import, because `test_settings_encoding_4940.py` calls `MigrationRegistry.clear()`. | Technical | High | Open |
| C-004 | Keep the count==1 asserts | `TestOrdering` keeps asserting each migration is registered exactly once. | Technical | High | Open |
| C-005 | No broad conversion | The remaining ~30 root-skipped chmod tests are listed in a follow-up issue, not converted. | Business | Medium | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `TestOrdering` passes when run alone with `-p no:randomly` (was 2 failed / 2 passed) — [build] · no-op passable: no
- **SC-002**: Each converted or proven test goes red as root against its planted break, and green after the revert — [build] · no-op passable: no
- **SC-003**: `rg "_atomic_write\b" src/specify_cli/gitignore_manager.py tests/cross_cutting/test_gitignore_manager_unit.py` returns 0 hits — [build] · no-op passable: no
