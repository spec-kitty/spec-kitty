# Quickstart: verifying the nightly remediation

```bash
uv sync --frozen --all-extras
# FR-001..FR-007 (+ C1 perf resume test)
PWHEADLESS=1 .venv/bin/python -m pytest tests/integration tests/next -q -n auto --dist loadfile
SPEC_KITTY_RUN_PERFORMANCE=1 .venv/bin/python -m pytest -m performance \
  tests/integration/test_merge_resume.py tests/specify_cli/invocation/test_doctor_ops.py -q
# FR-008 / FR-009 regressions + merge blast radius
.venv/bin/python -m pytest tests/merge tests/cli/commands -q -n auto --dist loadfile
# FR-010 workflow-shape tests
.venv/bin/python -m pytest tests/ci -q
make test-fast
ruff check . && ruff format --check . && mypy <changed src files>
```
