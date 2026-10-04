# Tasks: Upgrade reports one outcome

**Mission**: `upgrade-outcome-single-rendering-01M444Q6` | **Branch**: `issue-4925-upgrade-outcome-single-rendering` | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

Three sequential work packages. They share `src/specify_cli/cli/commands/upgrade.py`, so there is no parallelism between them.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Pin with a test that the legacy surface-repair branch is unreachable | WP01 | |
| T002 | Delete the legacy branch and its helpers | WP01 | |
| T003 | Repoint the six tests that patched the dead helper | WP01 | |
| T004 | Red-first regression repro through the CLI entry point | WP02 | |
| T005 | Outcome model: kind, reasons, errors, warnings, status, closing line | WP02 | |
| T006 | Unit matrix for the outcome | WP02 | [P] |
| T007 | Finalizer and surface-repair step return a report | WP02 | |
| T008 | Presentation reads the outcome (one text tail, both JSON builders) | WP02 | |
| T009 | CLI matrix: kind × mode × path, dry-run rows | WP02 | |
| T010 | Strengthen the tests that only pinned the exit code | WP02 | [P] |
| T011 | Help text and its generated mirrors | WP02 | [P] |
| T012 | Architectural gate with self-mutation and floor | WP03 | |
| T013 | Decision record | WP03 | [P] |
| T014 | Changelog entry; remove the known-limitation note | WP03 | [P] |
| T015 | Docs index and freshness guards | WP03 | |

## Phase 1 – Tidy first

### WP01 – Remove the unreachable legacy surface-repair branch

- **Prompt**: [tasks/WP01-remove-unreachable-surface-repair-branch.md](tasks/WP01-remove-unreachable-surface-repair-branch.md)
- **Goal**: one surface-repair path before the functional change. Behaviour-preserving.
- **Priority**: P1 (enabler)
- **Independent test**: the unreachability test, plus the existing upgrade tests pass unmodified in output and exit code.
- **Dependencies**: none
- **Requirements**: FR-016
- **Estimated prompt size**: ~150 lines

T001 Pin with a test that the legacy surface-repair branch is unreachable (WP01)
T002 Delete the legacy branch and its helpers (WP01)
T003 Repoint the six tests that patched the dead helper (WP01)

**Risks**: `_repair_stale_command_manifest` loses its only caller; verify the prepared path covers it before deleting.

## Phase 2 – Functional change

### WP02 – Upgrade outcome owns kind, reasons and rendering

- **Prompt**: [tasks/WP02-outcome-owns-kind-reasons-and-rendering.md](tasks/WP02-outcome-owns-kind-reasons-and-rendering.md)
- **Goal**: the closing line, JSON status and exit code derive from one outcome on both paths and in both modes.
- **Priority**: P1
- **Independent test**: the regression repro is red on its own commit and green at the end; the CLI matrix passes.
- **Dependencies**: Depends on WP01
- **Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, FR-009, FR-010, FR-011, FR-013, FR-014, FR-017, FR-018; NFR-001, NFR-002, NFR-003, NFR-004; SC-001, SC-002, SC-003, SC-004
- **Estimated prompt size**: ~230 lines

T004 Red-first regression repro through the CLI entry point (WP02)
T005 Outcome model: kind, reasons, errors, warnings, status, closing line (WP02)
T006 Unit matrix for the outcome (WP02)
T007 Finalizer and surface-repair step return a report (WP02)
T008 Presentation reads the outcome (WP02)
T009 CLI matrix: kind × mode × path, dry-run rows (WP02)
T010 Strengthen the tests that only pinned the exit code (WP02)
T011 Help text and its generated mirrors (WP02)

**Risks**: hidden consumers of the removed boolean; double printing of the dry-run notice; generated docs.

## Phase 3 – Close the class

### WP03 – Rendering gate, decision record and changelog

- **Prompt**: [tasks/WP03-gate-decision-record-and-changelog.md](tasks/WP03-gate-decision-record-and-changelog.md)
- **Goal**: an empty-allowlist gate keeps presentation from bypassing the outcome; the contract is recorded.
- **Priority**: P2
- **Independent test**: the gate passes on the tree and fails on each synthetic violation.
- **Dependencies**: Depends on WP02
- **Requirements**: FR-012, FR-015; NFR-005; SC-005
- **Estimated prompt size**: ~130 lines

T012 Architectural gate with self-mutation and floor (WP03)
T013 Decision record (WP03)
T014 Changelog entry; remove the known-limitation note (WP03)
T015 Docs index and freshness guards (WP03)

**Risks**: the gate may surface a residual in WP02's output.
