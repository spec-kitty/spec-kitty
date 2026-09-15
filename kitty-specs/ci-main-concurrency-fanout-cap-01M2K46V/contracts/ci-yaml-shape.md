# Contract: CI YAML shape (golden-YAML pins)

These are the exact resolved shapes the golden-YAML pytest assertions must enforce, using the canonical pattern from `tests/architectural/test_dual_mode_contract.py` (`yaml.safe_load(path.read_text())`; note PyYAML parses bare `on:` as boolean `True`, so read `doc[True]` for the trigger block).

## C-YAML-1 — `ci-router.yml` top-level concurrency (Lever 1a)

```yaml
concurrency:
  group: ci-router-${{ github.event_name == 'push' && github.sha || github.ref }}
  cancel-in-progress: ${{ github.event_name != 'push' }}
```

Assertions (NEW pin, `tests/architectural/test_dual_mode_contract.py`):
- `workflow["concurrency"]["group"]` contains `github.sha` **and** `github.event_name == 'push'` **and** `github.ref`.
- `str(workflow["concurrency"]["cancel-in-progress"])` contains `github.event_name != 'push'`.
- The `on:` block still has `push.branches == ['main']`, the `pull_request` trigger, and `workflow_dispatch` (unchanged).

## C-YAML-2 — `ci-fleet-verdict.yml` trigger types (Lever 2a.1)

```yaml
on:
  workflow_run:
    workflows: [ ...8 unchanged... ]
    types: [completed]
```

Assertions (UPDATE `tests/ci/test_fleet_verdict.py` around `:125`):
- `set(trigger["types"]) == {"completed"}`  ← was `{"requested","in_progress","completed"}`.
- `set(trigger["workflows"])` unchanged (still the full registered set).

## C-YAML-3 — `ci-fleet-verdict.yml` top-level concurrency (Lever 2a.2)

```yaml
concurrency:
  group: ci-fleet-verdict-${{ github.event.workflow_run.head_sha }}
  cancel-in-progress: true
```

Assertions (NEW pin, `tests/ci/test_fleet_verdict.py`):
- top-level `workflow["concurrency"]["group"]` contains `github.event.workflow_run.head_sha`.
- `workflow["concurrency"]["cancel-in-progress"] is True`.

## C-YAML-4 — `report-main` job concurrency (Lever 2a.3)

```yaml
jobs:
  report-main:
    concurrency:
      group: ci-fleet-verdict-main-${{ github.event.workflow_run.head_sha }}
      cancel-in-progress: true
```

Assertions (UPDATE `tests/ci/test_fleet_main.py:166`):
- `job["concurrency"]["group"]` contains `ci-fleet-verdict-main-` **and** `head_sha`.
- `job["concurrency"]["cancel-in-progress"] is True`  ← was `False` with a static `ci-fleet-verdict-main` group.
- The `report-main` `if:`, `permissions` (issues:write), and checkout `persist-credentials` assertions in that test remain unchanged.

## C-YAML-5 — `report` (PR) job concurrency (unchanged — negative pin)

```yaml
jobs:
  report:
    concurrency:
      group: ci-fleet-verdict-pr-${{ matrix.pr }}
      cancel-in-progress: false
```

Assertion (existing `test_fleet_verdict.py:126-127` stays green): `matrix.pr` in group; `cancel-in-progress is False`. **Must not change** (FR-002 / invariant CK-2).

## C-WIRE-1 — script-invocation wiring pins (mirror `test_router_gate_step_wiring...`)

New/kept assertions that the workflow steps still invoke the verdict scripts (so the fan-out cap cannot silently orphan them):
- `identify` step `run` text contains `scripts/ci/fleet_verdict.py` (or `-m scripts.ci.fleet_verdict`) and `attempts/` where a jobs-API call appears.
- `report` step invokes `fleet_verdict.py --pr`.
- `report-main` step invokes `python3 -m scripts.ci.fleet_main`.
