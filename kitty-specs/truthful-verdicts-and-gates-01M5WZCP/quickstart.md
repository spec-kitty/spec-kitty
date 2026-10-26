# Quickstart: verifying the fixes

```bash
# #6652 / #6654 — approval record
uv run --frozen pytest -q tests/specify_cli/cli/commands/agent/test_move_task_approval_feedback_6652.py
# #6653 — terminality gate
uv run --frozen pytest -q tests/policy/test_merge_gates_issue_matrix.py tests/tasks/test_issue_matrix_terminality_6653.py
# #6649 / #5393 — safe-commit
uv run --frozen pytest -q tests/specify_cli/cli/commands/test_safe_commit_cli.py
```
