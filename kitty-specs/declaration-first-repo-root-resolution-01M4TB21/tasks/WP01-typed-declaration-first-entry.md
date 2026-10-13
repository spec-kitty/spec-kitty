---
work_package_id: WP01
title: The typed declaration-first resolution entry
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- SC-001
- SC-003
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-declaration-first-repo-root-resolution-01M4TB21
base_commit: 8ea0b86b94379db5802a09ca77c954763be995c1
created_at: '2026-10-13T10:05:30Z'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - The typed entry (tidy-first enabler)
history:
- at: '2026-10-13T10:05:30Z'
  actor: system
  action: Prompt generated via spec-kitty tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/command_target.py
create_intent:
- src/specify_cli/core/command_target.py
- tests/specify_cli/core/test_command_target.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/core/command_target.py
- tests/specify_cli/core/test_command_target.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '6142'
---

# Work Package Prompt: WP01 – The typed declaration-first resolution entry

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (`spec-kitty agent profile show python-pedro`) and run
`spec-kitty charter context --action implement --json`; apply both before coding.

## Objectives & Success Criteria

Introduce ONE typed, declaration-first producer of a mission-scoped command's
`(repo_root, target_branch)` target, built on the existing public resolvers. This is a
**tidy-first, behaviour-preserving enabler** — it adds a new surface; it does not yet
change any command's behaviour (that is WP03).

Deliver in `src/specify_cli/core/command_target.py`:

- `TargetProvenance(Enum)`: `DECLARATION` (branch read from `meta.json target_branch`) and
  `VALIDATED_FALLBACK` (explicit configured-primary fallback).
- `CommandRepoTarget` — a frozen dataclass: `repo_root: Path`, `target_branch: str`,
  `provenance: TargetProvenance`.
- `resolve_command_repo_target(mission_slug, *, cwd=None, repo_root=None) -> CommandRepoTarget`:
  1. **repo_root**: if `repo_root` is passed → `get_main_repo_root(repo_root)`; else
     `resolve_canonical_root(cwd or Path.cwd())`. The `cwd or Path.cwd()` default is the
     ONE sanctioned ambient read, documented as the single boundary; the result is always
     the canonical primary (worktree→primary collapse), never a raw worktree.
  2. **target_branch**: `read_target_branch_from_meta(repo_root / "kitty-specs" /
     mission_slug)`; present → `DECLARATION`. Absent → `resolve_primary_branch(repo_root,
     bias=False)` → `VALIDATED_FALLBACK`. The entry **never** reads the ambient checked-out
     HEAD as the target (no `bias=True`, no `get_current_branch` as target).
  3. **fail-closed**: a corrupt `meta.json` propagates `MissionMetaReadError`; a cwd with
     no git marker propagates `WorkspaceRootNotFound`. No silent default.
- `__all__` declared. Docstrings name the `primary` / `merge` / `routing` senses
  explicitly (C-004) and state that this is the command-entry declaration-first producer.

## Constraints

- Lives in `specify_cli.core`; imports only down-chain. No package-set / layer-rule change
  (NFR-001).
- Adds NO `get_current_branch(...) or <fallback>` / `coord_branch or current` grammar and
  constructs NO `CommitTarget`/`safe_commit` — so `test_no_write_side_rederivation.py`
  stays green by construction, no allowlist entry (NFR-002).
- ruff + ruff format + mypy clean; cyclomatic complexity ≤ 15; no blanket suppressions
  (NFR-003).

## Validation (targeted test surface)

- `tests/specify_cli/core/test_command_target.py` covering EVERY branch (T003):
  declaration present → `DECLARATION` + declared branch; absent → `VALIDATED_FALLBACK` +
  configured primary; **disagreeing checked-out branch never wins** (assert the ambient
  HEAD is not returned when it differs from both the declaration and the configured
  primary); corrupt `meta.json` → `MissionMetaReadError`; invoked from a lane worktree →
  `repo_root` is the canonical primary.
- `.venv/bin/python -m pytest tests/specify_cli/core/test_command_target.py -q`
- `make format-check-files FILES=src/specify_cli/core/command_target.py tests/specify_cli/core/test_command_target.py`
- `.venv/bin/python -m pytest tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_layer_rules.py tests/architectural/test_pyproject_shape.py -q`
