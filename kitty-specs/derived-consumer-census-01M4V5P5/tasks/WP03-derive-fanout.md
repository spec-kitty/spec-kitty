---
work_package_id: WP03
title: Derive GROUP_MODULE_FANOUT from the census
dependencies:
- WP01
- WP02
requirement_refs:
- FR-008
- NFR-001
- SC-003
planning_base_branch: issue-6173-derived-consumer-census
merge_target_branch: issue-6173-derived-consumer-census
branch_strategy: Planning artifacts for this mission were generated on issue-6173-derived-consumer-census. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6173-derived-consumer-census unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
phase: Phase 3 - Derivation
history:
- timestamp: '2026-10-13T17:50:39Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: tests/ci/test_fanout_derivation.py
create_intent:
- tests/ci/test_fanout_derivation.py
execution_mode: code_change
owned_files:
- tests/ci/test_fanout_derivation.py
role: implementer
tags: []
tracker_refs: []
---

# WP03 — Derive GROUP_MODULE_FANOUT from the census

Replace the hardcoded `GROUP_MODULE_FANOUT` dict in `scripts/ci/gate_selection.py`
with a census-derived loader: for each non-src router group, union the modules
the census shows consuming a path matching that group's router globs (excluding
base-selected). The existing `test_group_module_fanout_is_wired` pins stay green
as a cross-check (NFR-001). Add no scrub/registry row (C-003); leave router globs
untouched (C-004).

ATDD: T009 (derived == pinned sets) red-first against the hardcoded dict removal.
Validation: `.venv/bin/python -m pytest tests/architectural/test_gate_selection_authority.py tests/architectural/test_ci_router_transcription_guards.py tests/architectural/test_workflow_coherence.py tests/architectural/test_module_shard_registry.py tests/ci -q`.
