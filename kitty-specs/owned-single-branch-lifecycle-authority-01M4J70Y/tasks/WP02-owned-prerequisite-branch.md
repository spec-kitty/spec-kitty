---
work_package_id: WP02
title: Owned prerequisite branch contract
dependencies:
- WP01
requirement_refs:
- C-001
- C-003
- FR-002
- FR-008
- NFR-002
- SC-001
- SC-002
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
phase: Phase 2 - Prerequisites
history:
- at: '2026-10-10T06:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/mission_check_prerequisites.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/mission_check_prerequisites.py
- tests/integration/test_owned_protected_single_branch.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5877'
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile with the `/spk-charter-profile-load` skill (profile: `python-pedro`, role: implementer). Then continue.

# Work Package Prompt: WP02 – Owned prerequisite branch contract (#5877)

## Objectives & Success Criteria

- For a protected PR-bound owned mission (checkout on the minted `kitty/mission-…` branch, landing target protected `main`), `check-prerequisites` reports `branch_matches_target: true` and `branch_context.expected_checkout_branch == <minted write branch>`, while `target_branch` still shows the protected landing target (FR-002).
- `commit_to_target` missions (write branch == target) keep `expected_checkout_branch == target_branch`; a wrong HEAD still refuses `OWNED_BRANCH_REFUSED`; non-owned callers are byte-identical (FR-008).
- `ruff` + `mypy --strict` clean (NFR-002).

## Context & Constraints

- Grounding + provenance: `../research.md` (row #5877), `../plan.md` IC-02.
- Repair branch to land-and-verify: `codex/5877-owned-prerequisites`, fix `96252a666` + test `0c9768e57`. **Adopt-as-is** — the base file is byte-identical to origin/main.
- Root cause (origin/main): `mission_check_prerequisites.py` — the `_emit_check_prerequisites_result(...)` call omits `expected_checkout_branch`, so the already-minted `owned.write_branch` is dropped; `mission_branch_context.py::_inject_branch_contract` then defaults the match reference to `target_branch` (the final `main`), judging a HEAD on the minted branch a mismatch.
- Model: `core/owned_mission._branch_matches_target` (the minter's own branch rule over `expected_write_branch(meta)`); `git/protection_policy.resolve_for_owned` threads the same fact.
- Charter: C-001 single resolver; C-003 ATDD red-first.

## Branch Strategy

- **Planning base branch**: main · **Merge target branch**: main. Runs in the write checkout.

## Subtasks & Detailed Guidance

### Subtask T006 – ATDD: port the owned prerequisite reproduction (RED first)

- **Steps**: Port into `tests/integration/test_owned_protected_single_branch.py` (from `0c9768e57`): `test_protected_mint_prerequisites_use_validated_write_branch` (parametrized `paths_only` × `explicit_owned`) asserting `current_branch == minted`, `target_branch == _TARGET`, `branch_matches_target is True`, `branch_context.expected_checkout_branch == minted`, and no checkout mutation; plus `test_commit_to_target_prerequisites_keep_target_contract` (control) and `test_protected_mint_prerequisites_refuse_wrong_checkout_branch` (wrong HEAD → `OWNED_BRANCH_REFUSED`).
- **Validation**: RED on the WP base (false mismatch). Record it.

### Subtask T007 – Thread owned.write_branch into the prerequisite emitter

- **Steps**: Apply `96252a666`: add keyword-only `expected_checkout_branch: str | None = None` to `_emit_check_prerequisites_result`, forward it into `_inject_branch_contract(...)`; in `check_prerequisites` pass `expected_checkout_branch=owned.write_branch if owned else None`. No other change; no new git reads (reuse the minted fact). Non-owned callers pass `None` → identical legacy contract.
- **Files**: `src/specify_cli/cli/commands/agent/mission_check_prerequisites.py`.

### Subtask T008 – Validate green

- **Steps**: Run `tests/integration/test_owned_protected_single_branch.py` + the prerequisite/branch-context test modules; format-check + ruff + mypy on the changed file. Green.

## Definition of Done

- Repro RED→GREEN; control + wrong-branch refusal pass; non-owned unchanged; lint/type clean.

## Reviewer Guidance

- Confirm the landing target is still reported as the protected branch while the match reference is the minted write branch; confirm no `core/paths.py` change and no new resolver.
