# Quickstart

## Reproduce the defect (end to end, ~5 min per arm)

```bash
RUN_ROOT=/tmp/sk-5460 python3 /home/user/Documents/code/test/qa/round18/repro_pull_reverts_discard.py \
  /home/user/Documents/code/test/qa/source/.venv/bin/spec-kitty trigger   # expect RESULTS {'trigger': 'lost'} before the fix, 'kept' after
```

## Run the mission's targeted tests

```bash
cd /home/user/Documents/code/test/qa/source
SPEC_KITTY_RUN_P0_REPRO=1 .venv/bin/python -m pytest tests/consolidation/test_meta_driver_base_aware_5460.py -q   # red before the fix
.venv/bin/python -m pytest tests/consolidation/test_merge_drivers.py tests/consolidation/test_squash_reconcilers_2709.py \
  tests/consolidation/test_mission_number_truthful_4900.py tests/consolidation/test_merge_driver_goldens.py -q -k meta
```

## Goldens

The three new case directories under `tests/consolidation/merge_driver_goldens/merge-driver-meta/` are hand-authored (correct bytes, red on the pre-fix driver). Do **not** run `_capture.py` over the five existing cases; the PR must show zero diff there. To verify a new case by hand: `python -m specify_cli merge-driver-meta O A B` from a copy of the case directory and diff `A` against `expected_A`.

## Gates to run after prose/doc edits

```bash
.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q
.venv/bin/python scripts/docs/check_docs_freshness.py --ci
.venv/bin/ruff format --check src/specify_cli/consolidation/drivers.py src/specify_cli/cli/commands/merge_driver.py tests/consolidation/test_meta_driver_base_aware_5460.py
.venv/bin/ruff check <same files>; .venv/bin/mypy src/specify_cli/consolidation/drivers.py
```
