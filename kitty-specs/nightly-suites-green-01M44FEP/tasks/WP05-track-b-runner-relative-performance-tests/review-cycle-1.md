---
affected_files: []
cycle_number: 1
mission_slug: nightly-suites-green-01M44FEP
reproduction_command:
reviewed_at: '2026-10-05T09:32:53Z'
reviewer_agent: reviewer-renata
wp_id: WP05
---

# WP05 review cycle 1: changes requested

Reviewer: reviewer-renata. The design is sound and honestly recorded. Two small changes are needed before a CI calibration run is meaningful.

1. **Planted tests record nothing and fail undiagnosably** (`tests/performance/test_owned_checkout_perf.py:178-209`, `tests/performance/test_cli_startup_budget_4409.py:343-359`). When the planted ratio lands under the limit the only output is "DID NOT RAISE". Record `planted_ratio`, `clean_ratio`, `plant_cost_fraction` and the three medians through `record_property` before `pytest.raises`.
2. **Correct the plant-band statement** (`docs/adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md:161`): an in-band plant still leaves the planted test red when its cost is below about `limit - clean ratio` (0.40 to 0.45 of the floor). State that as the detection threshold. In the same pass, `tests/_perf_helpers.py:40` and `test_cli_startup_budget_4409.py:23` describe the workload as imports only and omit the compile step.

Verified: not a relabelled budget; decision-record figures match the spike logs; no pre-existing assertion dropped; mutations turn the tests red; no product hook; 23 performance tests and 390 gate tests pass.
