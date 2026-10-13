---
work_package_id: WP03
title: Evidence bundle script and nightly job
dependencies:
- WP02
requirement_refs:
- FR-010
- FR-011
- NFR-003
- NFR-004
- SC-002
- SC-003
planning_base_branch: ccr-002603b2-bip646
merge_target_branch: ccr-002603b2-bip646
branch_strategy: Planning artifacts for this mission were generated on ccr-002603b2-bip646. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into ccr-002603b2-bip646 unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
- T011
history: []
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- scripts/ci/acceptance_evidence.py
- tests/ci/test_acceptance_evidence.py
- tests/ci/test_acceptance_bdd_job.py
execution_mode: code_change
model: ''
owned_files:
- scripts/ci/acceptance_evidence.py
- tests/ci/test_acceptance_evidence.py
- tests/ci/test_acceptance_bdd_job.py
- .github/workflows/ci-nightly.yml
role: implementer
tags: []
tracker_refs: []
---

# WP03: Evidence bundle script and nightly job

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Implementation command: `spec-kitty agent action implement WP03 --agent claude --mission acceptance-scenario-contract-01M4T9GC`

---

## Objective

Write one versioned `evidence.json` per nightly leg and make the upload strict.

## Context

Plan IC-03 and `contracts/evidence.schema.json`. Depends on WP02's folder layout `acceptance-jvm/build/acceptance/<pass>/{allure-results,cucumber.json,junit}`.

### Subtask T008: Tests first for `scripts/ci/acceptance_evidence.py`

- **Steps**: `tests/ci/test_acceptance_evidence.py` with fixtures building pass folders in `tmp_path`: passed gating + empty wip; failed gating; missing gating; multiple JUnit files summed; environment.properties parsed; run URL from env; schema validated with a minimal in-test checker (no `jsonschema` dependency unless already available). Red first.

### Subtask T009: The script

- **Steps**: stdlib only; `main(argv)` with `--root`, `--os`; per pass sum `tests/failures/errors/skipped` across `junit/*.xml` (`testsuite` or `testsuites` roots); `outcome` = `missing` when no XML, `failed` when failures+errors > 0, else `passed`; read `cli.version` and `commit.sha` from the gating pass's `allure-results/environment.properties` (fall back to wip); `run_url` from `GITHUB_SERVER_URL/GITHUB_REPOSITORY/actions/runs/GITHUB_RUN_ID` when set; result paths relative to `--root`. Complexity ≤ 15 per function; `ruff`, `mypy` clean.

### Subtask T010: Nightly job

- **Steps**: in `acceptance-bdd`: drop `|| github.event_name == 'pull_request'` from `if:`; gating step `gradle -p acceptance-jvm test --no-daemon -Pacceptance.pass=gating`; wip step `-Pacceptance.pass=wip` (keep `continue-on-error`); new step `if: always()` running `uv run --frozen --no-sync python -m scripts.ci.acceptance_evidence --root acceptance-jvm/build/acceptance --os "${{ matrix.os }}"`; upload path `acceptance-jvm/build/acceptance/`, `if-no-files-found: error`, `retention-days: 30`. Update the step comments.

### Subtask T011: Pin the job

- **Steps**: `tests/ci/test_acceptance_bdd_job.py` using `tests/architectural/_gate_coverage.load_spliced_workflow` to assert: no `pull_request` in the job `if:`; both gradle steps use `-Pacceptance.pass=` and no `cucumber.filter.tags`; the evidence step exists with `if: always()`; upload name, single path, `error`, `retention-days: 30`.

## Definition of Done

- T008 to T011 done; `uv run --frozen pytest -q tests/ci/test_acceptance_evidence.py tests/ci/test_acceptance_bdd_job.py tests/contract/test_gradle_pin_check.py` green; `ruff check`, `ruff format --check --force-exclude`, `mypy` on the new script clean.

## Risks

- A failing gating step must not skip the evidence or upload steps (`if: always()`).

## Reviewer Guidance

- Counts must come from the JUnit XML, never from step outcomes alone.
