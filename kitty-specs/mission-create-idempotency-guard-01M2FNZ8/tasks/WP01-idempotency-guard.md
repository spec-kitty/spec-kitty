---
work_package_id: WP01
title: Idempotency guard + abandonment-aware auto-allow + escape hatch (#4033)
dependencies: []
requirement_refs:
- C-001
- C-002
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: fix/mission-create-idempotency-4033
merge_target_branch: fix/mission-create-idempotency-4033
branch_strategy: Planning artifacts for this mission were generated on fix/mission-create-idempotency-4033. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/mission-create-idempotency-4033 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-create-idempotency-guard-01M2FNZ8
base_commit: 3cd6acb6e77abb9e5b0423e9b6200a4e7adb243d
created_at: '2026-09-14T10:09:17.843479+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
history:
- created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/
create_intent:
- tests/core/test_mission_create_idempotency_guard.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/core/mission_creation.py
- src/specify_cli/cli/commands/agent/mission_create.py
- tests/core/test_mission_create_idempotency_guard.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile
Run `/ad-hoc-profile-load python-pedro` before anything else — TDD/red-first, type-safe Python 3.11+.

## Objective
Stop `spec-kitty specify` / `agent mission create` from silently creating a duplicate mission on a re-run (#4033), with an abandonment-aware auto-allow and an explicit `--allow-duplicate` escape hatch. Design is operator-decided (see spec.md Intent Summary) — do NOT deviate.

## Context (grounded)
- Single seam: `src/specify_cli/core/mission_creation.py::_create_mission_core_impl` — hosts the early guards (git-repo, `has_unborn_head`, detached-HEAD) **before** any scaffold/branch write. The new guard goes there.
- `_list_mission_scaffolds(repo_root)` enumerates existing `kitty-specs/` mission dirs — the detection primitive.
- `create_mission_core(...)` already carries opt-in flags (`force_recreate_coordination_branch`, `allow_worktree_context`, `retain_*`) — add `allow_duplicate: bool = False` the same way.
- CLI: `src/specify_cli/cli/commands/agent/mission_create.py` invokes `create_mission_core` through the deterministic error funnel — add the `--allow-duplicate` typer option and pass it through. `/spec-kitty.specify` calls `agent mission create`, so the flag flows through it.

## Subtasks
- **T001 — abandonment classifier.** For each prior mission dir with the SAME `mission_slug` AND SAME `mission_type` (from its `meta.json`), classify **abandoned** vs **live** by reducing its `status.events.jsonl` (use the existing status reducer/reader): abandoned = canceled, OR genesis / no lifecycle progress / spec never committed. **Fail closed (C-002):** if a prior mission's state can't be read, treat it as **live**.
- **T002 — guard.** In `_create_mission_core_impl`, after the existing early guards and **before** any scaffold/branch write, if a **live** same-key prior mission exists and `allow_duplicate` is False → raise `MissionCreationError` naming the existing mission (slug + mid8) and the `--allow-duplicate` override.
- **T003 — flag threading.** Add `allow_duplicate: bool = False` to `create_mission_core` + `_create_mission_core_impl`; add `--allow-duplicate/--allow-dup` to `agent mission create` and pass it through the funnel. Confirm `/spec-kitty.specify`'s create call can pass it (factory/programmatic callers pass `allow_duplicate=True`).
- **T004 — red-first tests** (`tests/core/test_mission_create_idempotency_guard.py`, pytestmark matching siblings): an issue-pinned `@pytest.mark.regression` repro that creates the same mission twice through `create_mission_core` and asserts the SECOND currently succeeds (the bug) — RED before T002, then flip its assertion to the guarded refusal / or replace with the guarded-refusal unit test after the fix (do not leave a `regression`-marked passing test). Unit tests: guard fires on live duplicate; abandoned prior → auto-allow (no flag); `allow_duplicate=True` → second mission created; same-slug/different-type → allowed; **no orphan scaffold** in `kitty-specs/` after a refusal (NFR-002).
- **T005 — no-regression + quality.** `PWHEADLESS=1 SPEC_KITTY_ENABLE_SAAS_SYNC=0 uv run --no-sync python -m pytest tests/core -q` green; ruff/format/mypy clean on the two source files + the test; complexity ≤15 (extract a small `_find_live_duplicate(...)` helper if the guard pushes `_create_mission_core_impl` over).

## Branch Strategy
Planning/base + lane-consolidation target: `fix/mission-create-idempotency-4033`; the PR targets `main`. Enter the resolved lane workspace from `lanes.json`.

## Definition of Done
FR-001..004 satisfied; NFR-001 (tests/core green), NFR-002 (no orphan on refusal), NFR-003 (ruff/mypy/complexity + red-first). C-001 (single seam), C-002 (fail-closed) honored.

## Risks / reviewer guidance
- **Over-refusal breaking the factory / re-run-after-abandon** — reviewer: confirm abandoned priors auto-allow and `--allow-duplicate` overrides; a blind same-slug refusal is a regression.
- **Orphan on refusal** — reviewer: confirm the guard is BEFORE scaffold write and `kitty-specs/` is untouched on refusal.
- **Fail-closed** — reviewer: confirm an unreadable prior mission is treated as live (refuse), not silently skipped.
