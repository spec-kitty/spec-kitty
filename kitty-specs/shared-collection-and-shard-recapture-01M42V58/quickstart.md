# Quickstart: verifying the mission

Run from the repository root checkout with the synced environment (`uv sync --frozen --all-extras`). Use `uv run --no-sync` so the lock file is not rewritten.

## Collection store

```bash
# Unit and non-vacuity pins (no real collection)
uv run --no-sync pytest tests/architectural/test_universe_store.py tests/ci/test_collect_universe_prestep.py -q

# Real path, on a clean checkout: first call collects, second reuses
export SK_GATE_REUSE_REPORT="$(mktemp)"
uv run --no-sync python -m scripts.ci.collect_universe_prestep collect   # outcome: collected
uv run --no-sync python -m scripts.ci.collect_universe_prestep collect   # outcome: reused
uv run --no-sync python -m scripts.ci.collect_universe_prestep check
uv run --no-sync python -m scripts.ci.collect_universe_prestep compare   # 0 differences
```

## Workflow shape

```bash
uv run --no-sync pytest tests/ci/test_ci_workflow_prestep_shape.py -q
```

## Recapture and provenance

```bash
uv run --no-sync pytest tests/ci/test_recapture_shard_timings.py tests/architectural/test_shard_capture_provenance.py -q

# Report drift without writing
uv run --no-sync python -m scripts.ci.recapture_shard_timings

# Strict agreement at the capture commit
SPEC_KITTY_STRICT_SHARD_TIMINGS=1 uv run --no-sync pytest tests/architectural/test_module_length_agreement.py -q
```

## CI evidence (after the pull request is open)

For three per-PR runs, read each consuming job's summary: the pre-test step duration, every report line `reused`, and the setup time of the slowest collecting test. Record them in `evidence/ci-measurements.md`.
