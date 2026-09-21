---
work_package_id: WP04
title: Retire the legacy resolver + display rewire + FR-010 gate
dependencies:
- WP02
- WP03
requirement_refs:
- FR-001
- FR-003
- FR-006
- FR-007
- NFR-003
planning_base_branch: fix/mission-type-canonical-source-3831
merge_target_branch: fix/mission-type-canonical-source-3831
branch_strategy: Planning artifacts for this mission were generated on fix/mission-type-canonical-source-3831. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/mission-type-canonical-source-3831 unless the human explicitly redirects the landing branch.
subtasks:
- T030
- T031
- T032
- T033
phase: Phase 4 - Loader convergence
history:
- at: '2026-09-20T19:20:00Z'
  actor: system
  action: Prompt generated for mission-type-canonical-source
agent_profile: python-pedro
authoritative_surface: src/specify_cli/mission.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/mission.py
- src/specify_cli/config/path_conventions.py
- src/specify_cli/dashboard/handlers/features.py
- src/specify_cli/cli/commands/mission_type.py
- tests/architectural/test_mission_type_reader_invariants.py
- tests/architectural/mission_type_reader_allowlist.yaml
- tests/git_ops/test_worktree.py
- tests/test_dashboard/test_api_handler.py
- tests/cross_cutting/misc/test_acceptance_support.py
- tests/specify_cli/cli/commands/test_selector_resolution.py
- tests/charter/test_pack_manager.py
- tests/characterization/test_trio_pure_cores.py
- tests/charter/test_pack_context.py
- tests/missions/test_mission_schema_unit.py
- tests/specify_cli/acceptance/test_accept_candidate_source_tree_4254.py
- tests/specify_cli/acceptance/test_accept_contracts_path_repro.py
- tests/specify_cli/acceptance/test_path_conventions_all_types.py
- tests/specify_cli/cli/commands/test_mission_type_current_fallback_signal.py
- tests/specify_cli/cli/commands/test_wp03_no_selector_exit2.py
- tests/specify_cli/test_mission_type_read_converters.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Retire the legacy resolver + display rewire + FR-010 gate

## ⚡ Do This First: Load Agent Profile
Load `python-pedro` via `/ad-hoc-profile-load`.

## Objectives & Success Criteria
Strangle the org-blind loader; route mission loading through the charter source. WP01 T003 (#3831) flips GREEN. Everything green at this single commit (per-commit greenness).

## Context & Constraints
- Depends on WP02 + WP03 (canonical schema + rewired consumers already off the legacy `Mission`).
- **Preserve** the typeless→software-dev *template* default (`mission.py:783`, C-006/FR-003a) — removing it is #2660, NOT here (C-001). A typed-but-unknown type must surface visibly (never warn-and-substitute). Keep `get_mission_type` (already charter-clean).

## Subtasks & Detailed Guidance
### Subtask T030 – Retire the resolver
- Remove `_mission_path_by_name`, `get_mission_by_name`, `get_mission_for_feature` (fallback `:801-806`), `discover_missions`, `list_available_missions`, `_packaged_missions_dir`; route loading through charter. Remove the `specify_cli/mission.py` `VALID_PATH_KEYS` copy and repoint `config/path_conventions.py` to the charter home (finishing WP02's relocation).
### Subtask T031 – Display consumers
- Rewire `dashboard/handlers/features.py:109-112` (retire domain/version) and `cli/commands/mission_type.py` panel; **REMOVE the partial-#3831 `catch_warnings` band-aid at `:195-215`** — do not stack on the new source.
### Subtask T032 – Test-import sweep (all 14, same commit)
- Rewrite/delete **every** test file importing a retired symbol, enumerated (per-commit greenness — binding): `tests/git_ops/test_worktree.py`, `tests/test_dashboard/test_api_handler.py`, `tests/cross_cutting/misc/test_acceptance_support.py`, `tests/specify_cli/cli/commands/test_selector_resolution.py`, `tests/charter/test_pack_manager.py`, `tests/characterization/test_trio_pure_cores.py`, `tests/charter/test_pack_context.py`, `tests/missions/test_mission_schema_unit.py`, `tests/specify_cli/acceptance/test_accept_candidate_source_tree_4254.py`, `tests/specify_cli/acceptance/test_accept_contracts_path_repro.py`, `tests/specify_cli/acceptance/test_path_conventions_all_types.py`, `tests/specify_cli/cli/commands/test_mission_type_current_fallback_signal.py` (the #3836 band-aid test — delete/replace with the charter-source assertion), `tests/specify_cli/cli/commands/test_wp03_no_selector_exit2.py`, `tests/specify_cli/test_mission_type_read_converters.py`. Afterward `git grep -nE 'get_mission_for_feature|get_mission_by_name|list_available_missions|_mission_path_by_name|_packaged_missions_dir'` must show zero live call sites (src or tests).
### Subtask T033 – FR-010 gate fold
- In the same commit, **remove** the now-stale `src/specify_cli/mission.py` exemption entries from `tests/architectural/mission_type_reader_allowlist.yaml` (the retired lines are *deleted* — a line-number exemption is incorrect, not renumbered) and update `tests/architectural/test_mission_type_reader_invariants.py`. Assert the gate passes with **zero** mission.py exemptions.

## Test Strategy
- Run each owned test file individually + the FR-010 gate + WP01 T003 (now GREEN). `git grep` retired symbols = 0 live call sites.
- **SC-003 / FR-007 focused tests (new, T030-owned)**: (a) a *typed-but-unknown* mission type → non-zero exit / structured JSON error (visible, not warn-and-substitute); (b) a *typeless* feature → loads the software-dev template under `pytest.warns(None)` (zero warnings). Both are the behavior change this WP introduces and must be directly asserted (Sonar new-code gate).

## Risks & Mitigations
- Intermediate red from a missed consumer → `git grep` sweep before commit; WP03 already rewired the artifact/path consumers.

## Review Guidance
- Confirm typeless→software-dev template default preserved; typed-unknown surfaced; no `warnings.warn` substitute path survives; FR-010 allowlist updated, not bypassed.

## Activity Log
- 2026-09-20T19:20:00Z – system – Prompt created.
