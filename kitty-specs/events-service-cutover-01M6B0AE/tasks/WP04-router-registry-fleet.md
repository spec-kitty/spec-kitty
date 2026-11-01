---
work_package_id: WP04
title: Router, registry and fleet wiring
dependencies:
- WP03
requirement_refs:
- FR-005
- FR-012
planning_base_branch: issue-6915-events-service-cutover
merge_target_branch: issue-6915-events-service-cutover
branch_strategy: Planning artifacts for this mission were generated on issue-6915-events-service-cutover. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6915-events-service-cutover unless the human explicitly redirects the landing branch.
subtasks:
- T016
- T017
- T018
- T019
phase: Phase 3 - CI
history:
- at: '2026-11-01T08:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-router.yml
- .github/workflows/module-tests.yml
- .github/workflows/ci-fleet-verdict.yml
- .github/ci-module-registry.yml
- tests/release/ci_retirement_scrub.json
- scripts/ci/fleet_verdict.py
- tests/ci/test_ci_module_wiring.py
- tests/ci/test_contracts_routing.py
- tests/ci/test_fleet_verdict.py
- tests/ci/test_fleet_main.py
- tests/ci/test_mission_status_routing.py
- tests/architectural/test_gate_selection_authority.py
- tests/architectural/test_module_shard_registry.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load the assigned profile with the `/spk-charter-profile-load` skill (`python-pedro`), then load `spec-kitty charter context --action implement`. Read `research/code-grounding.md` for the facts this WP relies on.

## Branch Strategy

- Planning/base branch: `issue-6915-events-service-cutover`; final merge target: `issue-6915-events-service-cutover`.
- Topology `single_branch`: no lane worktree. `lanes.json` holds one repo-root lane; work in the repository root checkout.
- Start with: `spec-kitty agent action implement WP04 --agent <name> --mission events-service-cutover-01M6B0AE`.
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>` and `Refs #6915`. No model identifier in commits.

## Objective

The CI jobs that run the repointed suites fetch the pinned extras with the sync-services action; routing, the module registry, its retirement scrub and the fleet verdict stop naming `services/`, the torn-tail resources, the conformance resources and the three retiring workflows. The wiring ratchet in `tests/ci/test_sync_services.py` (red since WP01) turns green. Requirements: FR-005, FR-012 (routing part).

Exact line references are in `research/code-grounding.md` §1 and §4 (from the CI inventory); re-check them, the files are hot.

## Subtasks

### T016 — Router

`.github/workflows/ci-router.yml`:
- `tests-corpus-blocking` (`~:1282`): after "Sync packs", add `- name: Sync the pinned service extras` / `uses: ./.github/actions/sync-services` / `with: { extras-only: 'true' }`.
- `tests-contract-tools` (`~:1329`): it installs with `--no-install-project` and inlines the packs sync because `tests/ci/test_contracts_workflows.py` allowed only SHA-pinned external actions in this job. That test is deleted in WP06, but must not go red now: either delete its job-pin assertion here (it belongs to the retiring contracts workflows) or keep the inline style — add an inline equivalent: an `actions/cache` restore keyed `services-${{ runner.os }}-${{ hashFiles('pins/*.source.yaml') }}` on `~/.cache/spec-kitty/services` plus `PYTHONPATH="${GITHUB_WORKSPACE}/src" uv run --frozen --no-sync python scripts/sync_services.py --service all --extras-only`. Prefer the composite action if the pin test allows it after your check; record the choice. Update the job's comment (tool unit tests are gone in WP06; the job now runs the remaining `tests/contract` corpus modules).
- Path groups: drop the glossary torn-tail glob (`~:353-354`), the `ci` group's `services/mission-status-api/**` and its comment (`~:480-486`), the `contract_tools` group's `contracts.yml`/`contracts-release.yml` (`~:516-517`) and the `services/.../conformance/**` / `artifact-conformance/**` globs (`~:587-590`). Add `pins/**`, `scripts/sync_services.py`, `.github/actions/sync-services/**` and `tests/pinned_service_assets.py` to `contract_tools` (and the `glossary` group gets `pins/**` so a pin bump re-runs the torn-tail goldens). Narrow `corpus`'s `contracts/**` to `contracts/fixtures/**` and fix the comments that say `corpus` owns `contracts/**`.

### T017 — Module shards

`.github/workflows/module-tests.yml`: after the warmup step, add the sync-services action with `extras-only: 'true'` (≈230 KB, cached on the pin hash). Needed by the glossary shard (torn-tail goldens) and any shard collecting `tests/contract`. Check whether a test pins module-tests' step list (`grep -rn "module-tests.yml" tests/ci tests/architectural`) and update it.

### T018 — Registry, scrub, fleet

- `.github/ci-module-registry.yml`: drop the glossary torn-tail root (`~:267-268`), the `ci` services root (`~:425`, comment `~:461-463`); fix the corpus prose (`~:772-782`). Leave the `fast_gate` entry for `test_events_import_frozen.py` (`~:969`) to WP06, which deletes that test.
- `tests/release/ci_retirement_scrub.json`: mirror (`~:171`, `~:252` verbatim; `~:287-290`).
- `scripts/ci/fleet_verdict.py:46-47` `PR_WORKFLOWS`: drop `contracts.yml`, `mission-status-api.yml`. `.github/workflows/ci-fleet-verdict.yml:5`: drop `Contracts`, `Mission Status API`.

### T019 — Tests

- `tests/ci/test_ci_module_wiring.py:59-66`: drop the services root.
- `tests/ci/test_contracts_routing.py`: corpus glob is `contracts/fixtures/**`.
- `tests/ci/test_fleet_verdict.py`, `test_fleet_main.py`: rewrite expectations without the two workflows; retarget the tag-push case to a workflow that stays tag-triggered (find one with `on: push: tags`), or delete the case if none remains and say so.
- `tests/ci/test_mission_status_routing.py`: pins the conformance globs and `mission-status-api.yml`; delete it (its subject leaves) — the pins-only routing case below replaces its useful half.
- `tests/architectural/test_gate_selection_authority.py:252-265`: replace the services-only diff with a pins-only diff (`pins/read-service.source.yaml`) and assert it selects the `ci` module and the contract-tools router job — non-vacuous.
- `tests/architectural/test_module_shard_registry.py:744-751`: drop the services root.

## Validation

```bash
uv run --frozen pytest tests/ci/test_sync_services.py tests/ci/test_ci_module_wiring.py tests/ci/test_contracts_routing.py tests/ci/test_fleet_verdict.py tests/ci/test_fleet_main.py tests/ci/test_service_pins_gate.py tests/architectural/test_gate_selection_authority.py tests/architectural/test_module_shard_registry.py -q
actionlint .github/workflows/ci-router.yml .github/workflows/module-tests.yml .github/workflows/ci-fleet-verdict.yml   # if available
```
Also run every `tests/ci/test_*router*` / `*workflow*` file that parses ci-router.yml (`grep -ln "ci-router.yml" tests/ci tests/architectural`), by name.

## Definition of Done
- The wiring ratchet is green with a real job using the action.
- No router/registry/scrub entry names `services/` or the retiring workflows.
