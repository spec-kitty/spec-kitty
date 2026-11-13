# Quickstart — verifying #7560

```bash
# acceptance (both report shapes + soundness ratchets)
.venv/bin/python -m pytest tests/consolidation/test_dependency_ref_mission_base_7560.py -q
# unit
.venv/bin/python -m pytest tests/consolidation/test_mission_base.py -q
# blast radius
make test-fast && .venv/bin/python -m pytest tests/consolidation -q -n auto --dist loadfile
```

Manual: on a fork whose local target lacks the Mission base, `spec-kitty consolidate --mission <m> --dry-run` prints `Mission base: derived (...)` and no pre-base commit is reported.
