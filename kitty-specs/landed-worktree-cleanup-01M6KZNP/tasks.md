---
description: "Work packages for landed-worktree-cleanup-01M6KZNP (#7173)"
---

# Work Packages: Landed worktree cleanup and upgrade worktree scope

**Inputs**: `kitty-specs/landed-worktree-cleanup-01M6KZNP/` — spec.md, plan.md, research.md, data-model.md, contracts/, quickstart.md
**Tests**: Required by the spec (NFR-001 safety matrix, red-first per charter ATDD-first).

**Organization**: Subtasks (`Txxx`) roll up into work packages (`WPxx`). Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Dependency graph

```
WP01 (parser, tidy-first) ─┐
                           ├─> WP03 (assessment + prune) ──> WP04 (doctor CLI) ─┐
WP02 (guard extensions) ───┘                                                   ├─> WP06 (docs + changelog)
WP05 (upgrade worktree selection) ─────────────────────────────────────────────┘
```

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | `WorktreeEntry` + `parse_worktree_porcelain` in `kernel/git/listing.py` | WP01 | |
| T002 | `worktree_entries(cwd)` runner | WP01 | |
| T003 | Route `registered_worktree_paths` through the parser | WP01 | |
| T004 | Parser and reroute tests | WP01 | |
| T005 | No-force removal mode in `guarded_worktree_remove` | WP02 | [P] |
| T006 | `LANDED_INTENT` in `guarded_branch_delete`, tip kept | WP02 | [P] |
| T007 | Guard tests (no-force, lock, LANDED with and without unique commits) | WP02 | |
| T008 | Verdict model and reason codes | WP03 | |
| T009 | `/proc` running-process probe | WP03 | [P] |
| T010 | `assess_worktrees` (ordered verdict rule) | WP03 | |
| T011 | `prune_landed` (re-assess, guarded remove, LANDED delete, recreate hint) | WP03 | |
| T012 | Routing-gate pin gains the prune caller | WP03 | |
| T013 | Safety-matrix integration tests | WP03 | |
| T014 | `--prune` flag on the `doctor workspaces` shell | WP04 | |
| T015 | Text and JSON rendering of verdicts and prune outcomes | WP04 | |
| T016 | Exit-code semantics; `--fix` unchanged; combined flags | WP04 | |
| T017 | CLI tests | WP04 | |
| T018 | `WorktreeSelection` + dispositions + path validation | WP05 | |
| T019 | Runner threads the selection (replaces `_worktrees_to_upgrade`) | WP05 | |
| T020 | CLI flags, conflict and unknown-path refusals | WP05 | |
| T021 | Dispositions in the normal preview and output | WP05 | |
| T022 | `--plan-json` selection and dispositions | WP05 | |
| T023 | Existing tests opt in; new red-first tests | WP05 | |
| T024 | CLI reference: `doctor workspaces` and `upgrade` | WP06 | [P] |
| T025 | `pr-landing.md` removal step | WP06 | [P] |
| T026 | Changelog fragment | WP06 | [P] |

---

## Work Package WP01: Worktree porcelain parser (Priority: P0, tidy-first)

**Goal**: One parser for `git worktree list --porcelain` in the kernel git layer; `registered_worktree_paths` reuses it with no behaviour change.
**Independent Test**: Parser unit tests on recorded porcelain text; existing husk tests stay green unchanged.
**Prompt**: `tasks/WP01-worktree-porcelain-parser.md`
**Requirement Refs**: FR-001, FR-012, C-003

### Included Subtasks

T001 `WorktreeEntry` + `parse_worktree_porcelain` in `src/kernel/git/listing.py` (WP01)
T002 `worktree_entries(cwd)` runner (WP01)
T003 Route `registered_worktree_paths` through the parser (WP01)
T004 Parser and reroute tests (WP01)

### Dependencies

- None.

### Risks & Mitigations

- Behaviour drift in husk detection: run `tests/status/test_doctor_husks.py` and `tests/specify_cli/cli/commands/test_workspace_husk_doctor.py` unchanged.

