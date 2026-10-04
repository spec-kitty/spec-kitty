# Quickstart: verifying the finalize decomposition

```bash
# static gates
uv run --frozen ruff check src/specify_cli/cli/commands/agent/
uv run --frozen ruff format --check --force-exclude src/specify_cli/cli/commands/agent/mission_finalize*.py
.venv/bin/mypy src/specify_cli/cli/commands/agent/mission_finalize*.py

# seam invariants
.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_mission_finalize_phase_modules.py tests/_support/test_finalize_source.py -q

# behaviour parity: the finalize corpus
grep -rlE "mission_finalize|finalize_tasks|finalize-tasks" tests --include="*.py" > /tmp/ftests.txt
.venv/bin/python -m pytest $(cat /tmp/ftests.txt) -n 8 --dist loadfile -q
```

To find a phase, look at `docs/api/finalize-tasks-internals.md` → "Module map".
