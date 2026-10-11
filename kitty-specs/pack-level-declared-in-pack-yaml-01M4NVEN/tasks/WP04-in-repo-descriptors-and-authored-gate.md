---
work_package_id: WP04
title: In-repo descriptors (built-in += pack_level; new internal pack.yaml) + authored-field gate update + manifest regen
dependencies:
- WP01
requirement_refs:
- FR-011
- FR-012
- FR-018
- C-004
- NFR-006
planning_base_branch: issue-6048-pack-level-pack-yaml
merge_target_branch: issue-6048-pack-level-pack-yaml
branch_strategy: Planning artifacts for this mission were generated on issue-6048-pack-level-pack-yaml. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6048-pack-level-pack-yaml unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pack-level-declared-in-pack-yaml-01M4NVEN
base_commit: f1d74cfdfcc335528d18a2e69a3a1a00039319c5
created_at: '2026-10-11T17:24:36.220290+00:00'
subtasks:
- T017
- T018
- T019
- T020
- T021
phase: Phase 2 - In-repo packs
history:
- at: '2026-10-11T16:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: packs/
create_intent:
- packs/internal/pack.yaml
- tests/charter_offering/test_internal_pack_identity.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- packs/built-in/pack.yaml
- packs/built-in/pack-manifest.yaml
- packs/internal/pack.yaml
- tests/architectural/test_pack_manifest_no_author_edit.py
- tests/charter_offering/test_internal_pack_identity.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` via `/spk-charter-profile-load`. Read `plan.md` (IC-05 + LS-2 + LS-4), `contracts/pack-descriptor.contract.md`, and the CLAUDE.md pack-tier section. Depends on WP01 (the schema must accept the new fields). **LS-2**: the built-in `pack.yaml` field addition and the authored-field gate update MUST land together in this lane.

## Objective

Bring the repo's own packs into compliance: add `pack_level: built-in` to `packs/built-in/pack.yaml`, create `packs/internal/pack.yaml` (org, with pointers + pinned id), update the authored-field gate's expected key set, and regenerate + commit the built-in manifest (LS-4).

## Subtasks

### T017 — ATDD anchor (RED first): authored-field gate expects `pack_level`
In `tests/architectural/test_pack_manifest_no_author_edit.py`, update `_PACK_DESCRIPTOR_FIELDS` and the `set(data) == …` assertion to the new key set `{pack_id, pack_version, parent_pack, name, pack_level}` (FR-018). Write this expectation FIRST (RED: the current built-in `pack.yaml` lacks `pack_level`), then T018 makes it GREEN. Do NOT add `requires_core` to the built-in key set (keep built-in minimal). Keep the leaked-generated-field rejection intact.

### T018 — built-in `pack.yaml` += `pack_level: built-in` (FR-011)
Add `pack_level: built-in` to `packs/built-in/pack.yaml`. Keep it otherwise minimal (no `requires_core`, no pointers — built-in uses its sharded convention). `pack_version` stays present (built-in requires it, FR-005). Do NOT let a fixture conflate this with the generated manifest, which still omits `pack_version`.

### T019 — new `packs/internal/pack.yaml` (FR-012)
Create it: `pack_level: org`; a pinned minted `pack_id` (ULID); `name` (e.g. `spec-kitty-internal` matching its org-charter); `parent_pack: null`; `active_charter: org-charter.yaml`; `pack_drg: drg/fragment.yaml`. `org-charter.yaml` stays the pack's active-charter CONTENT (do not move/rename it). Internal is unsharded and has no `pack-manifest.yaml` — do not add one.

### T020 — internal pack_id drift test (FR-012)
`tests/charter_offering/test_internal_pack_identity.py`: pin internal's `pack_id` to its minted ULID (mirror `test_pack_id_identity` for built-in) so the id is stable, and assert internal loads as an org pack with the declared pointers.

### T021 — Regenerate + commit the built-in manifest (LS-4)
After editing `packs/built-in/`, run `spec-kitty charter pack regenerate-graph` (default root) and commit the regenerated `packs/built-in/pack-manifest.yaml` in this lane. Verify the no-author-edit gate's `test_regenerate_leaves_authored_files_byte_unchanged` is satisfied (the committed manifest is fresh). `packs/internal/` has no manifest — built-in regen only.

## Definition of Done
- built-in loads with `pack_level: built-in`; internal loads as a valid org pack with pinned id + pointers.
- `test_pack_manifest_no_author_edit.py` GREEN with the new key set (RED on base); regenerated manifest committed and fresh.
- `test_packaging_safety` still green — `packs/internal/pack.yaml` must NOT ship in the wheel (C-004); verify the new file does not break the packaging boundary.
- ruff/format/mypy clean (NFR-006).

## Tests to run (targeted)
`.venv/bin/python -m pytest tests/architectural/test_pack_manifest_no_author_edit.py tests/charter_offering/test_internal_pack_identity.py tests/cross_cutting/packaging/test_packaging_safety.py tests/charter_offering/ -q`

## Reviewer guidance
Verify LS-2 atomicity (field + gate together); verify the regenerated manifest is committed and fresh (LS-4); verify internal's id is pinned and `org-charter.yaml` is untouched content; verify packaging boundary intact.

## Branch Strategy
Planning/merge base `issue-6048-pack-level-pack-yaml`; worktree per `lanes.json`.
Implement with: `spec-kitty agent action implement WP04 --agent <name> --mission pack-level-declared-in-pack-yaml-01M4NVEN`
