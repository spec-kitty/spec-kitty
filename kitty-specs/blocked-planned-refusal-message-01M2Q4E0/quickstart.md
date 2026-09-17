# Quickstart: verify the source-aware unblock refusal

## Reproduce the defect (current behavior)

The refusal for `move-task --to planned` is source-agnostic — a `blocked` work
package is told to provide review feedback. Exercise the pure decision core
(no mission setup needed):

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
from specify_cli.cli.commands.agent.tasks_transition_core import decide_transition, RefuseExit1
# reuse the module's test helper shape: build a minimal request via the test factory
# (see tests/specify_cli/cli/commands/agent/test_tasks_transition_core.py::_base_request)
PY
```

In practice the fastest witness is the unit layer — the regression tests added
by WP01 drive `decide_transition` directly with `old_lane` set to each source.

## Verify the fix

Run the extended regression file:

```bash
PWHEADLESS=1 .venv/bin/python -m pytest \
  tests/specify_cli/cli/commands/agent/test_tasks_transition_core.py -q
```

Expected after WP01:

- `blocked` (± `--force`, no feedback) → refused, message names `--to in_progress`,
  no "requires review feedback".
- `done`/`canceled` (± `--force`, no feedback) → refused, lane unchanged, no
  forced-rewind event; message says terminal / not reachable.
- `genesis`/`in_review` (± `--force`, no feedback) → refused with the existing
  review-feedback text.
- `in_review` + valid non-empty feedback → succeeds (exit 0), lane `planned`.
- `blocked` + fabricated non-empty feedback → still refused.

## Blast-radius test set (record in the PR)

```bash
PWHEADLESS=1 .venv/bin/python -m pytest \
  tests/specify_cli/cli/commands/agent/test_tasks_transition_core.py \
  tests/specify_cli/cli/commands/agent/test_tasks_cli_contract_coord.py \
  tests/specify_cli/cli/commands/agent/test_tasks_backward_emit.py \
  tests/specify_cli/cli/commands/agent/test_move_task_rollback_clears_claim.py \
  -q
```

Plus the shared baseline `make test-fast`. Terminology guard (touching a
user-facing message):

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q
```
