---
description: "Work packages for the finalize-tasks status-surface restore (#5641)"
---

# Work Packages: finalize-tasks: a failed run leaves the status surface as it found it

**Inputs**: `kitty-specs/finalize-tasks-failed-run-restores-status-surface-01M43AHQ/` (spec.md, plan.md, research/code-grounding.md)
**Prerequisites**: plan.md, spec.md

**Tests**: the red-first reproduction from PR #5657 is the acceptance test; one added test for the foreign-commit report.

**Organization**: Subtasks (`Txxx`) roll up into work packages (`WPxx`).

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can proceed in parallel.
- Subtasks are reference rows: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Status-surface guard for a failed finalize-tasks run (Priority: P0)

**Goal**: A finalize-tasks run that fails before its final commit lands restores the status surface's branch tip, index and status files on every topology, through compare-and-swap, and reports the commits it could not undo.
**Independent Test**: `tests/specify_cli/cli/commands/agent/test_finalize_atomicity.py` green, the #5641 reproduction un-marked.
**Prompt**: `/tasks/WP01-status-surface-guard.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-006, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, C-004

### Included Subtasks

T001 Add `finalize_status_surface.py`: capture (branch, tip, index tree), record the tip after the last status write, CAS restore + `read-tree`, report of left-over commits
T002 Wire the guard into `_run_commit_pipeline` and both `except` arms of `finalize_tasks`; restore the coordination status bytes only after a successful ref restore
T003 Retire `_capture_owned_head` / `_restore_owned_head` and the `owned_head_before` plumbing (one restore authority)
T004 Remove the `regression` marker from the #5641 reproduction; add the foreign-commit report test
T005 Update the FR-015/NFR-001 "COVERED / NOT COVERED" comment in `finalize_tasks`

### Dependencies

- None (starting package).

### Risks & Mitigations

- Owned-checkout regression: run the owned finalize suites.
- Gate drift: run the destructive-op, rollback-authority, git-path-listing, status-write and untrusted-path gates by name.

---

## Work Package WP02: Retry evidence and changelog (Priority: P1)

**Goal**: Record what a retry after a failed run does before and after the fix, and add the changelog entry.
**Independent Test**: `python -m scripts.docs.check_changelog_style` passes; the evidence file shows one seed per WP after the fix.
**Prompt**: `/tasks/WP02-retry-evidence-and-changelog.md`
**Requirement Refs**: FR-005, FR-006

### Included Subtasks

T006 Record the retry evidence (before: double seed on lanes / single_branch; after: one seed) in `research/retry-evidence.md`
T007 Add a `### Fixed` entry under Unreleased in `docs/changelog/CHANGELOG.md`

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- Changelog house style: run the style and spelling checkers.
