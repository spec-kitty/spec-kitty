# Quickstart: CI Terminal-Cancel Verdict

## What ships
- `scripts/ci/fleet_verdict.py` — `classify` gains `infra-error` (4a) + comment line + docstring.
- `scripts/ci/stale_running_sweep.py` (new) — 4b stale-running detector.
- `tests/ci/test_fleet_verdict.py` / `test_fleet_main.py` — red-first 4a tests + migration.
- `tests/ci/test_stale_running_sweep.py` (new) — 4b detector + wiring guard.
- `.github/workflows/ci-stale-running-sweep.yml` (new) — scheduled 4b host.

## Run the tests (from repo root)
```bash
export PYTHONPATH=$(pwd)/src
uv sync --frozen --all-extras   # avoid stale-venv false reds (coverage/pytestarch)
uv run --frozen python -m pytest tests/ci/test_fleet_verdict.py tests/ci/test_fleet_main.py tests/ci/test_stale_running_sweep.py -q
```

## Pre-push gates
```bash
export PYTHONPATH=$(pwd)/src
uv run --frozen python -m pytest tests/ci/ -q
uv run --frozen ruff check .
uv run --frozen ruff format --check .            # separate gate
uv run --frozen python -m pytest tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen python -m pytest tests/contract/test_example_round_trip.py -q   # contract yaml skip marker
./actionlint .github/workflows/ci-stale-running-sweep.yml   # download binary; paste RAW output
```

## Manual smoke of classify
```bash
# fully-terminal + a cancelled required gate -> infra-error:
python3 -c "import sys; sys.path.insert(0,'scripts'); from ci.fleet_verdict import classify; \
print(classify({'g':{'status':'completed','conclusion':'cancelled'}}, set()))"   # -> infra-error
# cancel among an in-flight gate stays running (INV-2):
python3 -c "import sys; sys.path.insert(0,'scripts'); from ci.fleet_verdict import classify; \
print(classify({'g':{'status':'completed','conclusion':'cancelled'},'h':{'status':'in_progress'}}, set()))"  # -> running
```

## Post-merge verification (main-tip; NFR/SC)
- A real cancelled required run posts `[ci] infra-error @head` (not stranded on running) and creates no P0 for a cancelled `main` run.
- The scheduled sweep runs and (if any) flags a stale-running head as a `[ci-sweep]` watch item without releasing it.
