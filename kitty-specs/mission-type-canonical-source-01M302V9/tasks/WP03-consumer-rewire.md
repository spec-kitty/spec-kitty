---
work_package_id: WP03
title: Org-aware mission-type loader (#3831 #4088)
dependencies:
- WP02
requirement_refs:
- FR-002
- FR-003
- FR-007
planning_base_branch: fix/mission-type-canonical-source-3831
merge_target_branch: fix/mission-type-canonical-source-3831
subtasks:
- T020
- T021
- T022
- T023
phase: Phase 3 - Org-aware loader
agent_profile: python-pedro
authoritative_surface: src/specify_cli/mission.py
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/mission.py
- tests/specify_cli/test_org_mission_type_resolution.py
- tests/missions/test_mission_schema_unit.py
role: implementer
task_type: implement
---

# Work Package Prompt: WP03 – Org-aware mission-type loader (#3831 #4088)

> **RE-SCOPED 2026-09-21.** Was "consumer rewire onto charter"; the full convergence is the #2652
> epic (charter vs legacy encode different concerns — see spec Re-scope / tracer D10). This WP is now
> the targeted, behavior-safe loader fix.

## Objectives & Success Criteria
Make the mission-type loader org-aware so #3831 and #4088 are fixed with NO change to built-in
behavior (NFR-001). Flips BOTH WP01 repros green (removing their `xfail(strict)` markers). Built-ins
resolve exactly as today.

## Context & Constraints
- `src/specify_cli/runtime/resolver.py::resolve_mission(name, project_dir)` ALREADY resolves a
  `mission.yaml` through override → legacy → org → global → package tiers. The org-blind
  `_mission_path_by_name` (mission.py) does its own 2-tier lookup and ignores it — THAT is the defect.
- Two org-customization shapes:
  - **(a) full `mission.yaml`** shipped at the override or org tier (e.g. the #4088 fixture's
    `.kittify/overrides/missions/software-dev/mission.yaml`) → routing through `resolve_mission` finds it.
  - **(b) sparse registration** via `mission_types/<type>.yaml` only (id/display_name/action_sequence),
    no `mission.yaml` (the #3831 fixture's `org-packs/acme-doctrine/mission_types/docs-audit.yaml`) →
    no `mission.yaml` exists; must build a neutral `Mission` from the org registration.
- Do NOT retire the resolver, do NOT touch built-in consumers, do NOT migrate anything (all #2652).
- Preserve the typeless→software-dev *template* default (`mission.py:783`, C-006/FR-003a).

## Subtasks
### T020 – Route the loader through the org-aware resolver
Make `get_mission_by_name` resolve a `mission.yaml` via
`specify_cli.runtime.resolver.resolve_mission(name, project_dir)` (override → legacy → org → global →
package) instead of `_mission_path_by_name`'s bespoke 2-tier lookup. Fixes #4088 (override tier) and
the org full-`mission.yaml` case. Thread `project_dir` (the `.kittify` parent) through so the resolver
can reach org roots; keep public signatures working (adapt internally).

### T021 – Build a neutral Mission for sparse org types (#3831 case b)
When no `mission.yaml` resolves BUT the type is a registered org mission type (probe
`charter.activation.mission_type_profiles.resolve_mission_type_context(project_dir, mission_type=name)`
/ `MissionTypeRepository`), construct a `Mission`/`MissionConfig` carrying the org type's identity
(`name = display_name`) and **neutral conventions** — empty `paths` (→ path-convention check no-ops,
never software-dev's `src/`/`tests/`), empty/own `artifacts`, a minimal valid `workflow` (derive one
phase from `action_sequence`; `WorkflowConfig.phases` has `min_length=1`). Do NOT fall back to
software-dev for a *registered typed* type.

### T022 – Preserve typeless default; surface typed-unknown
`get_mission_for_feature`: typeless (`meta.json` has no mission_type) → software-dev *template*
default, no warning (unchanged, C-006/FR-003a). A *typed* value resolving to neither a `mission.yaml`
nor a registered org type → surface a visible error (raise a clear `MissionNotFoundError` the CLI
reports), NOT a warn-and-substitute to software-dev.

### T023 – Flip the repros green
In `tests/specify_cli/test_org_mission_type_resolution.py`: remove the `xfail(strict=True)` markers on
both repros and rewrite their bodies to the post-fix expectation (org custom type resolves to
`Docs Audit Kitty` with neutral conventions; the override is honoured). They must now PASS.

## Test Strategy (narrow — NEVER whole-dir pytest / make test-* / -n auto; they hang/crash you)
- `.venv/bin/python -m pytest tests/specify_cli/test_org_mission_type_resolution.py -q` → both PASS.
- Add focused tests: typed-unknown → raises/visible error; typeless → software-dev template, no warning.
- Built-in parity spot-check: `.venv/bin/python -m pytest tests/missions/test_mission_schema_unit.py -q`
  still green (built-ins unchanged).
- mypy on mission.py; ruff clean.

## Review Guidance
Confirm: built-in resolution unchanged; #3831/#4088 repros green (markers removed); typeless default
preserved; typed-unknown surfaces; no `charter → specify_cli` import; complexity ≤15.

## Activity Log
- 2026-09-21T00:00:00Z – system – Prompt re-scoped to org-aware loader.
