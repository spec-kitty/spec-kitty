# Contract: Coverage-Honesty Architectural Guards (REVISED per F17 — green-at-baseline)

Two new `tests/architectural/` guards + one green-preserving fix. All import-based (no test execution), built on `specify_cli.ast_analysis.imports` primitives with a full `ast.walk` (deferred/function-level imports count). Scoped for speed (NFR-002): scan limited to resolved test dirs + the src package walk (~1682 files parsed once, well under 5 s per F17 measurement).

**Landing posture: GREEN-at-baseline, NOT red-first.** The guards pass at a committed measured baseline (recording honest current debt) and fail only on a **regression** (a new dark package/root). Remediation SHRINKS the baseline. This means no red guard ever reaches `main`'s always-on `tests/architectural/` battery (dissolves GAP-2). See research D9/F17.

## Test-dir resolver (shared, pinned)

Resolve a row's test dirs with **module-tests.yml precedence**: explicit `test_dirs` if present, else `tests/{module}`. **Never** `_canonical_test_mirror`. Every resolved dir must exist on disk.

## foreign-coverage guard (`test_foreign_coverage_guard.py`, FR-001)

For every `ModuleRow` whose `roots:` resolve to importable src packages:
- **Dark-root baseline (shrink-only)**: enumerate declared roots that NO test in the row's resolved dirs imports (today: `next`→`specify_cli.runtime`). Compare against a committed baseline in `.github/ci-foreign-coverage-baseline.json`. FAIL only when a **new** dark root appears or a covered root regresses. Do NOT hard-fail today's baseline set.
- **Ratio ratchet (shrink-only)**: the row's own-root import ratio ≥ its committed baseline. Improvement ratchets up.
- **Exemptions (recorded)**: non-src-root rows (`ci`: `scripts/ci/**`, `.github/workflows/**`); self-declared aggregate/inventory rows (`execution_context`, `core_misc`, `unit`, `specify_cli_runtime`).

Passes at baseline today (records `next`'s dark root + all rows' current ratios). FR-004 (agent_utils explicit dir) ratchets agent's ratio up.

## src-reachability guard (`test_src_reachability_guard.py`, FR-002)

Enumerate importable packages by fs-walking `__init__.py` subpackages + loose top-level `*.py` modules under the 6 wheel roots. **Exclude data-only packages** = a package/dir with **no non-`__init__` `.py` module** (F18: covers both `schemas` (no `__init__.py`) AND data packages that HAVE an `__init__.py` but only ship `.yaml`/`.json`, e.g. `charter.activation.corpus`, `charter.activation.packs`, `specify_cli.skills.data`). Two tiers — **both shrink-only baselines (F18: no absolute zero — import-based static analysis structurally cannot see subprocess/CLI-tested modules like `specify_cli.__main__`/`encoding`, so a hard zero-floor would false-positive forever):**
- **Truly-dark baseline (shrink-only, hard-fail on GROWTH)**: a package imported by NO test **anywhere** (in-matrix ∪ out_of_matrix ∪ nightly). Measured **23 today** (F18). Seed as committed baseline; FAIL only when a NEW truly-dark package appears. This is the strongest honesty ratchet: no new untested-anywhere code can land.
- **In-matrix-dark baseline (shrink-only)**: packages imported only by out-of-matrix/nightly dirs. Measured **27 today** (F18, not the ~50 estimate). Seed as baseline; FAIL only when it GROWS. FR-005/009 shrink it by {live_work, config, calibration, tasks_authoring, diagnostics, bootstrap}; the guard asserts those left the baseline.

`live_work` is already in-matrix-reachable (via `tests/zeitgeist_client`) — FR-005 mints its row for per-PR *execution* of its 149 tests, and removes it from the in-matrix-dark baseline too if listed.

## phantom-mirror fix (`test_gate_selection_authority.py`, FR-003) — GREEN-PRESERVING

- Change the tree derivation to default `tests/{module}` (exists) instead of `_canonical_test_mirror` (phantom `tests/agent_utils`).
- Add INV-2: every derived module test dir EXISTS on disk. Apply strict self-reachability only to explicit-`test_dirs` rows; apply INV-2 + non-empty-routing (#4454) to all rows (the `agent` row routes `tests/agent`→[cli, execution_context], its own-root debt, not a phantom).
- **Must stay GREEN** (C-002) — baseline is 22 passed (F17).

## Sidecar baseline (`.github/ci-foreign-coverage-baseline.json`)

Committed, MEASURED (documented provenance header). Holds: per-row own-root ratios, the dark-root set, and the in-matrix-dark package set. All shrink-only. WP01 seeds it at current measured values (guards green at baseline); WP02 shrinks it.

## Unit tests (`tests/ci/test_coverage_guards.py`)

Exercise the lib directly: import-under-package (incl. a deferred import), resolver precedence, subpackage enumeration (excludes data dirs, includes loose modules), ratio computation, baseline shrink/grow logic (grow → fail, shrink → pass, equal → pass).
