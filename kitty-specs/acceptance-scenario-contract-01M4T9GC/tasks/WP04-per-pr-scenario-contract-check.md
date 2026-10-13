---
work_package_id: WP04
title: Per-PR scenario contract check
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-002
- NFR-003
- SC-001
planning_base_branch: ccr-002603b2-bip646
merge_target_branch: ccr-002603b2-bip646
branch_strategy: Planning artifacts for this mission were generated on ccr-002603b2-bip646. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into ccr-002603b2-bip646 unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
- T014
- T015
- T016
history: []
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- scripts/ci/scenario_contract.py
- tests/architectural/test_scenario_contract.py
- tests/ci/test_scenario_contract_reader.py
execution_mode: code_change
model: ''
owned_files:
- scripts/ci/scenario_contract.py
- tests/architectural/test_scenario_contract.py
- tests/architectural/fixtures/scenarios/**
- tests/ci/test_scenario_contract_reader.py
- .github/ci-module-registry.yml
role: implementer
tags: []
tracker_refs: []
---

# WP04: Per-PR scenario contract check

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Implementation command: `spec-kitty agent action implement WP04 --agent claude --mission acceptance-scenario-contract-01M4T9GC`

---

## Objective

A JDK-free per-PR check that every `.feature` file parses, every tag follows the vocabulary, and every step of a non-`@wip` scenario matches exactly one step definition.

## Context

Plan IC-04, data-model.md. Routing: add one row to `special_tiers.architectural.fast_gate.roster` in `.github/ci-module-registry.yml` (the `architectural-fast` job runs on every PR); do not touch `ci-router.yml` or `_DELIBERATELY_UNGATED_FILTER_GROUPS`. Depends on WP01's vocabulary text.

### Subtask T012: Broken fixtures first

- **Steps**: `tests/architectural/fixtures/scenarios/` with a tiny `steps/FixtureSteps.java` and one `.feature` per rule: unparseable line, scenario with no steps, bad promise id, repeated promise tag, `@wip` missing owner, bad `@wip-since` date, bad `@defect`, unknown prefixed tag, unbound gating step, ambiguous step, unsupported parameter type (in a separate steps dir), plus a valid `@wip` with an unbound step. Fixture files must not live under `tests/scenarios/` (the runner would pick them up).

### Subtask T013: Gherkin subset reader

- **Steps**: `scripts/ci/scenario_contract.py`: dataclasses `Step`, `Scenario`, `Problem`; parse Feature/Rule/Background/Scenario/Scenario Outline/Examples, tag lines, comments, doc strings (`"""`/```), data tables; tag inheritance; `And/But/*` keep the previous keyword; outline expansion per Examples row; Background steps prepended.

### Subtask T014: Tag rules and step matcher

- **Steps**: tag validation per data-model.md; extract `@(Given|When|Then)\("((?:[^"\\]|\\.)*)"\)` from Java sources, decode Java escapes; translate `{string}`, `{int}`, `{word}`; reject other `{...}`, `(`...`)` optional text and `/` alternation with a clear error; escape everything else; full-match.

### Subtask T015: Tests

- **Steps**: `tests/ci/test_scenario_contract_reader.py` unit-tests the reader, tags and matcher directly (each branch). `tests/architectural/test_scenario_contract.py`: the real tree is non-empty and clean against the real step definitions; each broken fixture produces its expected problem code; the `@wip` fixture produces only information.

### Subtask T016: Roster row

- **Steps**: add `{path: tests/architectural/test_scenario_contract.py, budget_seconds: 10, reason: ...}`; run `tests/ci/test_battery_roster_budgets.py`, `tests/ci/test_battery_partition_plugin.py`, `tests/architectural/test_battery_partition_proof.py`, `tests/architectural/test_module_shard_registry.py`, `tests/ci/test_ci_module_wiring.py` and fix any seed/timing entry they require.

## Definition of Done

- T012 to T016 done; check runs under 5 s; new Python passes `ruff`, format and `mypy`; diff coverage ≥ 90%.

## Risks

- Over-strict parsing of valid Gherkin: run against the real tree and the Cucumber docs' common shapes.

## Reviewer Guidance

- The step vocabulary must be read from Java source, never duplicated in Python.
