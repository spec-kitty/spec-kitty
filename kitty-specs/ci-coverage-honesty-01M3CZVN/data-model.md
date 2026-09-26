# Data Model: CI Coverage Honesty

The "data" here is CI configuration + derived analysis structures, not a persisted database. Entities, their fields, invariants, and transitions.

## Entity: ModuleRow (`.github/ci-module-registry.yml` `modules[]` entry)

| Field | Type | Notes |
|-------|------|-------|
| `module` | str | unique key |
| `roots` | list[glob] | source globs that select this shard |
| `cov_targets` | list[pkg] | coverage packages |
| `test_dirs` | list[dir] | explicit test dirs; if absent → `tests/<module>` default |
| `shard_count` | int | MEASURED via LPT (NFR-001) |
| `tier` | str | standard/... |

**Invariants** (REVISED per F17 — green-at-baseline, shrink-only):
- INV-1a (dark-root baseline): the set of declared roots imported by NO test in the row's resolved dirs (resolver = explicit `test_dirs` else `tests/{module}`, NOT `_canonical_test_mirror`) may not GROW beyond the committed baseline. Today's baseline includes `next`→`specify_cli.runtime` (honest debt, not a hard fail). Non-src-root rows (`ci`) exempt/recorded.
- INV-1b (ratio ratchet): a row's own-root import ratio may not drop below its committed baseline. No fixed global threshold.
- INV-2 (existence): every resolved test dir EXISTS on disk (kills phantom mirrors).
- INV-3 (measured sharding): `shard_count` traces to a `ci-shard-timings.json` measurement.

**New/changed rows this mission**:
- `agent`: gains `test_dirs` including the real own-root dir **`tests/specify_cli/agent_utils`** (NOT the phantom `tests/agent_utils`, which does not exist) alongside `tests/agent` — FR-004.
- `live_work` (NEW): `roots: [src/specify_cli/live_work/**]`, `cov_targets: [specify_cli.live_work]`, `test_dirs: [tests/specify_cli/live_work]`, measured `shard_count`; justified by per-PR execution of its 149 tests (INV-4 already green via `tests/zeitgeist_client`) — FR-005.
- enrol in-matrix-dark packages `config`/`calibration`/`tasks_authoring`/`diagnostics`/`bootstrap` (their tests exist, in out_of_matrix dirs — promote) — FR-009. **`schemas` excluded** (data-only dir, no `__init__.py`, already content-tested).

## Entity: OutOfMatrixEntry (`out_of_matrix_test_dirs` / `special_tiers`)

| Field | Type | Notes |
|-------|------|-------|
| `dirs` | list[dir] | test dirs excluded from the per-PR/main matrix |
| `reason` | str | why deferred |

**Transition**: `tests/specify_cli/live_work` moves OUT of `out_of_matrix_test_dirs` INTO the new `live_work` ModuleRow.test_dirs (FR-005). `tests/integration` stays out of `modules[]` but is consumed by the nightly integration lane (C-003).

## Entity: SrcPackage (fs-walk of `__init__.py` subpackages + loose top-level modules under the 6 wheel roots)

| Field | Type | Notes |
|-------|------|-------|
| `import_path` | str | e.g. `specify_cli.live_work`, `specify_cli.agent_tasks_ports` |
| `reachable_by` | list[test_dir] | in-matrix test dirs importing it (full `ast.walk`, deferred imports count) |

**Invariant** (REVISED per F17→F18, both tiers shrink-only): INV-4a (truly-dark baseline) — packages imported by NO test anywhere may not GROW beyond the committed baseline (measured 23 today; hard-fail on a NEW one). INV-4b (in-matrix-dark baseline) — packages reachable only out-of-matrix/nightly (measured 27) may not GROW; remediation shrinks it. **Excludes data-only packages** = no non-`__init__` `.py` module (F18: `schemas`, `charter.activation.corpus`, `charter.activation.packs`, `specify_cli.skills.data`). fs-walked (226 packages), NOT the 6-entry pyproject list.

## Entity: NightlySuite (`ci-nightly.yml` run-all-regardless job)

| Field | Type | Notes |
|-------|------|-------|
| `suite_key` | str | stable id, e.g. `integration`, `performance`, `e2e`, `stress` |
| `selector` | str | how it runs (dir `tests/integration` or marker `-m e2e`) |
| `conclusion` | enum | success / failure / marker-empty(exit5=skip) |

**Transitions** (escalation state machine, FR-007):
```
green ──(run goes red)──▶ red: open-or-update P0 issue[suite_key], job fails loudly
red   ──(run goes green)─▶ green: resolve/close P0 issue[suite_key]
red   ──(still red)──────▶ red: UPDATE existing P0 (never a new issue)   [NFR-005]
any   ──(token/API absent)▶ degrade: fail-loud only, no issue mutation, exit 0 from escalation step [C-005]
```

## Entity: AutoP0Issue

| Field | Type | Notes |
|-------|------|-------|
| `suite_key` | str | dedup key, embedded as `<!-- nightly-escalation-key: <key> -->` in body |
| `state` | enum | open / closed |
| `labels` | list | includes `priority:P0` |

**Invariant**: INV-5 — at most one OPEN AutoP0Issue per `suite_key` at any time.

## Entity: ReleaseGate (`release.yml` precondition)

| Field | Type | Notes |
|-------|------|-------|
| `release_sha` | str | exact commit being released |
| `nightly_conclusion` | enum | success required to proceed |

**Invariant**: INV-6 — publish jobs (`build-release`→`publish-pypi`) run only if a `ci-nightly.yml` run for `release_sha` concluded `success`. Missing/red/in-flight-then-non-success ⇒ fail closed.
