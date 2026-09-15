# Contract: CI YAML shape (golden-YAML pins)

These are the exact resolved shapes the golden-YAML pytest assertions must enforce, using the canonical pattern from `tests/architectural/test_dual_mode_contract.py` (`yaml.safe_load(path.read_text())`; note PyYAML parses bare `on:` as boolean `True`, so read `doc[True]` for the trigger block).

## C-YAML-1 — `ci-router.yml` top-level concurrency (Lever 1a)

```yaml
concurrency:
  group: ci-router-${{ github.event_name == 'push' && github.sha || github.ref }}
  cancel-in-progress: ${{ github.event_name != 'push' }}
```

Assertions (NEW pin, `tests/architectural/test_dual_mode_contract.py`) — **EXACT equality, not substring** (a substring pin like `"github.sha" in group` passes for a broken always-cancel expression such as `${{ github.event_name != 'push' || true }}`, silently re-enabling the main cancel-cascade — the exact hole FR-001 closes; Renata HIGH / Debbie LOW):
- `workflow["concurrency"]["group"] == "ci-router-${{ github.event_name == 'push' && github.sha || github.ref }}"`.
- `workflow["concurrency"]["cancel-in-progress"] == "${{ github.event_name != 'push' }}"`.
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

Assertions (NEW pin, `tests/ci/test_fleet_verdict.py`) — **EXACT equality** (a substring `head_sha in group` passes for a broken expression that drops the `workflow_run.` path and collapses ALL tips into one shared `cancel:true` group = the cross-tip-cancel NFR-002 forbids; Renata/Debbie):
- top-level `workflow["concurrency"] == {"group": "ci-fleet-verdict-${{ github.event.workflow_run.head_sha }}", "cancel-in-progress": True}`.

## C-YAML-4 — `report-main` job concurrency — **UNCHANGED (negative pin)**

> **Reversed post-plan squad (Alphonso MAJOR, operator-ratified 2026-09-15).** Moving `report-main` to per-SHA coalesce opens a create-create race on the single `from:ci` incident issue. `report-main` is therefore **left unchanged**; the fan-out cap is delivered entirely by C-YAML-2 (types trim) + C-YAML-3 (top-level coalesce), which cut `report-main` inflow to ≈1/tip so the existing single-group queue drains trivially.

```yaml
jobs:
  report-main:
    concurrency:
      group: ci-fleet-verdict-main
      cancel-in-progress: false
```

Assertion (existing `tests/ci/test_fleet_main.py:166` **stays green as-is — do NOT change it**):
- `job["concurrency"] == {"group": "ci-fleet-verdict-main", "cancel-in-progress": False}`.
- This preserves cross-tip incident-issue serialization (edge case: two concurrent red tips cannot both create an incident).

## C-YAML-5 — `report` (PR) job concurrency (unchanged — negative pin)

```yaml
jobs:
  report:
    concurrency:
      group: ci-fleet-verdict-pr-${{ matrix.pr }}
      cancel-in-progress: false
```

Assertion (existing `test_fleet_verdict.py:126-127` stays green): `matrix.pr` in group; `cancel-in-progress is False`. **Must not change** (FR-002 / invariant CK-2).

## C-YAML-6 — `report` (PR) job comment refresh (Alphonso/Debbie INFO)

The `report` (PR) job's `cancel-in-progress: false` + its comment ("Global concurrency could lose another PR", `ci-fleet-verdict.yml:40-41`) become semantically stale once the top-level per-SHA `cancel:true` block owns same-head coalescing (different PR heads never share the top-level group; the double-snapshot head-drift guard covers re-pushes). Implement task: **update the comment** at `:40-44` so a future reader knows the top-level key now carries that guarantee. No behavior change; not a golden-YAML pin.

## C-WIRE-1 — script-invocation wiring pins (mirror `test_router_gate_step_wiring...`)

New/kept assertions that the workflow steps still invoke the verdict scripts (so the fan-out cap cannot silently orphan them):
- `identify` step `run` text contains `scripts/ci/fleet_verdict.py` (or `-m scripts.ci.fleet_verdict`) and `attempts/` where a jobs-API call appears.
- `report` step invokes `fleet_verdict.py --pr`.
- `report-main` step invokes `python3 -m scripts.ci.fleet_main`.
