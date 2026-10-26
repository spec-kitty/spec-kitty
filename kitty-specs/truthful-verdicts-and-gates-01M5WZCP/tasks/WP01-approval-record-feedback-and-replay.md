---
work_package_id: WP01
title: Approval record keeps the review and a replayable command
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
- C-003
planning_base_branch: issue-6652-verdict-gate-truthfulness
merge_target_branch: issue-6652-verdict-gate-truthfulness
branch_strategy: Planning artifacts for this mission were generated on issue-6652-verdict-gate-truthfulness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6652-verdict-gate-truthfulness unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-truthful-verdicts-and-gates-01M5WZCP
base_commit: b39d1918d2d382be3cbe9e87b6ec90f4c5de8137
created_at: '2026-10-26T21:36:24.955236+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Defect fixes
history:
- at: '2026-10-26T21:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py
create_intent:
- tests/specify_cli/cli/commands/agent/test_move_task_approval_feedback_6652.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py
- src/specify_cli/review/cycle.py
- tests/specify_cli/cli/commands/agent/test_move_task_approval_feedback_6652.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Approval record keeps the review and a replayable command

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objective

`move-task --to approved --review-feedback-file <f>` validates the file, discards it, writes a one-line approval record and reports `verdict_durably_persisted: true` (#6652). The record's `reproduction_command` interpolates the reviewer unquoted (#6654). Make the record carry the file and make the command replay.

Operator decisions (spec Decision Moments):
- Body = `Approved by <reviewer>: <approval-ref>`, a blank line, then the file verbatim.
- A file supplied on an approval whose latest verdict is already approved writes a new approved cycle; without a file the no-op stays.

## Branch Strategy

Planning branch and merge target: `issue-6652-verdict-gate-truthfulness`. The execution worktree is allocated per computed lane from `lanes.json`:

```bash
spec-kitty agent action implement WP01 --agent claude --mission truthful-verdicts-and-gates-01M5WZCP
```

## Subtasks

### T001 — Red-first tests (commit before any fix)

New file `tests/specify_cli/cli/commands/agent/test_move_task_approval_feedback_6652.py`, modelled on `test_move_task_approval_evidence.py` (real `_do_move_task`, fake ports, `auto_commit=False`, `setup_mocked_env`). Cases:

1. First-pass approval (`in_review`) with a feedback file holding a distinctive line → `tasks/WP01-test/review-cycle-1.md` body contains the approval line, then the distinctive line.
2. Same without a file → body is exactly `Approved by <reviewer>: approval:WP01` (ratchet).
3. Reviewer `Jane Doe (model-x)` → `shlex.split(reproduction_command)` has `--agent` followed by `Jane Doe (model-x)`.
4. Latest verdict already approved (seed an approval via a first move, or seed the event-sourced review slot) + file → a new cycle carrying the file; without a file → no new cycle.
5. Feedback file whose content is a review-cycle artifact → command refuses (non-zero / `typer.Exit`), nothing written.
6. Damaged verdict slot + file → refusal, nothing written (if the slot is hard to seed, pin it at the `_persist_approved_review_cycle` unit level with a hand-built `_MoveTaskState`).

Run them against the unchanged code and confirm cases 1, 3, 4(with file), 5, 6 fail.

### T002 — Body preamble in the writer

`src/specify_cli/review/cycle.py`: add keyword `body_preamble: str | None = None` to `create_rejected_review_cycle` and `_resolve_review_body`. Only valid with `feedback_source`; the resolved body becomes `f"{body_preamble}\n{file_text}"`. The provenance guard still runs on the file. Update the docstring.

### T003 — Approval writer uses the file

`tasks_verdict_persistence._persist_approved_review_cycle`: when `st.resolved_feedback_source` is set, call the writer with `feedback_source=` and `body_preamble=f"Approved by {reviewer_agent}: {approval_reference}\n"`; otherwise keep `body=` (M1). The already-approved early return applies only when no file is supplied. Keep complexity ≤ 15 (extract a helper if needed).

### T004 — Refuse an unrecordable file

The damaged-slot early return with a supplied file raises a refusal (`ReviewCycleError` or the existing `TaskCliError` path) naming the file, before anything is written. The arbiter-override return stays (out of scope; recorded as a residual).

### T005 — Quote the replay command

`reproduction_command = shlex.join(["spec-kitty", "agent", "tasks", "move-task", st.task_id, "--to", "approved", "--mission", st.mission_slug, "--agent", reviewer_agent])`.

## Validation

```bash
uv run --frozen pytest -q tests/specify_cli/cli/commands/agent/test_move_task_approval_feedback_6652.py \
  tests/specify_cli/cli/commands/agent/test_move_task_approval_evidence.py \
  tests/specify_cli/cli/commands/agent/test_move_task_approval_body_collision.py \
  tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py tests/review/
```

## Definition of Done

- T001 committed red before the fix; green after.
- ruff, `ruff format --check --force-exclude`, mypy clean on changed files; no suppressions.
- Rejection path and provenance guard behaviour unchanged.

## Reviewer guidance

Verify red→green; confirm the no-file approval body is byte-identical to before; confirm a prior review-cycle artifact is still refused.
