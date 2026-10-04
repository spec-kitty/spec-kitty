# Tasks: Charter CLI tests independent of invoking checkout

**Mission**: `charter-test-cwd-isolation-01M43CM3` | **Branch**: `issue-5317-charter-test-cwd-isolation` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Three sequential work packages. Test-side only; nothing under `src/` changes.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first reproduction from a real linked worktree | WP01 | |
| T002 | Shared `charter_cwd_isolation` fixture, registered once; refusal control | WP01 | |
| T003 | Retire the three per-file copies | WP01 | |
| T004 | Re-derive the pinning inventory | WP01 | |
| T005 | Verify and hand over | WP01 | |
| T006 | Adopt in `tests/agent/cli/commands/` (3 files) | WP02 | [P] |
| T007 | Adopt in `tests/charter/` (3 files) | WP02 | [P] |
| T008 | Adopt in `tests/consolidation/test_profile_charter_e2e.py` | WP02 | [P] |
| T009 | Dry-run smoke test remedy | WP02 | [P] |
| T010 | Verify and hand over | WP02 | |
| T011 | Red-first self-mutation tests for the tripwire | WP03 | |
| T012 | Tripwire plugin and registration | WP03 | |
| T013 | Coverage test for watched guard call sites | WP03 | |
| T014 | Bounded straggler run | WP03 | |
| T015 | No-exemption assertion, verification, hand over | WP03 | |

## Phase 1 - Foundation

### WP01 — One owner for the charter working-directory isolation

- **Prompt**: [tasks/WP01-shared-isolation-fixture.md](tasks/WP01-shared-isolation-fixture.md)
- **Goal**: Witness the defect, introduce the single shared fixture, remove the three copies, keep the release inventory consistent.
- **Priority**: P1
- **Requirements**: FR-001, FR-002, FR-003, FR-008, FR-010
- **Dependencies**: none
- **Independent test**: the reproduction file shows the refusal without the helper and success with it; the three former copy files pass; the inventory freshness test passes.
- **Estimated prompt size**: ~210 lines

T001 Red-first reproduction from a real linked worktree (WP01)
T002 Shared `charter_cwd_isolation` fixture, registered once; refusal control (WP01)
T003 Retire the three per-file copies (WP01)
T004 Re-derive the pinning inventory (WP01)
T005 Verify and hand over (WP01)

- **Implementation sketch**: reproduction commit (red) → fixture + registration (green) → copies retired → inventory re-derived → targeted run.
- **Risks**: inventory regeneration touching unrelated entries; fixture changing tests that rely on the real resolver.

## Phase 2 - Adoption

### WP02 — Adopt the isolation in every leaking test

- **Prompt**: [tasks/WP02-adopt-isolation.md](tasks/WP02-adopt-isolation.md)
- **Goal**: The eight affected files give the same results from a linked worktree and from the repository root checkout.
- **Priority**: P1
- **Requirements**: FR-004, FR-007
- **Dependencies**: Depends on WP01
- **Independent test**: the eight files, run from a lane worktree, report zero failures with unchanged test counts.
- **Estimated prompt size**: ~200 lines

T006 Adopt in `tests/agent/cli/commands/` (3 files) (WP02)
T007 Adopt in `tests/charter/` (3 files) (WP02)
T008 Adopt in `tests/consolidation/test_profile_charter_e2e.py` (WP02)
T009 Dry-run smoke test remedy (WP02)
T010 Verify and hand over (WP02)

- **Parallel opportunities**: T006–T009 touch different files.
- **Risks**: assertions sensitive to the working directory; the smoke test's deferral path.

## Phase 3 - Guard

### WP03 — Recurrence tripwire for charter working-directory leaks

- **Prompt**: [tasks/WP03-recurrence-tripwire.md](tasks/WP03-recurrence-tripwire.md)
- **Goal**: A leaking test fails in every kind of checkout, named, with no exemptions.
- **Priority**: P2
- **Requirements**: FR-005, FR-006, FR-009
- **Dependencies**: Depends on WP02
- **Independent test**: planted offenders are caught and clean neighbours pass; removing a watched module turns the coverage test red.
- **Estimated prompt size**: ~230 lines

T011 Red-first self-mutation tests for the tripwire (WP03)
T012 Tripwire plugin and registration (WP03)
T013 Coverage test for watched guard call sites (WP03)
T014 Bounded straggler run (WP03)
T015 No-exemption assertion, verification, hand over (WP03)

- **Risks**: stragglers outside the known set; session import cost; `pytester` subprocess set-up.

## Dependencies

WP01 → WP02 → WP03. No parallel work packages.
