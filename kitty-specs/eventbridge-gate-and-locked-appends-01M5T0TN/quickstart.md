# Quickstart

```python
from kernel.event_log_append import append_event_log_lines
append_event_log_lines(path, [json.dumps(row, sort_keys=True)])          # locked, torn-tail refusing, fsynced
```

```python
from runtime.next.event_bridge import bind_work_package_transition_port, reset_work_package_transition_port
bind_work_package_transition_port(recorder)   # tests / a future #6675 client
```

Verify:

```bash
.venv/bin/python -m pytest tests/kernel/test_event_log_append.py tests/architectural/test_event_log_writes_gate.py -q
```
