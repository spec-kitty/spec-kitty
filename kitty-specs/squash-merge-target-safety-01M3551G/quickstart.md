# Verification Quickstart

Run the focused acceptance suite from the repository root:

```console
uv run --extra test pytest -q \
  tests/lanes/test_merge.py \
  tests/merge/test_forecast_seam.py \
  tests/merge/test_squash_target_newer_planning_3942.py \
  tests/merge/test_issue_2709_squash_provenance.py
```

Then run static checks for the changed production modules:

```console
uv run ruff check src/specify_cli/lanes/merge.py src/specify_cli/merge/forecast.py
uv run mypy src/specify_cli/lanes/merge.py src/specify_cli/merge/forecast.py
```

The focused tests cover rejected same-hunk source conflicts, ref and checkout
preservation, lossless disjoint changes, dry-run parity and schema stability,
registered-driver behavior, and both target-newer and source-newer PRIMARY
planning reconciliation.
