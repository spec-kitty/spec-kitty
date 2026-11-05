---
work_package_id: WP01
title: Remote-aware landed proof and the --remote option
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-7214-doctor-workspaces-remote
merge_target_branch: issue-7214-doctor-workspaces-remote
branch_strategy: Planning artifacts for this mission were generated on issue-7214-doctor-workspaces-remote. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7214-doctor-workspaces-remote unless the human explicitly redirects the landing branch.
created_at: '2026-11-05T17:10:00+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Behaviour
history:
- at: '2026-11-05T17:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/workspace/
create_intent:
- src/specify_cli/workspace/landed_worktrees.py
- src/specify_cli/cli/commands/_landed_worktree_doctor.py
- src/specify_cli/cli/commands/_workspace_husk_doctor.py
- src/specify_cli/cli/commands/doctor.py
- tests/specify_cli/workspace/test_landed_worktrees_remote.py
- tests/specify_cli/cli/commands/test_doctor_workspaces_remote.py
execution_mode: code_change
owned_files:
- src/specify_cli/workspace/landed_worktrees.py
- src/specify_cli/cli/commands/_landed_worktree_doctor.py
- src/specify_cli/cli/commands/_workspace_husk_doctor.py
- src/specify_cli/cli/commands/doctor.py
- tests/specify_cli/workspace/test_landed_worktrees_remote.py
- tests/specify_cli/cli/commands/test_doctor_workspaces_remote.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7214'
---

# Work Package Prompt: WP01 – Remote-aware landed proof and the `--remote` option

## Objective

Make the landed-worktree proof read a named remote instead of the hardcoded
`origin`, expose that as `doctor workspaces --remote <name>`, and fail loudly
when the name is wrong or unfetched. Read `contracts/doctor-workspaces-remote.md`
first: it fixes the flag semantics, the messages and the JSON key.

## Subtasks

- **T001 (red)** — `tests/specify_cli/workspace/test_landed_worktrees_remote.py`
  on a fork-clone fixture: bare `upstream.git` holds the rebased landing commit,
  bare `origin.git` still sits at the pre-landing `main`. Through the
  pre-existing entry points, assert the landed verdict under `remote="upstream"`,
  the unchanged default, the prune and its recreate command, the fail-closed
  remote mismatch, the unlanded negative control, the unconfigured-remote error,
  the missing-ref detail, the `<remote>/HEAD` primary, the other-remote negative
  control (NFR-003) and no network subcommand (NFR-001).
- **T002 (red)** — `tests/specify_cli/cli/commands/test_doctor_workspaces_remote.py`
  through `CliRunner` over `doctor.app`: help lists the option, the JSON payload
  carries `remote`, the text header names the remote's primary ref, an unknown
  remote exits 1, the printed prune remedy carries `--remote`, `--fix` reports
  against the named remote and prunes nothing, and the Typer default equals
  `DEFAULT_REMOTE`.
- **T003** — In `landed_worktrees.py`, resolve the primary from
  `refs/remotes/<remote>/HEAD` when it is a symbolic ref, else keep
  `resolve_primary_branch(bias=False)`; build `primary_ref` with
  `kernel.git.remote.tracking_ref`; keep the "only a guess" refusal (FR-005, C-001).
- **T004** — Thread `remote` through `assess_worktrees`, `_context`, `_absorption`
  (detail text) and `prune_landed` (including the pre-removal re-assessment, so a
  mismatch fails closed — FR-002, C-003). Add `remote` to `WorktreeAssessment`
  with default `DEFAULT_REMOTE` (its `to_json()` shape stays #7196's contract).
  Refuse an unconfigured remote as an `error` assessment before any verdict
  (FR-003).
- **T005** — CLI: add `--remote` to the `workspaces` command in `doctor.py`,
  thread it through `run_workspaces` → `run_worktree_section`, put `remote` in
  the JSON payload, and make the printed remedy line carry `--remote <name>`
  when it is not `origin` (FR-006).
- **T006** — Green: the two new files plus the pre-existing
  `tests/specify_cli/workspace/test_landed_worktrees.py`,
  `tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py` and
  `tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py` (NFR-002).

## Definition of done

- Both new test files fail on the pre-fix code and pass after it.
- The existing assessment, prune CLI and golden surface tests pass **without
  edits beyond the golden snapshot the new option necessarily changes**.
- `ruff check` and `ruff format --check --force-exclude` clean on the changed files.
- No `Reason`/`Verdict` member added or reordered; no change to the destructive
  guard, `LANDED_INTENT`, or the exit-code contract.
