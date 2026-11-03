---
work_package_id: WP02
title: move-task names the shape and stops the loop
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-006
- FR-009
- NFR-003
- SC-001
- SC-002
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T004
- T005
- T006
phase: Phase 2 - The quoted refusal
history:
- at: '2026-11-03T13:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty/tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- tests/specify_cli/cli/commands/agent/test_move_task_evidence_gate.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7120'
---

# Work Package Prompt: WP02 – move-task names the shape and stops the loop

## Objectives & Success Criteria

`_mt_require_lane_evidence` is where the issue's refusal is produced. It currently sends every
diff failure to one sentence:

> Make the lane branch and the recorded planning commit readable, then retry.

For a lane branch that was never created that sentence cannot be carried out, and it is what makes
an agent loop. This work package makes the gate use WP01's probe on the failure path only:

- the window tip is a branch that is truly absent → the refusal is the shared never-created /
  restore cause instead of "could not be diffed";
- the tip resolves but the diff cannot be read → the present "could not be diffed … Make the lane
  branch and the recorded planning commit readable, then retry" wording is unchanged;
- every path still refuses (no pass), and nothing but the text changes.

## Context & Constraints

- WP01 has landed `branch_ref_absent`, the lane-branch classifier and the shared cause in
  `specify_cli.consolidation.wp_evidence`; call them, do not restate the rule (C-002).
- Keep `IMPLEMENTATION_UNREADABLE`: no new code (NFR-003), no new flag.
- `from exc` chaining stays; the message begins with the code (the `--json` envelope and the
  orchestrator contract depend on that).
- Do not touch the `IMPLEMENTATION_MISSING`, `EVIDENCE_WINDOW_UNCOMPUTABLE` or single_branch
  branches of the same function.
- Do not advertise `--force` (it bypasses a review-evidence gate) and do not suggest re-running
  `agent action implement` (it provisions a lane worktree for work that already exists).

## Subtasks & Detailed Guidance

### Subtask T004 – Probe the tip on the failure path
- **Steps**:
  1. In `_mt_require_lane_evidence`, in the `except GitProbeError` arm, resolve the window tip
     (`window[1]`) and ask `wp_evidence.branch_ref_absent(st.main_repo_root, tip)`.
  2. When it is absent, build the refusal from WP01's shared cause (pass the manifest so the
     classifier can tell "this Mission never created its lanes" from "this lane was pruned"), with
     the same `"{code}: {wp}'s evidence window {base}..{tip} ({lane_id}) …"` prefix the gate already
     uses.
  3. Otherwise keep today's sentence exactly.
- **Files**: `src/specify_cli/cli/commands/agent/tasks_move_task.py`
- **Notes**: the probe runs only after a diff already failed, so a passing gate pays nothing
  (NFR-001). A probe that cannot be read is "not absent" (NFR-002).

### Subtask T005 – Keep the refusal a refusal
- **Steps**:
  1. Nothing in this work package may let the move through: no early return, no pass, no
     downgrade to a warning.
  2. Re-read the guard above (`st.force`, `st.owned`, review-ward gating) and confirm you did not
     change any of it.
- **Files**: `src/specify_cli/cli/commands/agent/tasks_move_task.py`

### Subtask T006 – Tests
- **Steps**:
  1. In `tests/specify_cli/cli/commands/agent/test_move_task_evidence_gate.py`, add cases over a
     real temporary git repository (the module's existing cases monkeypatch `evidence_paths`, which
     cannot express an absent ref): (a) a `lanes` manifest whose only code lane has no branch
     refuses `IMPLEMENTATION_UNREADABLE` with the never-created text, and does not contain
     "Make the lane branch and the recorded planning commit readable"; (b) with a second lane branch
     present and the work package's own branch absent, the refusal names the restore remedy; (c) a
     present-but-unreadable ref keeps "could not be diffed".
  2. Assert the work package is not moved: the function raises and nothing else runs.
  3. Prove red against the pre-fix source and record it.
- **Files**: `tests/specify_cli/cli/commands/agent/test_move_task_evidence_gate.py`

## Definition of Done

- `uv run pytest tests/specify_cli/cli/commands/agent/test_move_task_evidence_gate.py -q -p no:randomly` green, new cases red against the pre-fix source.
- `uv run ruff check` and `uv run mypy` clean on both files.
- The `IMPLEMENTATION_UNREADABLE` refusal in the issue's reproduction reads as specified.
