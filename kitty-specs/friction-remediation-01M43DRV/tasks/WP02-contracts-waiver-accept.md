---
work_package_id: WP02
title: meta.json contracts waiver honoured by strict accept
dependencies: []
requirement_refs:
- FR-004
- FR-005
- FR-006
- FR-007
- C-001
- C-002
- NFR-001
- NFR-002
planning_base_branch: issue-5552-friction-remediation
merge_target_branch: issue-5552-friction-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-5552-friction-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5552-friction-remediation unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Implementation
history:
- at: '2026-10-04T12:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/acceptance/
create_intent:
- tests/core/test_contracts_waiver_reader.py
- tests/specify_cli/acceptance/test_accept_contracts_waiver.py
- docs/adr/4.x/2026-10-04-1-mission-contracts-waiver-in-meta-json.md
execution_mode: code_change
owned_files:
- src/specify_cli/acceptance/summary_core.py
- src/specify_cli/core/paths.py
- src/specify_cli/validators/paths.py
- src/specify_cli/mission_metadata.py
- tests/core/test_contracts_waiver_reader.py
- tests/specify_cli/acceptance/test_accept_contracts_waiver.py
- docs/adr/4.x/2026-10-04-1-mission-contracts-waiver-in-meta-json.md
- docs/adr/4.x/index.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5298'
---
# Work Package Prompt: WP02 – meta.json contracts waiver honoured by strict accept

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (`/ad-hoc-profile-load python-pedro`) and follow it.

Mission: `friction-remediation-01M43DRV`. Read `../spec.md`, `../plan.md` and `../research/code-grounding.md` §2 first.

## Objective

Implement the operator ruling (2026-09-28 and 2026-10-04):
- `meta.json` `"contracts": "none"` plus a non-empty string `contracts_rationale` waives the software-dev `paths.deliverables: contracts/` convention in strict `accept`.
- One fail-closed reader in `core/paths.py`, modelled on `read_retention_from_meta`.
- No spec-frontmatter or plan-frontmatter source.

## Subtasks

- **T006 (RED, separate commit)**:
  - Reader unit tests (`tests/core/test_contracts_waiver_reader.py`) for absent, well formed, unknown value, non-string value, missing rationale, blank rationale and corrupt meta (raises `MissionMetaReadError`).
  - Strict-accept tests (`tests/specify_cli/acceptance/test_accept_contracts_waiver.py`) through `collect_feature_summary` and `evaluate_path_conventions`, reusing the `test_accept_contracts_dedup.py` fixture shape.
  - Commit red.
- **T007**: `read_contracts_waiver_from_meta(primary_meta_dir) -> ContractsWaiver`, a frozen dataclass with `waived: bool`, `rationale: str | None` and `warning: str | None`.
- **T008**:
  - `validate_mission_paths(..., waived_artifact_tokens: frozenset[str] = frozenset())` skips a declared ARTIFACT-tagged path whose normalized token is waived. It is never a build path.
  - `evaluate_path_conventions` reads the waiver from `planning_read_dir`, passes `{"contracts"}` when waived, and surfaces the waiver note or malformed warning in the warning slot.
  - Keep complexity ≤ 15 by extracting a helper.
- **T009**:
  - Add `MissionMetaOptional` fields `contracts: str` and `contracts_rationale: str`.
  - Write the ADR `docs/adr/4.x/2026-10-04-1-mission-contracts-waiver-in-meta-json.md` and add an index row if `docs/adr/4.x/index.md` lists ADRs.
- **T010**: Run the targeted suites and gates:
  - `tests/specify_cli/acceptance`;
  - `tests/agent/test_validators_unit.py`;
  - `tests/architectural/test_lifted_root_validate_mission_paths_single_caller.py`;
  - `tests/specify_cli/test_validate_mission_paths_single_caller.py`;
  - the load-meta census and dead-symbol gate files.

## Definition of Done

- A waived no-contracts Mission passes strict accept on path conventions.
- An unwaived or malformed one still blocks.
- A corrupt meta raises.
- The dedup tests stay green.
- The ADR is written.
