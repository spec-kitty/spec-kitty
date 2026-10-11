---
work_package_id: WP05
title: Widen the FR-006 census gate tree-wide
dependencies:
- WP01
- WP02
- WP03
- WP04
requirement_refs:
- FR-003
- FR-004
planning_base_branch: feat/org-pack-chain-tree-wide-authority
merge_target_branch: feat/org-pack-chain-tree-wide-authority
branch_strategy: Planning artifacts for this mission were generated on feat/org-pack-chain-tree-wide-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/org-pack-chain-tree-wide-authority unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-org-pack-chain-tree-wide-authority-01M4KGZG
base_commit: 75231ae3085a1ed0bff372ea5a9561c84d2892e6
created_at: '2026-10-10T19:21:00.768165+00:00'
subtasks:
- T016
- T017
- T018
history:
- created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- tests/architectural/test_org_pack_chain_single_authority.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load profile `python-pedro` via `/spk-charter-profile-load` before anything else.

## Objective

Widen the FR-006 single-authority census from its charter-surface path scope to all of `src/`, keeping the allowlist empty, with the two legitimate exemptions expressed as **scan rules** (not allowlist entries). **This WP must land AFTER WP01–WP04** — widening before the callers migrate turns the gate red.

## Context (from research.md Decision 5)
- `_SCOPE_DIRS` today = `src/charter/activation` + `src/specify_cli/cli/commands/charter`. `_scope_files()` already `rglob`s.
- Forbidden primitives: `{resolve_org_roots, resolve_existing_org_roots, require_declared_org_roots, resolve_org_root_chain}`. `_ALLOWED = frozenset()` and is asserted-empty (`test_allowlist_is_empty`). `_OWNER = layer_roots.py` is skipped.
- Name-paired enumeration (`_enumerate_org_pack_paths[_strict]`, `pack_context._read_org_packs`) is already a non-violation by rule semantics (reads `load_pack_registry()`, returns name-paired tuples / captures `pack.name`) — **no code needed** for exemption (b).

## Subtasks

### T016 — widen scope + offering exclusion rule
- `_SCOPE_DIRS = (_REPO_ROOT / "src",)`.
- Add a documented **scan-exclusion rule** skipping any file under `src/charter/offering/**` (that tier defines + cross-calls the primitives and cannot import the activation authority). Express it in `_scope_files()`/`census()` as a path filter (e.g. skip files with consecutive `("charter","offering")` parts), documented like the existing `_OWNER` skip. **Not** an `_ALLOWED` entry (C-003 / ADR 2026-09-30-1).

### T017 — raise floor + docstring
- Raise `_SCANNED_FILE_FLOOR` from 100 to comfortably below the new tree-wide scanned count (compute the real count, set the floor with margin); update the stale "modules in scope" comment.
- Extend the module docstring: the two name-paired tree-wide readers rely on the existing Rule-1/Rule-2 semantics (name-paired reads are non-violations); the offering tier is a scan-exclusion rule.

### T018 — prove it
- Run the gate: green tree-wide with `_ALLOWED` empty (requires WP01–04 merged into the lane base).
- Confirm the positive control still bites: a reintroduced direct `resolve_existing_org_roots` call on a non-exempt surface trips the gate naming the file (the existing owner-bypass control test covers the mechanism; add/confirm a focused assertion if needed).

## Branch Strategy
Planning base + merge target: `feat/org-pack-chain-tree-wide-authority`. Lane worktree from `lanes.json`. Because this WP `depends_on` WP01–WP04, its lane base includes their approved work.

## Definition of Done
- `_SCOPE_DIRS` = `src/`; offering exclusion is a documented rule; `_ALLOWED` still empty (`test_allowlist_is_empty` passes); floor raised; docstring extended.
- `pytest tests/architectural/test_org_pack_chain_single_authority.py` green.
- `ruff check` + format clean.

## Risks / reviewer guidance
Reviewer: confirm the allowlist is still empty, the offering exemption is a scan rule (not an entry), the file floor tracks the real scanned count, and the gate goes red if any caller were unmigrated (dependency on WP01–04 is real).
