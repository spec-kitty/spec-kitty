---
work_package_id: WP02
title: Red-first consumer-census routing gate
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-006
- FR-007
- NFR-001
- SC-001
- SC-002
planning_base_branch: issue-6173-derived-consumer-census
merge_target_branch: issue-6173-derived-consumer-census
branch_strategy: Planning artifacts for this mission were generated on issue-6173-derived-consumer-census. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6173-derived-consumer-census unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
phase: Phase 2 - Gate
history:
- timestamp: '2026-10-13T17:50:39Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: tests/architectural/test_consumer_census_routing.py
create_intent:
- tests/architectural/test_consumer_census_routing.py
execution_mode: code_change
owned_files:
- tests/architectural/test_consumer_census_routing.py
role: implementer
tags: []
tracker_refs: []
---

# WP02 — Red-first consumer-census routing gate

`tests/architectural/test_consumer_census_routing.py`: for each census
`(module, path)`, assert `select_modules([path]) ⊇ {module}`; red naming the
module + unrouted path. Non-vacuity: a planted unrouted consumer reds the
checker (FR-006); the three historical pins (prompt.md→next, lifecycle.py→agent,
expected-artifacts.yaml→dossier) red against a router with their globs stripped
(FR-007, red-first). Reads the committed artifact (static, battery-fast). Must
not loosen `test_group_module_fanout_is_wired` or the transcription lockstep
(NFR-001).

ATDD: the planted-consumer + glob-stripped pins ARE the red-first proof.
Validation: `.venv/bin/python -m pytest tests/architectural/test_consumer_census_routing.py -q`.
