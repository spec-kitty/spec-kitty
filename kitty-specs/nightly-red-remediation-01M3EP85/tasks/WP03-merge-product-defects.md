---
work_package_id: WP03
title: Merge product defects
dependencies: []
requirement_refs:
- FR-008
- FR-009
planning_base_branch: claude/lucid-ptolemy-fjtzep
merge_target_branch: claude/lucid-ptolemy-fjtzep
branch_strategy: Planning artifacts for this mission were generated on claude/lucid-ptolemy-fjtzep. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/lucid-ptolemy-fjtzep unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-red-remediation-01M3EP85
base_commit: 9810f2cfa014b77704d58b99c93a915717d7f6ba
created_at: '2026-09-26T11:14:41.248784+00:00'
subtasks:
- T008
- T009
- T010
- T011
phase: Phase 1 - Remediation
history:
- at: '2026-09-26T11:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/
create_intent:
- tests/merge/test_nightly_remediation_merge_defects.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/merge/forecast.py
- src/specify_cli/merge/executor.py
- src/specify_cli/cli/commands/merge.py
- tests/merge/test_nightly_remediation_merge_defects.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Merge product defects

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback before completing.

---

## Objectives & Success Criteria

- `spec-kitty merge --dry-run` with an unmaterialized coordination worktree, or a deleted coordination branch, prints the error, a remediation hint and exits 1. It never prints a traceback. With `--json`, stdout is a single JSON error document.
- A fresh merge that exits during the pre-mutation gate phase leaves no `state.json`, so the next plain merge is not refused as pre-fix.
- `merge --abort` removes the reconciliation post-fix marker.
- A genuinely pre-fix resume (state present, no marker) is still refused.

## Context & Constraints

- Research R-2 and R-3.
- Red-first (C-002): write each regression, show it failing on the unmodified code, then fix.
- Reuse the executor's refusal wording (`executor.py` ~3354-3369). Extract a small shared helper rather than duplicating strings (Sonar S1192).
- Complexity ≤ 15 per function.

## Subtasks & Detailed Guidance

### Subtask T008 – Dry-run clean refusal

- **Path**: `cli/commands/merge.py:~915` `run_dry_run_forecast` → `merge/forecast.py:~256` `run_review_artifact_consistency_preflight` → `post_merge/review_artifact_consistency.py:87` → `mission_runtime/resolution.py:1977` raises `CoordinationWorktreeUnmaterialized`.
- **Steps**:
  - Catch `CoordinationWorktreeUnmaterialized` and `CoordinationBranchDeleted` at the forecast seam.
  - Human mode: print the same message plus hint as the real merge, then `Exit(1)`.
  - JSON mode: emit `{"error": str(exc), "error_code": ...}` as a single document, then `Exit(1)`.
- **Test**: Build a coord-topology mission whose coordination branch exists but has no worktree, as in the red retention fixture. Invoke the CLI via `CliRunner` with `merge --dry-run` and with `--json`. Assert exit 1, no `Traceback`, and the message present.

### Subtask T009 – Reproduce the fresh-stop wedge (red-first)

- **Steps**: Drive `_run_lane_based_merge` (or the CLI) on a fresh mission where `evaluate_merge_gates` returns a blocking failure (patch it to fail). Assert `Exit(1)`. Then re-run with gates passing and assert the run is NOT refused with "pre-fix in-flight merge state". Confirm this fails before the fix. If it cannot be reproduced, record that in the mission notes and stop per the spec assumption.

### Subtask T010 – Clear the fresh run's own state on a pre-mutation exit

- **Steps**:
  - In `_run_lane_based_merge_locked`, wrap `_phase_gates_and_state(run)` so that on `typer.Exit` (and `click.exceptions.Abort` from a declined confirmation) a non-resume run calls `clear_state(run.main_repo, run.canonical_id)` before re-raising.
  - This generalises the #4764 clear in `_assert_mission_terminal_ready`. That clear becomes redundant: remove it only if tests stay green, and keep a single authority.
  - Never clear a resume's state.

### Subtask T011 – Abort removes the marker

- **Steps**: In `_dispatch_abort` (`cli/commands/merge.py:~405`), call `clear_post_fix_marker(repo_root, mission_id)` for each state cleared. Add a test that writes a marker plus state, runs `merge --abort`, and asserts both are gone.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/merge/test_nightly_remediation_merge_defects.py -q
.venv/bin/python -m pytest tests/merge tests/cli/commands -q -n auto --dist loadfile
mypy src/specify_cli/merge/forecast.py src/specify_cli/merge/executor.py src/specify_cli/cli/commands/merge.py
```

## Risks & Mitigations

- `Exit` from the gate phase on a *resume* must not clear state. Test both branches.
- Some existing tests assert `state.json` survives a readiness failure on a resume. Keep them green.

## Review Guidance

- Red-first evidence is recorded (the failing output before the fix).
- The JSON error is a single document.
- No duplicated refusal strings.

## Branch Strategy

- **Strategy**: single_branch mission; the execution workspace is resolved per computed lane from `lanes.json`.
- **Planning base branch**: `claude/lucid-ptolemy-fjtzep`
- **Merge target branch**: `claude/lucid-ptolemy-fjtzep`

## Definition of Done

- Every listed test passes locally.
- No test is skipped, xfailed, deleted or retried (C-001).
- `ruff check` and `ruff format --check` are clean on the touched files.
- Every re-pin carries a docstring or comment citing the product change that moved the contract.

## Activity Log

- 2026-09-26T11:30:00Z – system – Prompt created.
