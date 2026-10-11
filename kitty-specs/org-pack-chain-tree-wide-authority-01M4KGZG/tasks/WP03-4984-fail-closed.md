---
work_package_id: WP03
title: '#4984 fail-closed decision surfaces'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-005
- NFR-002
- NFR-003
planning_base_branch: feat/org-pack-chain-tree-wide-authority
merge_target_branch: feat/org-pack-chain-tree-wide-authority
branch_strategy: Planning artifacts for this mission were generated on feat/org-pack-chain-tree-wide-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/org-pack-chain-tree-wide-authority unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-org-pack-chain-tree-wide-authority-01M4KGZG
base_commit: 253aeee68af724fb510353b8e63f3acfa3f01692
created_at: '2026-10-10T18:52:24.249227+00:00'
subtasks:
- T009
- T010
- T011
- T012
- T013
history:
- created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/review/
create_intent:
- tests/specify_cli/review/test_gate_bindings_origin_strict.py
- tests/specify_cli/mission_step_contracts/test_executor_origin_strict.py
- tests/specify_cli/tool_surface/test_agent_profiles_origin_strict.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/review/gate_bindings.py
- src/specify_cli/mission_step_contracts/executor.py
- src/specify_cli/tool_surface/providers/agent_profiles.py
- tests/specify_cli/review/test_gate_bindings_origin_strict.py
- tests/specify_cli/mission_step_contracts/test_executor_origin_strict.py
- tests/specify_cli/tool_surface/test_agent_profiles_origin_strict.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load profile `python-pedro` via `/spk-charter-profile-load` before anything else.

## Objective

Complete #4984: the three governed **decision** surfaces must fail closed on a declared-but-missing org pack. Move each from the existing-filtered primitive to `resolve_pack_chain(..., strict=True)`, which raises naming the pack + the `spec-kitty charter fetch` remedy. This **is** a behaviour change (refuse vs silent-degrade) — land it red-first per ADR 2026-07-17-1.

## Red-first discipline (ADR 2026-07-17-1)

For each surface, FIRST add a focused regression that is RED through the real entry point before the fix: configure a declared-but-unfetched org pack, exercise the surface, assert it raises `ValueError` whose message names the pack and `spec-kitty charter fetch`. Mark it `@pytest.mark.regression` pinned to the issue (`p0_repro`/issue ref per repo convention). After the fix turns it green, keep it as a focused unit test (not left marked `regression` if that is the repo's transitional rule — follow the charter's test-remediation discipline).

## Subtasks

### T009 (red) → T010 (green) — `review/gate_bindings.py:286`
- T009: regression — an unfetched declared pack makes `_activated_msc_urns` raise with pack name + remedy.
- T010: `resolve_existing_org_roots(repo_root)` → `resolve_pack_chain(repo_root, strict=True)`.

### T011 (red) → T012 (green) — `mission_step_contracts/executor.py:194`
- T011: regression — unfetched pack makes `execute(...)` raise. **Do NOT touch `:173` (`resolve_org_dirs`) — out of scope.**
- T012: `resolve_existing_org_roots(context.repo_root)` → `resolve_pack_chain(context.repo_root, strict=True)`.

### T013 — `tool_surface/providers/agent_profiles.py:574`
- `tuple(resolve_org_roots(root))` + manual is-dir raise (575–577) → `resolve_pack_chain(root, strict=True)`. This already manual-raised; `strict=True` swaps the ad-hoc `"Required org profile root unavailable"` message for the canonical fetch-remedy one. Update/extend any test asserting the old message string (search `tests/` for it). Keep the is-dir loop only as a symlink/other-kind backstop, or remove it with a covering test.

## CHANGELOG
This WP's behaviour change needs a `docs/changelog/CHANGELOG.md [Unreleased]` entry — that is authored in the **closeout** phase (not owned by this WP) so the shared changelog is not a per-WP owned file. Note the operator-visible impact for the closeout author: review / step-contract execution / profile projection now **refuse** on a declared-but-unfetched pack instead of silently dropping it (#4984).

## Branch Strategy
Planning base + merge target: `feat/org-pack-chain-tree-wide-authority`. Lane worktree from `lanes.json`.

## Definition of Done
- 3 surfaces on `strict=True`; 3 red-first regressions now green; old-message test updated.
- New branches/tests in-commit; complexity ≤15.
- Targeted tests green: the three new test files + the existing suites for the three modules.
- `ruff check` + format clean.

## Risks / reviewer guidance
Reviewer: confirm each surface genuinely raises (not swallows) on an unfetched pack, the message names the pack + remedy, and the configured-chain happy path is unchanged. Confirm no `resolve_org_dirs` site was altered.
