# Quickstart: verify Decision log integrity

```bash
uv run --frozen pytest -q tests/specify_cli/decisions/test_service_open_concurrency.py \
  tests/specify_cli/decisions/test_index_fold_duplicate_open.py tests/decisions/test_decisions_reconciler.py
uv run --frozen pytest -q tests/architectural/test_event_log_writes_gate.py tests/architectural/test_status_events_writes_gate.py
```

Manual: run the reproducer from #4848 (Ivan-Melck, 2026-10-16) against this checkout; ARM A and
ARM B report 1 opening row each.
