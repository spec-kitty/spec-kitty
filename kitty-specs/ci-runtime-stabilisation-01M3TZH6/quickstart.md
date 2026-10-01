# Quickstart: validating CI runtime stabilisation

Audience: the implementer/reviewer of a work package in this mission, and the operator reading the evidence.

## Local, per work package (never the whole `tests/architectural`)

```bash
make test-fast
uv run --frozen pytest tests/ci/test_shard_select.py tests/ci/test_green_match.py -q          # as applicable
uv run --frozen pytest tests/architectural/<specific gate files the change implicates> -q
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q                    # prose/doctrine changes
uv run --frozen ruff check . && uv run --frozen ruff format --check .
uv run --frozen mypy scripts/ci/<new helper>.py
```

Partition proof without running the battery:

```bash
uv run --frozen python -m pytest tests/architectural -p scripts.ci.battery_partition_plugin --battery-part 1/2 --collect-only -q | tail -3
```

Companion regenerations when the relevant files change: `derive_pinning_inventory.py` (after `_gate_coverage.py` / `test_no_duplicate_suite_execution.py`), `capture_shard_timings.py --module consolidation` (FR-012), `PYTHONPATH=. python scripts/docs/docs_index.py --write` and `scripts/docs/check_docs_freshness.py --ci` (docs).

## On CI (mission branch)

1. Push the branch; the PR's own CI selects the battery because the diff touches `ci_config` paths (FR-007).
2. Dispatch the router in both modes: `gh workflow run ci-router.yml --ref <branch> -f mode=pr` and `-f mode=full`; dispatch the nightly once: `gh workflow run ci-nightly.yml --ref <branch>`.
3. For each run record in `evidence/ci-measurements.md`: run id, job, duration, `created: 4/4 workers` line, peak memory sampler line, slowest test.
4. Check NFR-001 (slowest of fast/legs median ≤ 14 min), NFR-002 (fast ≤ 5 min from start), NFR-003 (≤ 60% of ≤ 30-min timeouts; slowest test ≤ 180 s), NFR-005 (< 12 GB), NFR-006 (each consolidation shard p90 ≤ 15 min, the two shards within 25%) over ≥ 3 runs; NFR-003 also covers the nightly backstop (timeout ≤ 40 min, slowest run ≤ 24 min) and a slowest-test breach needs a fix or a recorded operator waiver; SC-001 = pipeline start → last battery job conclusion, SC-002 = pipeline start → fast gate job conclusion.
5. Consolidation runs for NFR-006: dispatch `gh workflow run ci-modules.yml --ref <branch> -f mode=full` three times (or use three nightly `full-module-matrix` runs) — the mission PR may not select the consolidation row.
6. Skip-if-green: open a draft PR (or toggle the mission PR to draft and back after a green run) and confirm the ready-for-review run logs the matched run; confirm a moved base runs normally.
