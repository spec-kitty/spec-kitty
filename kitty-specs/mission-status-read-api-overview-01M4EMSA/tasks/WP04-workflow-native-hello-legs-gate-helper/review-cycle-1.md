---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-11T13:34:37Z'
reviewer_agent: reviewer-renata
wp_id: WP04
---

# WP04 cycle 1: returned before review (orchestrator, operator ruling)

The implementation found that the new workflow turns 26 tests red in `tests/ci/test_fleet_verdict.py` (25) and `tests/ci/test_fleet_main.py` (1). `scripts/ci/fleet_verdict.py::PR_WORKFLOWS` is a closed set of `pull_request` workflows.

The operator ruled on 2026-10-11 to register the workflow. This supersedes plan E-3; see reviews/analyze.ruling.md, DD-77, the amended WP04 prompt and the amended spec AC-15d. WP04's owned_files now include the four paths below.

| id | severity | file | problem | remedy |
|---|---|---|---|---|
| R1 | high | scripts/ci/fleet_verdict.py, .github/workflows/ci-fleet-verdict.yml, tests/ci/test_fleet_verdict.py, tests/ci/test_fleet_main.py | The new `pull_request` workflow is not registered in the fleet verdict, so the inventory check raises and 26 tests are red. After merge, the verdict job would fail on every PR. | Add `"mission-status-api.yml"` to `PR_WORKFLOWS`. Add the workflow's exact `name:` to `ci-fleet-verdict.yml` `on.workflow_run.workflows`. Update the expectations in the two fleet tests only where they enumerate the set. Do not weaken any assertion. Both test files must be fully green. |
| R2 | medium | tests/ci/test_mission_status_api_build.py (WP04 section) | The WP04 pins assert the workflow is NOT mentioned in `ci-fleet-verdict.yml`, which now contradicts the ruling. | Invert that pin: the workflow name IS listed in `ci-fleet-verdict.yml` and `mission-status-api.yml` IS in `PR_WORKFLOWS`. Keep the `ci-router.yml` absence pin. Add a revert row. |
| R3 | low | T022 sweep | The sweep list lacked the two fleet test files. | Include `tests/ci/test_fleet_verdict.py` and `tests/ci/test_fleet_main.py` in the T022 sweep, re-run it, and report the results. |
