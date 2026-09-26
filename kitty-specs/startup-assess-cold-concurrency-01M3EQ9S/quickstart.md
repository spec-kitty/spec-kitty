# Quickstart: reproduce and verify #3998

## Deterministic (the gate)

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/runtime/test_startup_torn_read_escalation.py tests/runtime/test_build_serialized.py -q
```

On main, before the fix, the entry-point tests fail with `RuntimeError: Asset changed during preparation: …`. After the fix they all pass.

## Fresh-home concurrency (PR evidence, not a gate)

Use Ivan's reproducer from the #3998 comment. Set `SPK_QA_SOURCE` to the repo root.

```bash
SPK_QA_SOURCE=$PWD bash repro.sh 16   # ×5, one run under `taskset -c 0-3`
SPK_QA_SOURCE=$PWD bash repro.sh 32   # ×5
```

Expected: every process in the `fresh HOME` row exits 0, with 0 tracebacks, and no `BUG CONFIRMED` line.

## Warm path unchanged

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/runtime/test_build_serialized.py -k warm -q
```
