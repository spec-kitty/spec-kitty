# Quickstart — Terminus / Merge-Coord Integrity

How to reproduce the class red-first and verify the fix.

## Run the Tier-0 property test (the invariant)
```bash
# Red before the fix, green after (in-scope children):
PWHEADLESS=1 .venv/bin/python -m pytest tests/ -k "terminus_reconciliation and property" -q
```
Asserts: for any terminus command that exits 0, every approved WP's approved commits are reachable
from the target and no excluded commit is.

## Per-child reproductions (each red-first through its documented entry point)
```bash
# Group by seam; each test drives the real CLI entry point, not a mock:
PWHEADLESS=1 .venv/bin/python -m pytest tests/merge tests/coordination tests/git tests/lanes -q \
  -k "repro and (4945 or 4969 or 4970 or 4973 or 4977 or 4978 or 4981 or 4982 or 4985 or 4991 or 4996 or 4997)"
```

## Blast-radius suites (record commands + counts in the PR)
```bash
make test-fast                                  # shared baseline
PWHEADLESS=1 .venv/bin/python -m pytest tests/merge tests/coordination tests/git tests/lanes -q
pytest tests/architectural/test_no_legacy_terminology.py -q   # docs touch guard
```

## Manual smoke (the honest-failure path)
```bash
# Construct a divergent target (e.g. an approved WP's lane not projected), then:
spec-kitty merge --feature <mission>       # MUST exit non-zero + name the divergence, NOT exit 0
echo "exit=$?"                              # expect non-zero
```

## Gates before pushing
```bash
ruff check . && ruff format --check .
mypy src/specify_cli/{merge,coordination,git,lanes}
```
