---
work_package_id: WP01
title: One read-only stem-resolution batch for the cascade (#6777)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-006
planning_base_branch: issue-6777-cascade-stem-resolution-pass
merge_target_branch: issue-6777-cascade-stem-resolution-pass
branch_strategy: Planning artifacts for this mission were generated on issue-6777-cascade-stem-resolution-pass. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6777-cascade-stem-resolution-pass unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Fix
history: []
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent:
- tests/charter/activation/test_cascade_stem_resolution_6777.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/charter/activate.py
- tests/charter/activation/test_cascade_stem_resolution_6777.py
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 – One read-only stem-resolution batch

## Objective

`_activate_cascade_targets` maps every cascade target's DRG URN to its config-stem ID
with a fresh `ResolutionPass` (121 passes for 114 targets, 5309 artifact-file parses).
Resolve the whole batch through one shared pass, before the first activation write.

## Context

* `src/specify_cli/cli/commands/charter/activate.py` — `_activate_cascade_targets`
  (line ~370) and `_cascade_activation_report` (the pass at ~525 is render-only, #5526).
* `src/charter/activation/kind_vocabulary.py` — `ResolutionPass` contract: memoises layer
  scans and id reads, "must never span a write to the artifact files it reads".
* `src/specify_cli/cli/commands/charter/_cascade_shared.py` — `drg_urn_to_config_id`
  already accepts and threads a pass.

## Definition of Done

* T001 RED-first guard in `tests/charter/activation/test_cascade_stem_resolution_6777.py`
  fails on unmodified `main`, passes after the fix: (a) one shared pass across all
  lookups, (b) every lookup precedes the first `activate()`.
* T002 one batch resolution, then activation.
* T003 no new `specify_cli` import in the charter layer; render-path pass untouched.
* T004 two scripted-writer timings recorded in `traces/approach.md`, both ≤60 s.
