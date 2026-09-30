# Quickstart: verifying this mission

```bash
# Protected-target preflight (real CLI, real git)
.venv/bin/python -m pytest tests/terminus/test_protected_target_preflight.py -q
# Post-mutation rollback, one planted failure per phase
.venv/bin/python -m pytest tests/terminus/test_rollback_door.py -q
# The pin
.venv/bin/python -m pytest tests/consolidation/test_single_rollback_authority.py -q
```
