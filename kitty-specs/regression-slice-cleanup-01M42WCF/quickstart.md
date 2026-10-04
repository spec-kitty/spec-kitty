# Quickstart: verifying this mission

```bash
# what the regression slice selects (compare against the baseline in the PR body)
uv run --frozen pytest tests -m regression --collect-only -q | tail -1
# marker routing gates
uv run --frozen pytest tests/architectural/test_marker_job_completeness.py tests/architectural/test_ci_collection_completeness.py tests/architectural/test_fast_tier_marker_completeness.py -q
# the #5620 priority guard
uv run --frozen pytest tests/charter/test_charter_scope_config_reader.py -q
```
Planted-break records live in the PR body.
