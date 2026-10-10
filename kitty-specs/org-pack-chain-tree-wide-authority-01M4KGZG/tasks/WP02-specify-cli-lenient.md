---
work_package_id: WP02
title: specify_cli lenient callers
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-006
- NFR-001
planning_base_branch: feat/org-pack-chain-tree-wide-authority
merge_target_branch: feat/org-pack-chain-tree-wide-authority
branch_strategy: Planning artifacts for this mission were generated on feat/org-pack-chain-tree-wide-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/org-pack-chain-tree-wide-authority unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-org-pack-chain-tree-wide-authority-01M4KGZG
base_commit: 67d7af56bd7f9af3d3ae2f7acb2bd67a7a700c29
created_at: '2026-10-10T18:48:35.233898+00:00'
subtasks:
- T005
- T006
- T007
- T008
history:
- created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/skills/catalog.py
- src/specify_cli/invocation/org_profiles.py
- src/specify_cli/cli/commands/profiles_cmd.py
- src/specify_cli/cli/commands/_charter_pack_collect.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load profile `python-pedro` via `/spk-charter-profile-load` before anything else.

## Objective

Migrate the best-effort / diagnostic / read-only specify_cli org-pack chain callers onto `resolve_pack_chain(strict=False)`, posture-preserving, no behaviour change. Exact replacements in `research.md` Decision 2. Import `resolve_pack_chain` directly from `charter.activation.layer_roots`; keep lazy imports lazy.

## Subtasks

### T005 — `skills/catalog.py:154`
`bool(resolve_existing_org_roots(project_root))` → `bool(resolve_pack_chain(project_root, strict=False))`.

### T006 — `invocation/org_profiles.py:67`
`[root for root in resolve_org_roots(repo_root) if root.exists()]` → `resolve_pack_chain(repo_root, strict=False)`. Keep the surrounding `try/except → []`.

### T007 — `cli/commands/profiles_cmd.py:109`
`[root for root in resolve_org_roots(repo_root) if root.exists()]` → `resolve_pack_chain(repo_root, strict=False)`.

### T008 — `cli/commands/_charter_pack_collect.py:258/365/609/1213`
All four `resolve_org_roots(repo_root)` → `resolve_pack_chain(repo_root, strict=False)`.
- **First verify** `CharterOfferingService` treats absent roots as no-ops (it should — they load nothing). If it did anything meaningful with an absent root, `strict=False` would hide an unfetched pack from `doctor` — stop and flag.
- Do **not** touch the separate `registry.packs` name-capturing loops (`_build_pack_entries` ~558, `_retired_layout_findings` ~1257) — those are the name-paired reads that supply per-pack snapshot/health and are NOT census hits.

## Branch Strategy
Planning base + merge target: `feat/org-pack-chain-tree-wide-authority`. Lane worktree from `lanes.json`.

## Definition of Done
- Four modules migrated (4 call sites in `_charter_pack_collect`).
- `CharterOfferingService` absent-root no-op verified (note the verification in the review).
- `doctor charter-packs` output unchanged on a configured project; existing tests for these modules pass.
- `ruff check` + format clean.

## Risks / reviewer guidance
Reviewer: confirm diagnostic completeness is untouched (health comes from the `registry.packs` loops, not the migrated `resolve_org_roots` calls), and the prefilter/short-circuit semantics are preserved.
