---
work_package_id: WP01
title: Runtime-tier lenient hot-path migration
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
base_commit: 4570616fd9ae88a8b2a93f19f8a566ff3e4c7f67
created_at: '2026-10-10T18:45:04.371343+00:00'
subtasks:
- T001
- T002
- T003
- T004
history:
- created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- src/runtime/next/runtime_bridge_io.py
- src/runtime/next/_internal_runtime/discovery.py
- src/specify_cli/runtime/resolver.py
- src/specify_cli/mission_loader/command.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile via the `/spk-charter-profile-load` skill with profile `python-pedro`. Adopt its identity, boundaries, and discipline for this work package.

## Objective

Route the runtime/next org-pack chain **hot paths** onto the single authority `resolve_pack_chain()` (`src/charter/activation/layer_roots.py`), posture-preserving (`strict=False`). Pure single-authority consistency — **no behaviour change**. Exact replacements are in `kitty-specs/org-pack-chain-tree-wide-authority-01M4KGZG/research.md` (Decision 2).

## Context

`resolve_pack_chain(repo_root, *, strict=False)` is byte-identical to `resolve_existing_org_roots` and (for the raw `resolve_org_roots` sites) adds an existence filter that is harmless in template search. Import it **directly** from `charter.activation.layer_roots` (matches all existing importers; DEC-6012-2). Keep the lazy (in-function) imports lazy.

## Subtasks

### T001 — `runtime_bridge_io.py:465`
- Replace `org_roots=list(resolve_org_roots(repo_root, quiet=True))` with `org_roots=resolve_pack_chain(repo_root, strict=False)`.
- Update the lazy import and the DEC-004/005 comment block (lines ~442–456) that still names `resolve_org_roots`/the facade rationale.

### T002 — `runtime/resolver.py:356` and `:818`
- Both `for org_root in resolve_org_roots(project_dir, quiet=True)` loops → `for org_root in resolve_pack_chain(project_dir, strict=False)`. Update the DEC comment blocks (~342–353, ~813–816).

### T003 — `mission_loader/command.py:235`
- `org_roots=list(resolve_org_roots(repo_root, quiet=True))` → `resolve_pack_chain(repo_root, strict=False)`. Update the DEC comment (~218–220). **Do NOT touch `:275` (`resolve_org_dirs`) — out of scope.**

### T004 — `_internal_runtime/discovery.py:82`
- Docstring only (not a caller): refresh the `DiscoveryContext.org_roots` docstring to say roots are populated by callers via `resolve_pack_chain`. No code change.

## Branch Strategy
Planning base: `feat/org-pack-chain-tree-wide-authority`; final merge target: same (the mission branch, which PRs to upstream `main`). Your execution worktree is the lane allocated from `lanes.json` — do not pick a base branch manually.

## Definition of Done
- All four source edits made; `resolve_org_dirs` sites untouched.
- `resolve_pack_chain` imported directly from `charter.activation.layer_roots`, imports stay lazy.
- Existing runtime tests pass unchanged (`tests/runtime/`, `tests/next/`, `tests/specify_cli/mission_loader/`, `tests/specify_cli/runtime/` — run the files covering the touched modules, not whole dirs).
- `ruff check` + `ruff format --check` clean on touched files.

## Risks / reviewer guidance
No behaviour change expected. Reviewer: confirm chain ordering unchanged and that the raw→`strict=False` existence filter is harmless at each site (template/root search no-ops on absent roots). Confirm no `resolve_org_dirs` call was migrated.