---

## Work Package WP02: Guard extensions (Priority: P0)

**Goal**: The destructive guard can remove a proven-clean worktree without `--force`, and delete a landed branch while keeping its tip under `refs/spec-kitty/discarded/`.
**Independent Test**: Guard unit/integration tests on temp repositories.
**Prompt**: `tasks/WP02-guard-extensions.md`
**Requirement Refs**: FR-003, FR-004, NFR-001, C-002

### Included Subtasks

T005 No-force removal mode in `guarded_worktree_remove` (WP02)
T006 `LANDED_INTENT` in `guarded_branch_delete`, tip kept (WP02)
T007 Guard tests (WP02)

### Dependencies

- None.

### Risks & Mitigations

- Existing callers must be unaffected: the new mode is opt-in via a keyword with the old default.

---

## Work Package WP03: Landed-worktree assessment and prune (Priority: P1)

**Goal**: Every registered worktree gets an offline verdict; `prune_landed` removes only proven-landed ones through the guard.
**Independent Test**: The SC-001 fixture: rebase-merged, open-with-unpushed, dirty, running-process, Mission lane — only the first is removed.
**Prompt**: `tasks/WP03-landed-assessment-and-prune.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-003, C-004

### Included Subtasks

T008 Verdict model and reason codes (WP03)
T009 `/proc` running-process probe (WP03)
T010 `assess_worktrees` (WP03)
T011 `prune_landed` (WP03)
T012 Routing-gate pin gains the prune caller (WP03)
T013 Safety-matrix integration tests (WP03)

### Dependencies

- Depends on WP01, WP02.

### Risks & Mitigations

- Data loss: every refusal case is tested beside a landed positive control on the same fixture; the verdict is re-evaluated immediately before removal.

---

## Work Package WP04: `doctor workspaces --prune` CLI (Priority: P1)

**Goal**: The operator-facing report and prune, text and JSON, with stable exit codes.
**Independent Test**: CliRunner tests on temp repositories.
**Prompt**: `tasks/WP04-doctor-workspaces-prune-cli.md`
**Requirement Refs**: FR-001, FR-006, FR-012, NFR-004

### Included Subtasks

T014 `--prune` flag on the shell (WP04)
T015 Text and JSON rendering (WP04)
T016 Exit codes; `--fix` unchanged; combined flags (WP04)
T017 CLI tests (WP04)

### Dependencies

- Depends on WP03.

---

## Work Package WP05: Upgrade worktree selection (Priority: P1)

**Goal**: `upgrade` writes into non-Mission worktrees only when opted in, and names every worktree with its disposition.
**Independent Test**: `upgrade --yes` with no flag, `--include-worktree`, `--all-worktrees` on a temp repository.
**Prompt**: `tasks/WP05-upgrade-worktree-selection.md`
**Requirement Refs**: FR-007, FR-008, FR-009, FR-010

### Included Subtasks

T018 `WorktreeSelection` + dispositions + validation (WP05)
T019 Runner threads the selection (WP05)
T020 CLI flags and refusals (WP05)
T021 Dispositions in preview and output (WP05)
T022 `--plan-json` fields (WP05)
T023 Existing tests opt in; new red-first tests (WP05)

### Dependencies

- None.

### Risks & Mitigations

- Open PRs #7094 / #7116 touch `upgrade.py`: keep edits local to worktree handling.

---

## Work Package WP06: Documentation and changelog (Priority: P2)

**Goal**: CLI reference, landing runbook and changelog describe the new behaviour.
**Independent Test**: Docs parity and changelog-style tests pass.
**Prompt**: `tasks/WP06-docs-and-changelog.md`
**Requirement Refs**: FR-011, C-005

### Included Subtasks

T024 CLI reference (WP06)
T025 `pr-landing.md` removal step (WP06)
T026 Changelog fragment (WP06)

### Dependencies

- Depends on WP04, WP05.
