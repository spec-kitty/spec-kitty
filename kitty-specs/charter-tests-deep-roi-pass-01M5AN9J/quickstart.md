# Quickstart: reviewing one file

1. Read the file top to bottom; for each test, classify it against the #6485 rubric.
2. For a deletion candidate, find the covering test (`grep -rn "<symbol>" tests/charter_offering tests/architectural tests/charter`) and confirm it exercises the same behaviour.
3. Edit the file, then run it plus every covering test you named:
   `PWHEADLESS=1 .venv/bin/python -m pytest <file> <covering tests> -q -p no:cacheprovider`
4. Measure the coverage effect of your removals on the modules the file targets:
   `.venv/bin/python -m pytest <file> --cov=src/charter/<module> --cov-report=term-missing -q`
5. Record rows in `roi-ledger/WP0N.md`, then run
   `ruff check <files>` and `ruff format --check --force-exclude <files>`.
