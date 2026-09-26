# Quickstart: reproduce & verify

All commands from the repo root; editable install is LIVE (do NOT `pip install -e .`).

## Reproduce the defect (RED on the base)

```bash
PWHEADLESS=1 .venv/bin/python -m pytest \
  tests/terminus/test_repro_5038.py::test_5038_p1_clean_single_lane_squash_must_not_false_refuse \
  tests/terminus/test_repro_5038.py::test_5038_p2_genuine_projection_failure_still_refuses \
  tests/merge/test_reconciliation.py::test_squash_three_way_merge_resolution_is_unattributable \
  -v --no-header -p no:cacheprovider
# Base expectation: P1 XFAIL, P2 PASSED (floor), 3-way XFAIL.
```

Run the repros FROM THE LANE WORKTREE during implement — the terminus conftest resolves `_SRC`
from the test's own worktree.

## Verify after the fix

- `test_5038_p1_...` → PASSED (flipped by the real driver-replay fix, via the real `spec-kitty merge` CLI).
- `test_5038_p2_...` (re-grounded onto genuine coord-content loss) → still REFUSEs / PASSED-as-test.
- `test_squash_three_way_merge_resolution_is_unattributable` → still XFAIL (narrowed reason).

## Guardian + blast-radius suite (must stay green modulo honest xfails)

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/merge/ tests/terminus/ tests/coordination/ -q
```

## Quality gates

```bash
uv run --frozen ruff check src/specify_cli/merge/ tests/terminus/ tests/merge/
uv run --frozen ruff format --check src/specify_cli/merge/reconciliation.py   # format-gated file(s) only
.venv/bin/mypy --strict src/specify_cli/merge/
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py \
  tests/architectural/test_foreign_coverage_guard.py tests/architectural/test_no_dead_symbols.py -q
```

Do NOT reformat `executor.py`, `bookkeeping_projection.py`, `git_probes.py` (`[tool.ruff.format].exclude`).
Recapture `.github/ci-foreign-coverage-baseline.json` to the MEASURED value only if a new real-CLI
repro is added under `tests/terminus/`.
