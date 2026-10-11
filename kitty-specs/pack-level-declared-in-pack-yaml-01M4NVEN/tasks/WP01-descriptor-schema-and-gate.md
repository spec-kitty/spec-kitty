---
work_package_id: WP01
title: PackDescriptor schema (pack_level/requires_core/active_charter/pack_drg) + pack_level single-authority gate
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-020
- NFR-002
- NFR-006
- C-001
planning_base_branch: issue-6048-pack-level-pack-yaml
merge_target_branch: issue-6048-pack-level-pack-yaml
branch_strategy: Planning artifacts for this mission were generated on issue-6048-pack-level-pack-yaml. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6048-pack-level-pack-yaml unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pack-level-declared-in-pack-yaml-01M4NVEN
base_commit: 32e32351f4fdc1112498cf38dadb606b3dba2516
created_at: '2026-10-11T16:42:31.990434+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Schema foundation
history:
- at: '2026-10-11T16:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/packs/
create_intent:
- tests/architectural/test_pack_level_single_authority.py
- tests/charter_offering/test_pack_descriptor_level.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/charter/offering/packs/pack_descriptor.py
- tests/charter_offering/test_pack_descriptor_level.py
- tests/architectural/test_pack_level_single_authority.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your profile via the `/spk-charter-profile-load` skill with profile `python-pedro`. Then read, in order: this mission's `kitty-specs/pack-level-declared-in-pack-yaml-01M4NVEN/plan.md` (esp. the "Plan-point-cut adversarial squad — folded refinements" section), `data-model.md`, and `contracts/pack-descriptor.contract.md`. Those carry the authoritative design; this prompt gives the subtask steps.

## Objective

Make `PackDescriptor` (`src/charter/offering/packs/pack_descriptor.py`) carry the new `pack.yaml` fields, and ship a new **empty-allowlist** architectural gate proving every `pack_level` literal derives from `kernel.pack_tiers` (DIRECTIVE_043: non-vacuous in the same mission as the field it protects — LS-3).

This WP is the mission ROOT: WP02/03/04/05 depend on it. **Import `kernel.pack_tiers.PackTier`; never edit `kernel/pack_tiers.py`** (that file belongs to WP06).

## Context

`PackDescriptor` is `ConfigDict(extra="forbid", frozen=True)` — every new field must be a declared field. Today it has `pack_id`, `pack_version` (required), `parent_pack` (optional), `name`. See `data-model.md` for the full target field table and `contracts/pack-descriptor.contract.md` for the schema + error codes.

## Subtasks

### T001 — ATDD anchor (RED first)
Create `tests/charter_offering/test_pack_descriptor_level.py` pinning the user-observable schema behaviour BEFORE implementing:
- `PackDescriptor(pack_level="org", …)` with NO `pack_version` validates.
- omitting `pack_level` is a schema error.
- `pack_level="built-in"` with no `pack_version` is refused (conditional-requiredness).
- an unknown `pack_level` value is refused.
- `requires_core=">=4.0,<5.0"` accepted; an invalid specifier → schema error naming `requires_core`.
- `active_charter`/`pack_drg` accept a string.
Commit this test as the first commit of the lane (RED on `issue-6048-pack-level-pack-yaml`).

### T002 — Add `pack_level` (required, reuse kernel Literal)
Add `pack_level: PackTier` (import `from kernel.pack_tiers import PackTier`). Required field. No new enum (C-001, R-1).

### T003 — Add `requires_core` (optional, validated)
Add `requires_core: str | None = None`; validate as a PEP 440 version specifier (`packaging.specifiers.SpecifierSet`) — invalid → a pydantic validation error that surfaces as `schema_invalid` naming `requires_core`. (The reusable `check_requires_core` predicate itself is WP05; here only the field + format validation.)

### T004 — Add `active_charter`/`pack_drg` + conditional `pack_version`
Add `active_charter: str | None = None` and `pack_drg: str | None = None` (plain pack-relative strings; in-pack path resolution is validated in WP02). Add a `model_validator` making `pack_version` required iff `pack_level == PackTier` built-in token, optional otherwise (FR-005). Do not break the retired-field rejection path.

### T005 — New single-authority gate (FR-020, empty allowlist)
Create `tests/architectural/test_pack_level_single_authority.py` mirroring the PATTERN of `tests/architectural/test_charter_kind_vocabulary_single_authority.py` (AST gate, read the authority's tokens live from `kernel.pack_tiers.PACK_TIERS`, flag any hand-authored display/`Literal` restating the full level set outside `kernel/pack_tiers.py`). Empty `_ALLOWLIST`, a `test_allowlist_is_empty`, a non-vacuity floor, and a self-mutation test that plants a re-spelled `pack_level` literal and asserts it is flagged. **Scope the gate to the pack_level/level vocabulary; do NOT duplicate the tier-token gate (WP06 owns that).**

## Definition of Done
- `tests/charter_offering/test_pack_descriptor_level.py` GREEN on the final commit, RED on base.
- `test_pack_level_single_authority.py` passes with an empty allowlist; its self-mutation test proves non-vacuity.
- `ruff check`, `ruff format --check --force-exclude`, `mypy --strict` clean on changed files (NFR-006).
- No edit to `kernel/pack_tiers.py`.

## Tests to run (targeted)
`.venv/bin/python -m pytest tests/charter_offering/test_pack_descriptor_level.py tests/architectural/test_pack_level_single_authority.py tests/charter/ tests/charter_offering/ -q`

## Reviewer guidance
Verify red→green on the ATDD test; confirm `pack_level` uses the kernel Literal (not a re-spelled literal); confirm the new gate is non-vacuous (self-mutation planted violation is caught) and allowlist empty.

## Branch Strategy
Planning base `issue-6048-pack-level-pack-yaml`; merge target `issue-6048-pack-level-pack-yaml`. The execution worktree is allocated per the computed lane from `lanes.json`.

Implement with: `spec-kitty agent action implement WP01 --agent <name> --mission pack-level-declared-in-pack-yaml-01M4NVEN`
