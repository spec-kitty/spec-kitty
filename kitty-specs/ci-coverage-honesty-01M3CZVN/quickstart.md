# Quickstart: CI Coverage Honesty

How to verify the mission end-to-end locally.

## Guards (RED-first → GREEN after remediation)

```bash
# Before remediation these FAIL (they encode the defect):
.venv/bin/python -m pytest tests/architectural/test_foreign_coverage_guard.py \
  tests/architectural/test_src_reachability_guard.py -q

# Authority gates must stay green throughout:
.venv/bin/python -m pytest tests/architectural/test_gate_selection_authority.py \
  tests/architectural/test_pyproject_shape.py -q
```

Expected after the mission: all four green together (C-002).

## Registry / selection

```bash
# live_work now selected on a source change to its root:
.venv/bin/python -c "from scripts.ci.gate_selection import select_modules; \
print('live_work' in select_modules(['src/specify_cli/live_work/authored.py'], mode='main'))"
# → True

# live_work test dir now selected on a test-only change:
.venv/bin/python -c "from scripts.ci.gate_selection import select_modules; \
print(select_modules(['tests/specify_cli/live_work/test_authored.py'], mode='main'))"
# → includes live_work
```

## Escalation helper

```bash
.venv/bin/python -m pytest tests/ci/test_nightly_escalation.py -q      # create/update/close/degrade
.venv/bin/python -m pytest tests/ci/test_release_nightly_gate.py -q    # green/dispatch/red/in-flight
```

## Sharding evidence (NFR-001)

```bash
.venv/bin/python scripts/ci/capture_shard_timings.py --module live_work --write
# shard_count in ci-module-registry.yml traces to ci-shard-timings.json
```

## Full local gate before pushing

```bash
make test-fast
.venv/bin/python -m pytest tests/architectural/ tests/ci/ -q
make format-check
ruff check .
```
