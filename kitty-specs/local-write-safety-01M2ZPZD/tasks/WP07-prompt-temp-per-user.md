---
work_package_id: WP07
title: Prompt temp per-user
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-010
- FR-011
planning_base_branch: fix/local-write-safety
merge_target_branch: fix/local-write-safety
branch_strategy: Planning artifacts for this mission were generated on fix/local-write-safety. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/local-write-safety unless the human explicitly redirects the landing branch.
subtasks:
- T022
- T023
- T024
history:
- at: '2026-09-20T16:18:00Z'
  by: claude
  note: Authored by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent:
- tests/unit/runtime/test_prompt_tmp_namespace.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/runtime/next/_tmp_namespace.py
- tests/unit/runtime/test_prompt_tmp_namespace.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
Load `python-pedro` via `/ad-hoc-profile-load` (+ `charter context --action implement`); apply and state.

## Objective
Move prompt temp files out of the world-shared predictable `$TMPDIR` path into the per-user
runtime root, symlink-safe and never world-readable — closing #4721's symlink, cross-user DoS, and
information-disclosure facets in one move.

## Context
- `runtime/next/_tmp_namespace.py::prompt_tmp_dir()` roots prompt files at
  `tempfile.gettempdir()/spec-kitty-prompts/<sha>` via `mkdir(parents=True, exist_ok=True)`
  (default umask → 0755): world-shared, predictable, symlink-plantable, and 0644-readable by other
  local users.
- This is a **distinct** instance of the #4756 world-shared-predictable-temp class (folded in fully per the operator decision).
- Depends on **WP01** (consume the canonical `kernel.no_follow` helper).
- See `../research.md` D1/D3.

## Subtasks

### T022 — Relocate + harden the prompt temp dir
- Compute the prompt temp dir under the per-user runtime root (`~/.spec-kitty`, e.g. `get_runtime_root()`), not `gettempdir()`. Create it owner-only (`0700`); write prompt files via the no-follow helper; ensure files are never world-readable (`≤0600`).

### T023 — Red-first symlink + relocation + confidentiality assertions
- Plant a symlink at the prompt path → victim; assert bytes intact + refuse. Assert the resolved dir is under `~/.spec-kitty` (isolated HOME), not `$TMPDIR`. Assert prompt files are mode ≤`0600`. Red-first.

### T024 — Confirm DoS + info-disclosure facets closed
- Per-user isolation removes the cross-user DoS (another user can no longer pre-create/deny the shared dir); `≤0600` removes the prompt-content information disclosure. Add **assertions** mapping each facet to its check (a note is not a proof): the resolved dir is under the per-user root (DoS), and prompt files are mode `≤0600` (info-disclosure).

## Branch Strategy
Base/merge `fix/local-write-safety`. Depends on WP01. `spec-kitty agent action implement WP07 --agent claude`.

## Definition of Done (non-fakeable)
- Prompt dir resolves under `~/.spec-kitty` (isolated HOME), not world-shared temp (SC-006).
- Symlink-plant refused + bytes intact (SC-001); prompt files never world-readable (SC-005).
- DoS + info-disclosure facets demonstrably closed (assertions, not a note).
- **Red-first evidence**: PR "Tests run" includes the failing-on-current-code output for the prompt symlink-plant + world-readable tests.
- ruff + mypy clean; complexity ≤15.

## Risks & Reviewer Guidance
- **Risk**: copying #4721's partial shape (per-repo hash subdir still under `/tmp`). Reviewer: confirm the dir is under the per-user root, not a `gettempdir()` subdir.
