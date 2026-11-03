---
work_package_id: WP03
title: End-to-end proof through the real CLI
dependencies:
- WP01
- WP02
requirement_refs:
- FR-009
- SC-001
- SC-003
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
phase: Phase 3 - The recorded shape, end to end
history:
- at: '2026-11-03T13:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty/tasks
agent_profile: python-pedro
authoritative_surface: tests/integration/
create_intent:
- tests/integration/test_7120_lane_window_never_created.py
execution_mode: code_change
model: ''
owned_files:
- tests/integration/test_7120_lane_window_never_created.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7120'
---

# Work Package Prompt: WP03 – End-to-end proof through the real CLI

## Objectives & Success Criteria

The unit cases prove the message. This work package proves the shape the issue recorded, through
the command an operator actually runs: a real `lanes` Mission, the work package's implementation
committed on the target branch, no lane worktree and no lane branch, an unforced
`spec-kitty agent tasks move-task WP02 --to for_review`.

Success: the command exits non-zero, the work package stays where it was, and the refusal names the
shape (absent lane branch, work on the target branch), the fabrication warning and the open ruling,
and no longer tells the operator to make an absent branch readable and retry.

## Context & Constraints

- Reuse the existing real-CLI harness in `tests/integration/test_6715_consolidate_lane_evidence.py`
  (`setup_mission`, `_sk`, `_git`, `_commit_specs`, `lanes_of`) instead of a new harness; read them,
  do not modify them (they belong to #6715's suite, not this Mission).
- `pytestmark` must carry `pytest.mark.integration`, `pytest.mark.git_repo` and an explicit
  `pytest.mark.timeout(600)`; never raise the global default.
- Do not weaken or skip any gate to make the case pass; if a pre-existing gate refuses for an
  unrelated reason, record it and report rather than working around it.

## Subtasks & Detailed Guidance

### Subtask T007 – The case
- **Steps**:
  1. Create `tests/integration/test_7120_lane_window_never_created.py` with one case:
     `setup_mission(tmp_path, "lanes")`, commit WP02's owned file (`tools/check.sh`) on the target
     branch, move WP02 to `in_progress` without running `agent action implement` (so no lane
     worktree/branch is created), mark its subtask done, then attempt the unforced
     `move-task --to for_review`.
  2. Assert: non-zero exit; `IMPLEMENTATION_UNREADABLE` leads the message; the message names the
     absent lane branch; it says the work is on the target branch / the lanes were never created;
     it says creating the branch would fabricate the evidence; it names #7120; the old
     "Make the lane branch and the recorded planning commit readable, then retry" sentence is gone;
     `lanes_of(mission)["WP02"] == "in_progress"` (nothing moved); `git show-ref` still shows no
     lane branch (nothing was fabricated).
  3. Prove red: the same case against the pre-fix source fails on the message assertions.
- **Files**: `tests/integration/test_7120_lane_window_never_created.py`

### Subtask T008 – Keep it honest and cheap
- **Steps**:
  1. Print the captured output on failure (`output[-2500:]`) so a future maintainer can read the
     refusal from CI.
  2. Confirm the case runs in well under its timeout and does not spawn lane worktrees it does not
     assert on.
- **Files**: `tests/integration/test_7120_lane_window_never_created.py`

## Definition of Done

- `uv run pytest tests/integration/test_7120_lane_window_never_created.py -q -p no:randomly` green,
  red against the pre-fix source.
- `uv run ruff check` clean on the new file.
