---
work_package_id: WP03
title: Red-first behaviour correction and fail-closed preservation
dependencies:
- WP02
requirement_refs:
- FR-006
- FR-007
- FR-008
- C-002
- C-003
- SC-004
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-declaration-first-repo-root-resolution-01M4TB21
base_commit: 8ea0b86b94379db5802a09ca77c954763be995c1
created_at: '2026-10-13T10:05:30Z'
subtasks:
- T008
- T009
- T010
phase: Phase 3 - Behaviour correction (red-first) + fail-closed preservation
history:
- at: '2026-10-13T10:05:30Z'
  actor: system
  action: Prompt generated via spec-kitty tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/core/test_command_target_behaviour.py
create_intent:
- tests/specify_cli/core/test_command_target_behaviour.py
- tests/specify_cli/workspace/test_declaration_first_failclosed_preserved.py
execution_mode: code_change
model: ''
owned_files:
- tests/specify_cli/core/test_command_target_behaviour.py
- tests/specify_cli/workspace/test_declaration_first_failclosed_preserved.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '6142'
---

# Work Package Prompt: WP03 – Red-first behaviour correction + fail-closed preservation

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` and run `spec-kitty charter context --action implement --json`.

## Objectives & Success Criteria

Prove the behaviour correction **red-first**, prove the existing fail-closed refusals are
unchanged, and file-and-link the deferred out-of-scope sites. This WP lands AFTER the
WP01/WP02 enablers (tidy-first).

### T008 — Red-first behaviour correction (FR-006, SC-003)

Commit a FAILING test first, then confirm GREEN:

- The correction: a mission-scoped resolution whose ambient location (checked-out branch /
  invoking worktree) disagrees with the Mission's stored declaration now resolves to the
  **declaration** (or fails closed), never to ambient location. Express it against the WP01
  entry and (where a site was routed in WP02) through that command, contrasting the entry's
  declaration-first result with the pre-entry ambient-biased pattern
  (`resolve_primary_branch(repo_root)` with `bias=True`, which returned the checked-out
  branch). Prove RED on the pre-fix tree and GREEN after (per charter C-011; swap the
  pre-fix resolver back and watch it fail).

### T009 — Fail-closed preservation (FR-007, C-002, C-003)

Negative tests asserting the existing refusals are byte-for-byte unchanged:

- `enforce_checkout_identity` (#3128, `src/mission_runtime/checkout_identity.py`) still
  raises `CheckoutIdentityError` for a WP-execution write from a foreign lane worktree.
- `resolve_checkout_identity` (#3328, `src/specify_cli/core/checkout_identity.py`) still
  returns a `FailClosedRefusal` for a WRITE invoked from a worktree.
- `get_status_read_root`'s worktree-preferring READ contract is untouched (the entry does
  not collapse a legitimate read to primary).

### T010 — Deferred-scope hygiene (FR-008)

- File a follow-up issue naming the filed-and-linked out-of-scope sites with reasons
  (merge-target `mission_accept_merge`; the `implement_claim` #2453-deferred guard;
  create-time seeds; project-scoped commands; honest-invocation-identity inputs) and the
  remaining un-routed command-entry seeds (Increment-2 surface).
- Refs the still-open siblings the entry forecloses: #2802, #5114.
- Append the approach / design-decisions tracers with the final routed set + exclusions.

## Constraints

- Keep the red-first test in its own file (unambiguous RED→GREEN witness).
- Do NOT modify #3128/#3328 code — assert, do not rewrite (ratchet).
- ruff + mypy clean.

## Validation (targeted test surface)

- `.venv/bin/python -m pytest tests/specify_cli/core/test_command_target_behaviour.py tests/specify_cli/workspace/test_declaration_first_failclosed_preserved.py -q`
- Re-run WP01/WP02 suites to confirm no regression.
- `make test-fast`
