# Quickstart

```python
from kernel.ledger_append import append_ledger_lines
append_ledger_lines(path, [json.dumps(row, sort_keys=True)])          # locked, torn-tail refusing, fsynced
```

```python
from runtime.next.event_bridge import bind_work_package_transition_port, reset_work_package_transition_port
bind_work_package_transition_port(recorder)   # tests / a future #6675 client
```

Verify:

```bash
.venv/bin/python -m pytest tests/kernel/test_ledger_append.py tests/architectural/test_event_log_writes_gate.py -q
```
