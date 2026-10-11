---
work_package_id: WP05
title: Vendoring tooling — regenerate-graph --pack-root, requires_core checker, clean-tree level-aware digest
dependencies:
- WP01
requirement_refs:
- FR-013
- FR-014
- FR-015
- NFR-003
- NFR-004
- NFR-006
planning_base_branch: issue-6048-pack-level-pack-yaml
merge_target_branch: issue-6048-pack-level-pack-yaml
branch_strategy: Planning artifacts for this mission were generated on issue-6048-pack-level-pack-yaml. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6048-pack-level-pack-yaml unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pack-level-declared-in-pack-yaml-01M4NVEN
base_commit: e5208637df3b87bb7fa82c15244c7ef3bdffe0ad
created_at: '2026-10-11T17:27:59.445598+00:00'
subtasks:
- T022
- T023
- T024
- T025
- T026
- T027
phase: Phase 2 - Tooling
history:
- at: '2026-10-11T16:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/packs/
create_intent:
- src/charter/offering/packs/pack_clean_digest.py
- src/charter/offering/packs/core_compat.py
- tests/charter_offering/test_pack_clean_digest.py
- tests/charter_offering/test_requires_core_check.py
- tests/specify_cli/cli/commands/charter/test_regenerate_graph_pack_root.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/cli/commands/charter/pack_tooling.py
- src/charter/offering/packs/pack_clean_digest.py
- src/charter/offering/packs/core_compat.py
- tests/charter_offering/test_pack_clean_digest.py
- tests/charter_offering/test_requires_core_check.py
- tests/specify_cli/cli/commands/charter/test_regenerate_graph_pack_root.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` via `/spk-charter-profile-load`. Read `plan.md` (IC-06 + architect item C — level-aware digest), `contracts/pack-descriptor.contract.md` (digest + requires_core + `--pack-root` contracts). Depends on WP01 (the `requires_core` field). **Do NOT edit `snapshot_sha256` or its callers (NFR-004).** The digest and checker are NEW modules to avoid touching `builtin_manifest.py`/`pack_manifest.py`.

## Objective

Deliver the three #6046 vendoring prerequisites: `regenerate-graph --pack-root`, a reusable `requires_core` compatibility check, and a clean-tree drift digest reproducible across git-archive export / worktree / installed copy.

## Subtasks

### T022 — ATDD anchor (RED first)
`tests/specify_cli/cli/commands/charter/test_regenerate_graph_pack_root.py`: `regenerate-graph --pack-root <tmp built-in copy>` writes that root's shards + `pack-manifest.yaml`; `--check --pack-root <dir>` reports freshness for that dir; default (no flag) is byte-unchanged. Commit RED first.

### T023 — `--pack-root` on regenerate-graph (FR-013)
In `pack_tooling.py`, add `--pack-root <dir>` (default = `_built_in_pack_root()`). Thread it through BOTH the write path and `--check` (`generate_builtin_manifest`/`builtin_manifest_is_fresh` already take a `pack_root`). The no-flag default must stay byte-identical to today.

### T024 — clean-tree level-aware digest (FR-015) — ATDD first
`tests/charter_offering/test_pack_clean_digest.py`: a pack tree with `assets/__pycache__/` present yields the SAME digest as its `git archive` export; an org pack (internal shape: `org-charter.yaml` + `drg/fragment.yaml`, NOT sharded) is covered, not just built-in. Then implement `pack_clean_digest.py`: enumerate a declared, LEVEL-AWARE file set — `RECOGNISED_ARTIFACT_DIRS` + the level's layout files resolved via the `kernel.charter_pack_paths` conventions (the same constants the WP02 seam delegates to — `DRG_FRAGMENT`/`ORG_CHARTER_FILENAME`/`PROJECT_GRAPH_FILENAME` + per-level layout) + `pack.yaml` — LF-normalize via the existing `_lf_normalized` helper. Enumerating from `kernel.charter_pack_paths` (not WP02's new `resolve_pack_layout`) keeps this WP independent of WP02. Do NOT use `has_built_in_content_dir` (built-in-only) and do NOT use rglob.

### T025 — assert snapshot_sha256 untouched (NFR-004)
Add/keep a test asserting `snapshot_sha256` and its two callers (`write_pack_manifest`, `_snapshot_manifest_is_intact`) produce byte-identical output to before. Do not edit those functions.

### T026 — `requires_core` checker (FR-014) — ATDD first
`tests/charter_offering/test_requires_core_check.py`: a satisfied range passes, an unsatisfied range fails, absent `requires_core` passes (no constraint). Implement `core_compat.check_requires_core(descriptor, core_version) -> bool` using `packaging.specifiers.SpecifierSet`. Pure predicate, callable by #3504 tooling.

### T027 — wire + docs-help
Ensure the new CLI option has clear help text; ensure the digest/checker are importable from a stable location for downstream (#3504) use.

## Definition of Done
- All three ATDD anchors GREEN (RED on base).
- Digest identical across export/worktree/installed and level-aware (NFR-003); `snapshot_sha256` byte-unchanged (NFR-004).
- `--pack-root` default byte-unchanged; CLI < 2s.
- ruff/format/mypy clean (NFR-006).

## Tests to run (targeted)
`.venv/bin/python -m pytest tests/charter_offering/test_pack_clean_digest.py tests/charter_offering/test_requires_core_check.py tests/specify_cli/cli/commands/charter/test_regenerate_graph_pack_root.py tests/charter_offering/ -q`

## Reviewer guidance
Verify the digest is level-aware (org/project covered, not just built-in) and determinism holds across export vs __pycache__-polluted worktree; verify `snapshot_sha256` is untouched; verify `--pack-root` default path unchanged. The digest enumerates from `kernel.charter_pack_paths` conventions, so this WP is independent of WP02.

## Branch Strategy
Planning/merge base `issue-6048-pack-level-pack-yaml`; worktree per `lanes.json`.
Implement with: `spec-kitty agent action implement WP05 --agent <name> --mission pack-level-declared-in-pack-yaml-01M4NVEN`
