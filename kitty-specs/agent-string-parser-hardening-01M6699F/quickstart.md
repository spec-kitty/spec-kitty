# Quickstart — Agent String Parser Hardening

Audience: automation-agent / software-engineer. Updated: 2026-10-30.

Verify the hardened parser through the pre-existing entry points, from the
repository root checkout (or the mission lane worktree during implement):

```bash
# 1. Unit rows (the three issue rows plus the untouched contracts)
uv run pytest tests/status/test_actor_boundary_normalize.py -q

# 2. The three explicit --agent paths refuse >4 segments before any write
uv run pytest tests/specify_cli/cli/commands/agent/test_structured_actor_annotations_6400.py \
              tests/specify_cli/cli/commands/agent/test_move_task_structured_actor_6400.py -q

# 3. Live spot-check of the parser contract
uv run python -c "
from specify_cli.status.models import parse_agent_boundary_string as p
assert p('claude: :') == ('claude', None, None, None)
assert p('claude\n') == ('claude', None, None, None)
assert p(' codex :: planner-priti: ') == ('codex', None, 'planner-priti', None)
try:
    p('a:b:c:d:e')
    raise SystemExit('expected ValueError')
except ValueError as e:
    print('refused:', e)
"

# 4. Types
uv run mypy src/specify_cli/status/models.py
```

Expected: all tests green; the spot-check prints a refusal naming the segment
count; mypy clean. Before the fix, steps 1–3 were red (that red state is the
committed failing-first evidence).
