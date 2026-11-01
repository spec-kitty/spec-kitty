---
work_package_id: WP06
title: Remove the copies and their coupling
dependencies:
- WP05
requirement_refs:
- FR-011
- FR-013
- C-004
- SC-001
- SC-005
planning_base_branch: issue-6915-events-service-cutover
merge_target_branch: issue-6915-events-service-cutover
branch_strategy: Planning artifacts for this mission were generated on issue-6915-events-service-cutover. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6915-events-service-cutover unless the human explicitly redirects the landing branch.
subtasks:
- T024
- T025
- T026
- T027
phase: Phase 4 - Remove and release
history:
- at: '2026-11-01T08:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: services/
create_intent:
- tests/architectural/test_events_cutover_absent.py
execution_mode: code_change
model: ''
owned_files:
- services/**
- contracts/**
- .github/workflows/mission-status-api.yml
- .github/workflows/contracts.yml
- .github/workflows/contracts-release.yml
- .github/CODEOWNERS
- .gitattributes
- NOTICE
- pyproject.toml
- scripts/ci/mission_status_gate_checks.py
- tests/architectural/test_events_import_frozen.py
- tests/architectural/test_no_duplicate_suite_execution.py
- tests/architectural/test_events_cutover_absent.py
- tests/ci/test_mission_status_api_build.py
- tests/ci/test_mission_status_gate_checks.py
- tests/ci/test_contracts_workflows.py
- tests/contract/test_breaking_check.py
- tests/contract/test_bundle.py
- tests/contract/test_citation_check.py
- tests/contract/test_client_smoke.py
- tests/contract/test_codeowners_check.py
- tests/contract/test_contract_resolver.py
- tests/contract/test_enum_pin_check.py
- tests/contract/test_event_mapping_check.py
- tests/contract/test_example_check.py
- tests/contract/test_fixture_builder.py
- tests/contract/test_gradle_pin_check.py
- tests/contract/test_install_tools.py
- tests/contract/test_layout_check.py
- tests/contract/test_leak_patterns.py
- tests/contract/test_leak_scan.py
- tests/contract/test_lint_ruleset.py
- tests/contract/test_no_pytest_scan.py
- tests/contract/test_provisional_check.py
- tests/contract/test_release_check.py
- tests/contract/test_resolver_parity.py
- tests/contract/test_run_negative_cases.py
- tests/contract/test_schema_formats.py
- tests/contract/test_structure_check.py
- tests/contract/test_tamper_check.py
- tests/contract/test_verify_pins.py
- tests/contract/test_mission_status_examples.py
- tests/contract/test_mission_status_contract_1_1.py
- tests/contract/fixtures/mission_status_pre_slice/**
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
- Start with: `spec-kitty agent action implement WP06 --agent <name> --mission events-service-cutover-01M6B0AE`.
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>` and `Refs #6915`. No model identifier in commits.

## Objective

Remove core's copies of the events domain's Java service and contracts and everything that existed only for them. After this WP, ADR `2026-10-29-1`'s Confirmation holds: `services/`, `mission-status-api.yml`, `contracts.yml` and `contracts-release.yml` are absent. Requirements: FR-011, FR-012, FR-013, C-004.

## Subtasks

### T024 — Red absence test

`tests/architectural/test_events_cutover_absent.py` (mark like the neighbouring fast architectural gates; check `tests/architectural/conftest.py`/markers):
- `services/` does not exist; `contracts/` holds exactly `fixtures/fixture_0*.json` (5 files, assert the set);
- the three workflows do not exist;
- no file under `.github/` (workflows, actions, CODEOWNERS, registry), `Makefile`, `pyproject.toml`, `.gitattributes`, `NOTICE` names `services/mission-status-api` or `contracts/tools` / `contracts/mission-` — non-vacuity: a planted string in a tmp copy is detected (self-test of the scanner function).
- `pins/read-service.source.yaml` loads (ties the absence to the replacement).
Commit red. Register it where the registry needs a home for new architectural files (check `.github/ci-module-registry.yml` `fast_gate`; `test_ci_module_wiring` may require every architectural file to be listed). Replace the `fast_gate` entry of `test_events_import_frozen.py` (`~:969`) with this file.

### T025 — Delete

```bash
git rm -r -q services .github/workflows/mission-status-api.yml .github/workflows/contracts.yml .github/workflows/contracts-release.yml
git rm -r -q contracts/mission-status contracts/mission-write contracts/_shared contracts/tools contracts/lint contracts/gradle contracts/README.md contracts/build.gradle contracts/settings.gradle
ls -A contracts; ls contracts/fixtures   # anything else left? decide per file, report
```

### T026 — Delete the gate and copy-only tests

- `tests/architectural/test_events_import_frozen.py` (ADR D-9 exit: removed with `services/`).
- `scripts/ci/mission_status_gate_checks.py`, `tests/ci/test_mission_status_gate_checks.py`, `tests/ci/test_mission_status_api_build.py`, `tests/ci/test_contracts_workflows.py` (build/workflow pins of removed subjects; events carries the build pins). Before deleting `test_contracts_workflows.py`, check whether its "every `tests/contract` module has exactly one home" rule protects anything still alive; if so, move that one assertion to `tests/ci/test_contracts_routing.py` (owned by WP04 — out-of-map edit with a one-line rationale).
- The 25 tool tests and `test_mission_status_examples.py`, `test_mission_status_contract_1_1.py`, `tests/contract/fixtures/mission_status_pre_slice/` (D-6). Check `tests/contract/_loader.py` still has callers (it does: the oracle helpers) — keep it.
- `grep -rn "test_events_import_frozen\|mission_status_gate_checks\|test_mission_status_api_build\|test_contracts_workflows" .github tests scripts docs/development` and fix every live reference (registry entries, `tests/ci/*` lists).

### T027 — Coupling

- `.github/CODEOWNERS`: `/contracts/` → `/contracts/fixtures/`; drop `/services/mission-status-api/` (`~:13-14`, `~:34-35`).
- `.gitattributes:38`: drop the conformance `-text` line.
- `NOTICE:19-27`: drop the Gradle Wrapper block (its files are gone). The charter's Attribution sentence naming it is WP08's.
- `pyproject.toml`: drop `services/**` from the sdist `exclude` (`~:267-271`); keep `contracts/**` (fixtures remain) and `also_copy` `contracts/`.
- `tests/architectural/test_no_duplicate_suite_execution.py:190`: drop the `contracts-release.yml` allowlist entry (shrink).
- Search for leftovers: `git grep -n "services/mission-status-api\|mission-status-api.yml\|contracts.yml\|contracts-release.yml\|contracts/tools" -- ':!kitty-specs' ':!docs' ':!*.md' ':!CHANGELOG*'` must be empty except intentional history. Docs are WP08's.

## Validation (specific gate files; never the bare tests/architectural/)

```bash
uv run --frozen pytest tests/architectural/test_events_cutover_absent.py tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_shared_package_boundary.py tests/architectural/test_pyproject_shape.py tests/architectural/test_gate_selection_authority.py tests/architectural/test_module_shard_registry.py tests/architectural/test_release_asset_download_owner.py tests/architectural/test_scenario_contract.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_dead_modules.py -q
uv run --frozen pytest tests/cross_cutting/packaging/ tests/ci/ tests/contract/ -q -n 4 --dist loadfile
make test-fast
```

## Definition of Done
- T024 green; packaging guards green; no remaining non-doc reference to removed paths.
