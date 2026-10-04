---
work_package_id: WP01
title: Stress fixture is a well-formed coordination Mission
dependencies: []
requirement_refs:
- FR-001
- NFR-001
- NFR-002
- SC-001
planning_base_branch: kitty/nightly-reds-b-2026-10-04
merge_target_branch: kitty/nightly-reds-b-2026-10-04
branch_strategy: Planning artifacts for this mission were generated on kitty/nightly-reds-b-2026-10-04. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/nightly-reds-b-2026-10-04 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-reds-b-01M42YYF
base_commit: b3970b2c82a91bace43b04746b7f198ace27e09a
created_at: '2026-10-04T08:07:49.721596+00:00'
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Nightly red repair
history:
- at: '2026-10-04T08:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/stress/test_concurrent_emits.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/stress/test_concurrent_emits.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Stress fixture is a well-formed coordination Mission

## Objectives & Success Criteria

- `tests/stress/test_concurrent_emits.py` passes 2/2 (base: `test_concurrent_emits_produce_valid_event_log` fails, 20 of 20 emitters raise `StatusContractError: coordination_transaction_append requires a coordination worktree path`).
- Requirement refs: FR-001, NFR-001, NFR-002, SC-001.

## Context & Constraints

Root cause (see `research/nightly-red-memo.md`): commit `5b5699e50` made the placement seam read the Mission's routing from `meta.json`; a Mission dir with no `meta.json` degrades to the PRIMARY checkout, where a coordination append is refused. The same commit added `_write_modern_meta(repo)` to the sibling unit tests in `tests/specify_cli/coordination/test_transaction.py` but missed this nightly-only stress file. Once `meta.json` exists, a second fixture defect surfaces: `MID8 = "01J6STRSS"` is 9 characters; `mid8` is single-derived as `mission_id[:8]` (FR-012, `src/mission_runtime/context.py`), so the seam computes a different coordination worktree and raises `CoordinationWorktreeUnmaterialized`.

## Subtasks & Detailed Guidance

### Subtask T001 – Write the Mission meta.json

- In `_init_coord_repo`, after creating `COORD_BRANCH`, write `kitty-specs/<FEATURE_DIRNAME>/meta.json` with `mission_id`, `mission_slug` (= `FEATURE_DIRNAME`), `target_branch: "main"`, `coordination_branch: COORD_BRANCH` — the same shape as `_write_modern_meta` in `tests/specify_cli/coordination/test_transaction.py`. Leave it uncommitted, as that helper does.
- Add a docstring stating why (the seam reads routing from `meta.json`; a real coordination Mission always has it before its first `acquire()`).

### Subtask T002 – Valid mid8

- `MID8 = "01J6STRS"` and `MISSION_ID = f"{MID8}000000000000000000"` (26 chars, `MISSION_ID[:8] == MID8`), with a comment that mid8 is `mission_id[:8]`.

### Subtask T003 – Evidence

- Base red: run the file on the planning base (before your commit) — 1 failed, 1 passed.
- Lane green: 2 passed.
- Also run `tests/architectural/test_timing_coverage_invariant.py` (it pins this file's correctness test body).

## Risks & Mitigations

- Do not edit the body of `test_concurrent_emits_produce_valid_event_log`; it is pinned verbatim.

## Review Guidance

- The fixture now matches what `mission create` writes; no assertion changed; the 20-emitter count and timeout are unchanged.

## Branch Strategy

- **Strategy**: lanes_with_coord
- **Planning base branch**: kitty/nightly-reds-b-2026-10-04
- **Merge target branch**: kitty/nightly-reds-b-2026-10-04

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

## Binding rules for this WP

- Commits: author AND committer are `Stijn Dejongh <stijn.dejongh@sddevelopment.be>`; set `git config user.name "Stijn Dejongh"` and `git config user.email "stijn.dejongh@sddevelopment.be"` in the lane worktree before committing. End every commit message you write with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Run tests foreground by named node id or file only: `PWHEADLESS=1 <repo>/.venv/bin/python -m pytest -p no:cacheprovider -q -n0 -m "" <ids>`. Never a directory, never `make test-full`.
- No retries, skips, xfails, deselections, timeout or budget changes; keep every assertion except the stale literal named below.
- Do not touch any file outside `owned_files`.
- `ruff check` and `uv run --frozen ruff format --check --force-exclude` on every touched Python file.

## Activity Log

- 2026-10-04T08:10:00Z – system – Prompt created.
