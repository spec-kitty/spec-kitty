---
work_package_id: WP03
title: Nightly integration+next lane + red-to-P0 escalation
dependencies:
- WP02
requirement_refs:
- FR-006
- FR-007
- NFR-004
- NFR-005
planning_base_branch: feat/ci-coverage-honesty
merge_target_branch: feat/ci-coverage-honesty
branch_strategy: Planning artifacts for this mission were generated on feat/ci-coverage-honesty. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/ci-coverage-honesty unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T013
- T014
- T015
- T016
- T017
phase: Phase 3 - Nightly + escalation
history:
- at: '2026-09-25T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- scripts/ci/nightly_escalation.py
- tests/ci/test_nightly_escalation.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-nightly.yml
- scripts/ci/nightly_escalation.py
- tests/ci/test_nightly_escalation.py
- tests/architectural/test_module_shard_registry.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
Use `/ad-hoc-profile-load` to load `python-pedro` (implementer, claude) before anything else.

---

## Objectives & Success Criteria
Run the orphaned behavioral corpus on the nightly and make hidden reds self-surface as a deduped P0. Read `contracts/ci-workflow-contract.md`, `research.md` (D5/D6), `data-model.md`.

**Success**: `pytest tests/ci/test_nightly_escalation.py` green; the nightly lane job runs `tests/integration tests/next`, is in `nightly-summary.needs`, and each run-all-regardless suite calls the escalation step.

## Subtasks

### T011 — retire dead integration_tests_next tier + repoint its guard (FR-006, #4729)
Remove the `special_tiers.integration_tests_next` block from `.github/ci-module-registry.yml` (a sequential out-of-map edit — the registry is WP02-owned, but WP03 depends on WP02, so no parallel collision; record the rationale in the commit). Repoint `tests/architectural/test_module_shard_registry.py::test_special_tiers_encode_heavy_pole_deserialization` so it no longer asserts the retired tier exists — update it to assert the new nightly `tests/integration tests/next` lane (T013) is the heavy-pole home instead. Both land together so the guard is never left red. Leave a one-line registry comment pointing to the nightly lane.

### T013 — nightly integration+next lane (`ci-nightly.yml`, FR-006)
Add a job running `pytest tests/integration tests/next` (directory-based — NOT `-m integration`) with the existing `if: always()` + set-`+e` + exit-into-`$GITHUB_ENV` + terminal fail-loud (#4212) pattern, `PWHEADLESS=1` + per-worker HOME isolation. Measure durations with `pytest tests/integration tests/next --durations=0` and shard only if it overruns the per-shard timeout (NFR-004) — `capture_shard_timings.py` cannot measure a non-row dir.

### T014 — wire into aggregator (`nightly-summary.needs`)
Add the new job to `nightly-summary.needs` so its red surfaces in the aggregator.

### T015 — escalation helper (`scripts/ci/nightly_escalation.py`, FR-007)
CLI `--suite-key <key> --conclusion <success|failure> [--repo] [--run-url]`:
- `failure`: find open issues containing `<!-- nightly-escalation-key: <key> -->`; update the existing one if present, else create a `priority:P0` issue with the marker + run link. INV-5: at most one open per key.
- `success`: close the open issue for the key if any.
- Token/API absent (fork/outage): print a warning, exit 0 (degrade to fail-loud only), never echo the token (C-005).
Use the Actions token via `gh`/REST; SHA-pin nothing here (pure script).

### T016 — wire escalation step into each run-all-regardless suite
After each nightly suite (performance/e2e/stress/interpreter + the new integration lane), add a step (runs `if: always()`) invoking `nightly_escalation.py` with that suite's key and captured conclusion.

### T017 — unit tests (`tests/ci/test_nightly_escalation.py`)
Mock the GitHub client; cover create, update-existing (dedup, NFR-005), close-on-green, and token-absent degrade (exit 0, no crash, no token in output).

## Branch Strategy
Planning base `feat/ci-coverage-honesty` → main via squashed PR. Lane worktree per `lanes.json`. Depends on WP02.

## Definition of Done
- Lane runs both dirs, in nightly-summary.needs; escalation idempotent + fail-closed; tests green; ruff/mypy clean; workflow YAML valid.

## Reviewer guidance
Verify: dir-based selection (not marker); tests/next included; escalation dedup by body-marker; token-absent degrades not crashes; no token leak; job wired into aggregator.
