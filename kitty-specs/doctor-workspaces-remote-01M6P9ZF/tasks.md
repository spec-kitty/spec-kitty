---
description: "Work packages for doctor-workspaces-remote-01M6P9ZF (#7214)"
---

# Work Packages: `doctor workspaces --remote`

**Inputs**: `kitty-specs/doctor-workspaces-remote-01M6P9ZF/` — spec.md, plan.md, research.md, contracts/doctor-workspaces-remote.md
**Tests**: Required (NFR-001 no network, NFR-003 no weaker proof, red-first per charter ATDD-first).

**Organization**: Subtasks (`Txxx`) roll up into work packages (`WPxx`). Subtasks are reference rows; the canonical status lives in `status.events.jsonl`.

## Dependency graph

```
WP01 (remote-aware proof + --remote option) ──> WP02 (docs, CLI reference, changelog fragment)
```

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red: fork-clone assessment/prune matrix in `tests/specify_cli/workspace/test_landed_worktrees_remote.py` | WP01 | |
| T002 | Red: `--remote` through the CLI in `tests/specify_cli/cli/commands/test_doctor_workspaces_remote.py` | WP01 | [P] |
| T003 | Primary name from `refs/remotes/<remote>/HEAD`; `primary_ref` built from the remote | WP01 | |
| T004 | Thread `remote` through assess/prune/context/absorption; `WorktreeAssessment.remote`; fail fast on an unconfigured remote | WP01 | |
| T005 | `--remote` in the `workspaces` shell, JSON payload, and prune remedy line | WP01 | |
| T006 | Full landed-worktree + prune CLI suites green, no edits to existing tests | WP01 | |
| T007 | `pr-landing.md` removal step names `--remote upstream` for a fork clone | WP02 | |
| T008 | `docs/api/cli-commands.md` `doctor workspaces` block matches the live surface | WP02 | [P] |
| T009 | `docs/changelog/unreleased/<pr>.fixed.md` fragment | WP02 | [P] |

---

## Work Package WP01: Remote-aware landed proof and the `--remote` option (Priority: P1)

**Goal**: A landed worktree is proven against the primary ref of the remote the operator names, so a fork clone can see and prune what landed upstream.
**Independent Test**: the fork-clone fixture reports `not_landed` by default and `landed` with `--remote upstream`; `--prune --remote upstream` removes it and deletes the branch; an unknown remote exits 1; a configured-but-unfetched remote says which fetch is missing.
**Prompt**: `tasks/WP01-remote-aware-landed-proof.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002, NFR-003, C-001, C-003, SC-001, SC-002, SC-003

---

## Work Package WP02: Docs, CLI reference and changelog fragment (Priority: P2, depends on WP01)

**Goal**: The runbook, the CLI reference and the changelog state the option and the fork-clone path.
**Independent Test**: the freshness checkers report errors=0 and the fragment passes the changelog style check.
**Prompt**: `tasks/WP02-docs-and-changelog.md`
**Requirement Refs**: FR-001, FR-004, FR-006, C-002, SC-001
