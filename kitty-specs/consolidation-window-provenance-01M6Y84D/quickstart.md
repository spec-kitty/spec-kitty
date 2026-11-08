# Quickstart: verify consolidation window provenance locally

**Mission**: `consolidation-window-provenance-01M6Y84D` · **Date**: 2026-11-08
Run everything from the repository root checkout. The test files named below are created by the Mission. Before they exist, the commands show you what each phase must make green. Only targeted files run, never `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION).

## 0. Prepare the checkout

```bash
uv sync --frozen --all-extras      # a stale venv gives false import reds
make sync-packs                    # every checkout / lane needs the pinned built-in pack
make test-fast                     # shared baseline
```

## 1. Phase 1: pins exist and are green on unchanged code

```bash
uv run --frozen pytest -q \
  tests/consolidation/test_reconciliation_characterization.py \
  tests/consolidation/test_refusal_precedence_matrix.py \
  tests/consolidation/test_reconciliation_surface_pin.py \
  tests/consolidation/test_reconciliation_family_guard.py
```

Expected: everything passes. The intended-behaviour scenarios report `xfailed` (strict): the commit between two approvals, the #5048(b) read error, the resume dependency-lane move, and the forecast's excluded canceled work packages. Each pin's control test proves it can fail: a removed name, a swapped refusal order, a stale patch target.

## 2. Phase 2: the window-open SHA is recorded, and verdicts do not change

```bash
uv run --frozen pytest -q tests/status/test_wp_window_capture.py tests/consolidation/test_claim_inputs_parity.py
uv run --frozen pytest -q tests/architectural/test_dossier_sha_provenance.py \
  tests/architectural/test_status_module_boundary.py tests/architectural/test_cold_import_status_boundary.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py   # still identical
```

Inspect a real event: move a work package of a lane Mission to `claimed`, then read the row.

```bash
spec-kitty agent tasks move-task WP01 --to claimed --mission <handle>
tail -n 1 kitty-specs/<mission>/status.events.jsonl | jq '.policy_metadata'
# -> {"lane_head":"<sha>","wp_window":{"schema_version":1,"open_sha":"<same sha>"}}
```

Delete (or rename) the lane branch and repeat on another work package. The move succeeds, and `wp_window.gap.cause` is `lane_branch_missing`.

## 3. Phase 3: the split changes no verdict

```bash
uv run --frozen pytest -q tests/consolidation/ tests/terminus/        # owning subsystem dirs
uv run --frozen pytest -q tests/consolidation/test_reconciliation_seeded_mutations.py
uv run --frozen pytest -q tests/ci/test_reducer_lock_census.py \
  tests/architectural/test_dead_symbol_allowlist_contract.py tests/architectural/test_no_dead_modules.py \
  tests/architectural/test_exemption_registry_ratchet.py tests/consolidation/test_single_rollback_authority.py
wc -l src/specify_cli/consolidation/reconciliation*.py                 # every module <= 1,200
grep -c '^def \|^class ' src/specify_cli/consolidation/reconciliation.py   # facade: 0
```

Expected: the corpus, the precedence matrix and the surface pin are byte-identical to Phase 1. Each seeded mutation turns at least one scenario red, and the mutation test asserts that it does.

## 4. Phase 4: behaviour changes, red-first

For each behaviour change, check the commit order: the failing test is committed before its fix.

```bash
git log --oneline feat/consolidation-window-provenance -- tests/consolidation/test_lane_approval_windows.py
uv run --frozen pytest -q tests/consolidation/test_lane_approval_windows.py tests/consolidation/test_claim_inputs_parity.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py
```

Expected corpus delta: only the scenarios NFR-002 names flip from `xfailed` to passing. Every other verdict is unchanged.

Run the forecast against a fixture with a commit between two approvals, and look for the gap report:

```bash
spec-kitty consolidate --mission <handle> --dry-run --json | jq '.window_gaps, .error'
spec-kitty consolidate --mission <handle> --dry-run   # human block: "Window gaps (judged by the approval-stamp bound)"
```

Expected: `LANE_MOVED_AFTER_APPROVAL`, naming the stray commit and WP01, the same code as the fresh run. On a Mission written before the upgrade, every approved work package is listed with reason `not recorded`, and the verdict is the pre-upgrade one.

## 5. Quality gates (every phase)

```bash
uv run --frozen ruff check src/specify_cli/consolidation src/specify_cli/status tests/consolidation tests/status
uv run --frozen ruff format --check --force-exclude <changed files>
uv run --frozen mypy src/specify_cli/consolidation src/specify_cli/status
uv run --frozen pytest -q tests/architectural/test_no_legacy_terminology.py
```

Zero findings, no new `# noqa` / `# type: ignore`, and complexity ≤ 15 (ruff `C901`).
