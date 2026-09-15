# Quickstart: RED-first verification per fix

Base commit for RED evidence: `36d866d4fa`. Run from the repo root with the synced `.venv`
(`uv sync --frozen --all-extras`). Each command below is RED on base and must go GREEN on the fix.

## #4360-B — selected-shard reconciler
```bash
.venv/bin/python -m pytest tests/ci/test_reconcile_shards.py -q
# RED today: the module does not exist yet / completeness demands all 37 shards.
# GREEN after: selected-shard completeness + must_be_fresh guard (contracts C-recon-1..4).
```

## #4454 — tests-only routing
```bash
.venv/bin/python -m pytest tests/architectural/test_gate_selection_authority.py -q -k "tests_only or owning_module"
# RED today: select_modules(["tests/status/test_store.py"]) == frozenset()
# GREEN after: returns the status module's group set.
```

## #4208 — router-gate classification
```bash
.venv/bin/python -m pytest tests/architectural/test_dual_mode_contract.py -q
# RED today: no timed_out distinction (contract C-gate-1).
# GREEN after: timed_out reported distinctly; blocking verdict unchanged (C-gate-2).
```

## #4212 — nightly fail-loud
```bash
.venv/bin/python -m pytest tests/architectural/test_performance_marker_guard.py -q
# RED today: suite steps discard pytest exit into an annotation string.
# GREEN after: each suite exit captured + terminal fail-loud step; run-all preserved.
```

## Blast-radius suite (before opening each PR)
```bash
make test-fast
# Plus the touched arch/CI battery for workflow/gate-selection changes:
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/ tests/ci/ -q
ruff check . && uv run --frozen ruff format --check .
```

Note (C-004): matrix-selection / aggregate-verdict / nightly-failure behaviour is asserted by the
workflow-lint + gate-selection-authority tests so correctness does not depend on a live CI run;
final confirmation of the workflow topology happens on the merged `main` tip.
