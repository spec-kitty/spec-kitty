# Quickstart: verifying this mission

```bash
# Door bans and writes gate
.venv/bin/python -m pytest tests/architectural/test_status_unsafe_allowlist.py tests/architectural/test_status_events_writes_gate.py tests/architectural/test_no_dead_symbols.py -q
# Public-imports boundary
.venv/bin/python -m pytest tests/architectural/test_events_tracker_public_imports.py tests/architectural/test_shared_package_boundary.py -q
# Seam contract + timeout
.venv/bin/python -m pytest tests/status/test_fanout_timeout.py tests/status/test_adapters_contract.py -q
# No "saas" left on the seam
! grep -rni saas src/specify_cli/status/adapters.py
```
