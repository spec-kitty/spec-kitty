---
work_package_id: WP02
title: Level load-refusals (MISMATCH/MISSING), validate branch-on-level, and the pack-layout resolution seam
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-007
- FR-008
- FR-009
- NFR-005
- NFR-006
planning_base_branch: issue-6048-pack-level-pack-yaml
merge_target_branch: issue-6048-pack-level-pack-yaml
branch_strategy: Planning artifacts for this mission were generated on issue-6048-pack-level-pack-yaml. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6048-pack-level-pack-yaml unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pack-level-declared-in-pack-yaml-01M4NVEN
base_commit: dd99aecd4b902c70a5f4a84adfaac45fb185a6b5
created_at: '2026-10-11T17:17:49.474427+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
- T011
- T012
phase: Phase 2 - Load & validate
history:
- at: '2026-10-11T16:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/packs/
create_intent:
- src/charter/offering/packs/pack_layout.py
- tests/charter_offering/test_pack_layout.py
- tests/charter_offering/test_pack_level_load_refusals.py
- tests/charter_offering/test_org_pack_level_read.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/charter/offering/packs/pack_validator.py
- src/charter/offering/packs/pack_layout.py
- src/charter/offering/drg/org_pack_loader.py
- src/charter/offering/drg/org_pack_config.py
- tests/charter_offering/test_pack_layout.py
- tests/charter_offering/test_pack_level_load_refusals.py
- tests/charter_offering/test_org_pack_level_read.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` via `/spk-charter-profile-load`. Then read `plan.md` (the squad-refinements section — items A & B are load-bearing for this WP), `data-model.md` (per-level layout table), and `contracts/pack-descriptor.contract.md` (error codes + the resolution seam + the `check_pack_level` design).

## Objective

Refuse a mis-placed pack by name, warn on a missing level, branch `charter pack validate` on the DECLARED level, and introduce the ONE pack-layout resolution seam. Depends on WP01 (the fields must exist).

## Context & binding architect rulings (from plan.md)
- **Seam home (A)**: new `charter/offering/packs/pack_layout.py` (NOT kernel — it takes a `PackDescriptor`). Convention fallback **delegates to existing `kernel.charter_pack_paths`** constants/helpers (`DRG_FRAGMENT`, `ORG_CHARTER_FILENAME`, `PROJECT_GRAPH_FILENAME`, `pack_drg_fragment`, `pack_org_charter`). `drg_path` return = a path `charter/offering/drg/loader.py::load_graph_or_dir` accepts (file OR directory) so built-in's sharded root fits with no separate branch.
- **Configured position (B, real gap)**: `validate_pack(pack_dir)` has NO position context. Add a pure `check_pack_level(descriptor, expected_level: PackTier | None) -> ValidationIssue | None`. Position-aware callers pass `expected_level` (built-in root / each `charter_packs.org.packs[]` entry / `project_pack_root`). On a bare path with no context: **skip the mismatch check (fail-closed — never silently pass a wrong level) but still run MISSING + schema.**

## Subtasks

### T006 — ATDD anchor (RED first)
`tests/charter_offering/test_pack_level_load_refusals.py`: a `pack_level: built-in` pack loaded from an org position → `PACK_LEVEL_MISMATCH` naming file/declared/configured; a matching pack loads; an org pack with no `pack_level` → `PACK_LEVEL_MISSING` WARN (not refuse) naming the file. Commit RED first.

### T007 — `resolve_pack_layout` seam (FR-009)
New `pack_layout.py`: `resolve_pack_layout(pack_root, descriptor) -> (active_charter_path | None, drg_path)`. Descriptor pointer when set (validated inside `pack_root`, reject `..` escape), else per-level convention via `kernel.charter_pack_paths`. Cover with `tests/charter_offering/test_pack_layout.py` (descriptor-set and convention-fallback both resolve; out-of-pack path rejected).

### T008 — Route existing lookups through the seam
Replace the files-present `org-charter.yaml`/`drg/fragment.yaml` lookups in `pack_validator.py` (and callers in `org_pack_loader.py`) with the seam. No behaviour change for packs that omit the pointer fields (convention fallback reproduces today's lookups).

### T009 — `validate` branches on declared level (FR-008)
In `validate_pack`, branch expectations on `descriptor.pack_level` (built-in → sharded `*.graph.yaml` + generated manifest; org → `org-charter.yaml` + `drg/fragment.yaml`; project → `graph.yaml` + overlays) using the seam, instead of files-present inference.

### T010 — `check_pack_level` + MISMATCH wiring (FR-006)
Add the pure predicate; thread `expected_level` from the position-aware load paths. Bare-path validate skips mismatch fail-closed. `PACK_LEVEL_MISMATCH` names file/declared/configured.

### T011 — `PACK_LEVEL_MISSING` warn-then-refuse (FR-007)
Absent `pack_level` → WARN now (name the file to add). Gate the hard refuse behind ONE module-level constant (default = warn) so both paths are testable (C-006). No invented release anchor.

### T012 — Org-path `pack.yaml` read (bounded sub-task)
Teach the org load path (`org_pack_loader.py`/`org_pack_config.py`) to read `pack.yaml` and run the descriptor + level checks. `OrgPackConfig` has ~57 callers — keep the change bounded and add `tests/charter_offering/test_org_pack_level_read.py` as the regression anchor. Do not change unrelated org-load behaviour.

## Definition of Done
- ATDD + layout + org-read tests GREEN (RED on base); existing `tests/charter/`+`tests/charter_offering/` still pass.
- One seam; no second filename authority; bare-path validate never silently passes a wrong level.
- ruff/format/mypy clean (NFR-006); CLI within 2s (NFR-005).

## Tests to run (targeted)
`.venv/bin/python -m pytest tests/charter_offering/test_pack_layout.py tests/charter_offering/test_pack_level_load_refusals.py tests/charter_offering/test_org_pack_level_read.py tests/charter/ tests/charter_offering/ -q`

## Reviewer guidance
Confirm the seam is the sole layout authority; confirm the bare-path fail-closed skip; confirm convention fallback reproduces prior lookups (no silent regression for pointer-less packs); scrutinise the `org_pack_config` blast radius.

## Branch Strategy
Planning/merge base `issue-6048-pack-level-pack-yaml`; worktree per `lanes.json`.
Implement with: `spec-kitty agent action implement WP02 --agent <name> --mission pack-level-declared-in-pack-yaml-01M4NVEN`
