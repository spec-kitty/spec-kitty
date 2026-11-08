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

Expected: everything passes. `verdict_corpus.json` records today's **actual** verdict for every cell (mode × lane shape × approval-stamp state × window state), the known-wrong ones included, and every window state gives today's verdict. The intended verdicts are separate tests reporting `xfailed` (strict, `raises=AssertionError`): the commit between two approvals, the rewound work package, the #5048(b) read error, the resume dependency-lane move (closed world, approved bound, fully-canceled lane), and the forecast's excluded canceled work packages and coordination base. Each pin's control test proves it can fail: a removed name, a swapped refusal order (after asserting both refusals are present), a stale patch target.

The seeded mutations land now, before any code moves, and must already turn their named cells red:

```bash
uv run --frozen pytest -q tests/consolidation/test_reconciliation_seeded_mutations.py
```

## 2. Phase 2: the window-open SHA is recorded, and verdicts do not change

```bash
uv run --frozen pytest -q tests/status/test_wp_window_capture.py tests/consolidation/test_claim_inputs_parity.py
uv run --frozen pytest -q tests/architectural/test_dossier_sha_provenance.py \
  tests/architectural/test_status_module_boundary.py tests/architectural/test_cold_import_status_boundary.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py   # still identical
```

Inspect a real event: start a work package of a lane Mission with `implement` (it creates the lane branch before it records the claim), then read the row.

```bash
spec-kitty agent action implement WP01 --mission <handle>
tail -n 1 kitty-specs/<mission>/status.events.jsonl | jq '.policy_metadata'
# -> {"lane_head":"<sha>","wp_window":{"schema_version":1,"open_sha":"<same sha>"}}
```

Move another work package to `claimed` before its lane branch exists. The move succeeds and the row carries `wp_window.gap.reason == "lane_branch_missing"`. Then run `implement` on it: the `in_progress` row carries `open_sha`, and the reader skips the leading branch-missing opener and opens the window there (FR-021).

```bash
spec-kitty agent tasks move-task WP02 --to claimed --mission <handle>
tail -n 1 kitty-specs/<mission>/status.events.jsonl | jq '.policy_metadata.wp_window.gap'
```

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

Expected: the corpus golden file, the precedence matrix and the surface pin are byte-identical to Phase 1. Each seeded mutation (now retargeted through `RECONCILIATION_FAMILY` to the moved checks) still turns its named cell red, and the mutation test asserts that it does.

## 4. Phase 4: behaviour changes, red-first

For each behaviour change, check the commit order: the failing test is committed before its fix.

```bash
git log --oneline feat/consolidation-window-provenance -- \
  tests/consolidation/test_lane_approval_windows.py tests/consolidation/test_resume_frozen_anchors.py
uv run --frozen pytest -q tests/consolidation/test_lane_approval_windows.py \
  tests/consolidation/test_resume_frozen_anchors.py tests/consolidation/test_claim_inputs_parity.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py
git diff <phase-3 tip> -- tests/consolidation/characterization/verdict_corpus.json   # golden diff
```

Expected corpus delta: the golden diff touches only the cells NFR-002 (a)–(h) names, and each flipped cell's strict `xfail` marker is removed in its own fix commit. Every other verdict is unchanged. Every red-first test drives `consolidate`, `consolidate --dry-run` or `consolidate --resume` and asserts no branch moved on a refusal (NFR-010). The resume tests reach their state with the SIGKILL harness (`tests/terminus/rollback_harness.py`) and first assert that `state.json` holds the frozen dependency-lane tip. Record each red commit SHA in the PR's *Tests run* section.

Run the forecast against a fixture with a commit between two approvals, and look for the gap report:

```bash
spec-kitty consolidate --mission <handle> --dry-run --json | jq '.window_gaps, .error'
spec-kitty consolidate --mission <handle> --dry-run   # human block: "Window gaps (judged by the approval-stamp bound)"
```

Expected: `LANE_MOVED_AFTER_APPROVAL`, naming the stray commit and WP01, the same code as the fresh run. On the dependency-chain fixture (a dependent lane merged the stray commit and was approved) the stray commit is exempt. On a Mission written before the upgrade, every approved work package is listed with reason `not recorded`, and the verdict and refusal text are the pre-upgrade ones (today's check runs unchanged on an all-gap lane).

## 5. Quality gates (every phase)

```bash
uv run --frozen ruff check src/specify_cli/consolidation src/specify_cli/status tests/consolidation tests/status
uv run --frozen ruff format --check --force-exclude <changed files>
uv run --frozen mypy src/specify_cli/consolidation src/specify_cli/status
uv run --frozen pytest -q tests/architectural/test_no_legacy_terminology.py
```

Zero findings, no new `# noqa` / `# type: ignore`, and complexity ≤ 15 (ruff `C901`).
