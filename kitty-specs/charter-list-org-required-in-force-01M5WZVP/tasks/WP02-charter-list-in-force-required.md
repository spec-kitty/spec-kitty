---
work_package_id: WP02
title: charter list names in-force required ids; JSON contract v2; acceptance scenario
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-003
- FR-004
- FR-005
- FR-006
- FR-008
- FR-009
- NFR-002
- NFR-004
- C-003
- C-004
planning_base_branch: issue-6417-charter-list-org-required
merge_target_branch: issue-6417-charter-list-org-required
branch_strategy: Planning artifacts for this mission were generated on issue-6417-charter-list-org-required. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6417-charter-list-org-required unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
- T009
phase: Phase 2 - User Story 1 and 2
history:
- at: '2026-10-26T21:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent:
- tests/specify_cli/cli/commands/charter/test_list_required_in_force.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/charter/list_cmd.py
- tests/specify_cli/cli/commands/charter/test_list_required_in_force.py
- tests/specify_cli/cli/commands/charter/test_charter_list_commands.py
- acceptance-jvm/src/test/java/kitty/acceptance/steps/CharterSteps.java
- tests/scenarios/charter/governance-in-force/governance-in-force.feature
- tests/scenarios/charter/PROMISES.md
- docs/api/charter-commands.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – charter list names in-force required ids; JSON contract v2; acceptance scenario

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission charter-list-org-required-in-force-01M5WZVP`). Address all feedback before the work is complete.

---

## Objective

`spec-kitty charter list` names the org-required ids in force on a row whose kind has no allow key
of its own (FR-001), using `charter.activation.api.required_in_force` from WP01 (never a second
computation). `--json` versions its contract (FR-003–FR-005; `contracts/charter-list-json.md`).
The acceptance scenario `PR-CHARTER-GOVERNANCE-002` gates with a fixture whose rule an org layer
really provides (FR-008). The explicit-allow-list FR-023 marker is unchanged (FR-006).

## Context

- Research: `kitty-specs/charter-list-org-required-research-01M5WZQH/research.md` (D2 fixture drift,
  D3 contract, D4 tag convention; `research/repro.sh <dir> old|fixed` reproduces both fixtures).
- `src/specify_cli/cli/commands/charter/list_cmd.py`: `list_cmd` is long; FR-023 helpers
  `_required_not_in_force_by_kind`, `_with_required_not_in_force`, `_REQUIRED_NOT_IN_FORCE`;
  `_KindIdentity.label` gives `stem (declared_id)`.
- `RequiredOmission.describe_packs()` renders `'acme'` (quoted) — reuse the same on
  `RequiredInForce` for the label `"<label> (required by <describe_packs>)"`.
- Import only from `charter.activation.api` (C-001).

## Subtasks

### T005 — Red-first tests and scenario (commit alone, red, before T006)

1. New `tests/specify_cli/cli/commands/charter/test_list_required_in_force.py` (`pytestmark =
   [pytest.mark.fast]`), CliRunner on `charter_app` like `test_list_required_omitted.py`:
   - Built-in floor: org pack `acme` requires `DIRECTIVE_001`, directive key absent → the table's
     flattened output contains `001-architectural-integrity-standard` and `required by 'acme'` and
     still `(All built-ins — no explicit activation)`; `--json` directive row has
     `activated == ["001-architectural-integrity-standard"]`, `allow_list_present is False`; payload
     `schema_version == "2"`.
   - Scenario-shaped fixture (port of `CharterSteps` with the corrected rule at
     `directives/team-rule.directive.yaml`, valid body, `required_directives: [team-rule]`, pack
     `team-pack` at `.kittify/team-pack`, DRG fragment node) → table contains `team-rule`.
   - Negative control on the same fixture with the rule file at the old `directive/` path → the
     directive row does NOT name `team-rule` (an unprovided id is not claimed in force).
   - Every row has `allow_list_present` (bool); a project with explicit `activated_directives`
     has `True` there and its list unchanged; mission-type row `True` when seeded.
   - Positive FR-023 control: explicit list omitting the required id still shows the existing marker
     and no in-force label for that id.
2. Scenario: in `tests/scenarios/charter/governance-in-force/governance-in-force.feature` remove
   `@wip @wip-owner:stijn-dejongh @wip-since:2026-10-18 @defect:6417` from
   `PR-CHARTER-GOVERNANCE-002` (precedent: `tests/scenarios/upgrade/migration-ledger.feature:146`,
   #6416, drops all four), and rewrite the maintainer-notes bullet about it in the past tense: it
   was `@wip @defect:6417` (#6369); `charter list` did not fold org-required ids into an absent-key
   row and the fixture's rule sat in `directive/` with an invalid body; #6417 fixed both.
3. `CharterSteps.java`: the rule file goes to `directives/team-rule.directive.yaml` (constant, used by
   both team-pack steps and the `RULE_NODES` `body_path`), with a valid body from `teamRule(...)`:
   `schema_version: "1.0"`, `id: TEAM_RULE`, `title: Team rule`, `intent: >` + body,
   `enforcement: required`, `scope: docs`. The project-override step writes
   `.kittify/charter-packs/directives/team-rule.directive.yaml` (same drift; that scenario stays
   `@wip` under its own owner). Keep `PROJECT_RULE_MARKER = "team-rule"` (the stem; the listing
   prints `team-rule (TEAM_RULE)`). The JVM suite needs Java 25; if unavailable, say so in the
   history note — the Python test above is the local witness.

### T006 — Table rendering

Extract helpers so `list_cmd` stays ≤ 15 complexity (consider one `_row_cells(...)` or
`_activated_cell(value, in_force, omissions, identity)`), add
`_required_in_force_by_kind(repo_root)` (lenient `strict=False`, keyed by operator token) and
render, for an absent key with ids, the all-built-ins note plus one line per id:
`f"{identity.label(item.artifact_id)} (required by {item.describe_packs()})"`. Hoist repeated
literals (the all-built-ins note appears more than once after this change) to module constants.

### T007 — JSON

- Row: `activated` = sorted ids when the key is absent and ids exist, `None` when absent and none,
  the list otherwise; `allow_list_present = value is not None`.
- Payload: `schema_version: "2"` (string; charter-area convention) as a module constant.
- `required_not_in_force` unchanged.

### T008 — Existing tests and help text

- `test_charter_list_commands.py`: add `allow_list_present` / `schema_version` assertions where rows
  are pinned (`test_json_flag_emits_valid_json` and friends). Do not weaken any assertion.
- Update the `--json` help text and `list_cmd` docstring (OP-CONTRACT-003 paragraph) for the new keys
  and the changed `activated`.
- Run the other consumers and fix only real expectation drift: `tests/specify_cli/cli/commands/charter/test_activate_preset.py`,
  `tests/acceptance/charter_pack_cutover/` (`test_presets.py` has an org pack with `required_tactics`;
  `test_golden_before.py`), `tests/specify_cli/migration/test_legacy_charter_gate.py`,
  `tests/cli/test_mission_agnostic_flag.py`.

### T009 — Docs

- `docs/api/charter-commands.md` §`charter list --json`: describe `schema_version: "2"`,
  `allow_list_present`, the changed `activated`, and the human-table line; bump `updated:`.
  Mention `required_in_force` / `RequiredInForce` in the `charter.activation.api` export list.
- `docs/changelog/CHANGELOG.md` `[Unreleased]`: a Fixed entry (#6417) and a flagged contract
  change line (OP-CONTRACT-003, `schema_version: "2"`), matching the file's style.
- `tests/scenarios/charter/PROMISES.md`: `PR-CHARTER-GOVERNANCE-002` binding → `bound`.

## Test strategy

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/charter/test_list_required_in_force.py tests/specify_cli/cli/commands/charter/test_charter_list_commands.py tests/specify_cli/cli/commands/charter/test_list_required_omitted.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/charter/ -q
uv run --frozen pytest tests/acceptance/charter_pack_cutover/ tests/specify_cli/migration/test_legacy_charter_gate.py tests/cli/test_mission_agnostic_flag.py -q
uv run --frozen pytest tests/architectural/test_scenario_contract.py tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen ruff check src/specify_cli/cli/commands/charter/list_cmd.py tests/specify_cli/cli/commands/charter/
uv run --frozen ruff format --check --force-exclude src/specify_cli/cli/commands/charter/list_cmd.py tests/specify_cli/cli/commands/charter/test_list_required_in_force.py
uv run --frozen mypy src/specify_cli/cli/commands/charter/list_cmd.py
```

## Definition of Done

- T005 committed red (the new Python test fails on WP01's head; the scenario is un-`@wip`'d) before T006.
- All listed tests green; FR-023 tests unchanged and green.
- Docs and changelog updated; contract change flagged.

## Risks

- `list_cmd` complexity (C901 ≤ 15).
- `charter_pack_cutover` golden files may pin `activated: null` for a kind with an org required id.
  Re-pin only with a stated reason (the contract change), never by loosening.

## Reviewer guidance

Check red→green, the negative control (unprovided rule not claimed), FR-023 unchanged, the JSON
contract against `contracts/charter-list-json.md`, and that the scenario tags follow the #6416 precedent.

## Implementation command

```bash
spec-kitty agent action implement WP02 --agent claude --mission charter-list-org-required-in-force-01M5WZVP
```
