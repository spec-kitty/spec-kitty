# Quickstart: verifying the decomposition locally

```bash
uv sync --frozen --all-extras
# targeted suites (no make test-full, no whole tests/architectural/)
.venv/bin/python -m pytest tests/consolidation tests/specify_cli/consolidation tests/orchestrator_api tests/lanes -n 4 --dist loadfile -q
.venv/bin/python -m pytest tests/terminus -n 4 --dist loadfile -q
make test-fast
# named gate files (see research/code-grounding.md §3)
.venv/bin/python -m pytest tests/consolidation/test_single_rollback_authority.py tests/architectural/test_destructive_op_routing.py -q
# where things live now
ls src/specify_cli/consolidation/{executor,run_state,phase_*,coord_strand,entry_preflight,resume_recovery}.py src/specify_cli/consolidation/mission_number/
```
