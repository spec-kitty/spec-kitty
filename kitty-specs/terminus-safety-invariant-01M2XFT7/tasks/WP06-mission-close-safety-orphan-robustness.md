---
work_package_id: WP06
title: Mission close safety + orphan robustness (#4765 +
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- FR-013
planning_base_branch: issue-4764-terminus-safety-invariant
merge_target_branch: issue-4764-terminus-safety-invariant
branch_strategy: Planning artifacts for this mission were generated on issue-4764-terminus-safety-invariant. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4764-terminus-safety-invariant unless the human explicitly redirects the landing branch.
subtasks:
- T017
- T018
- T019
history:
- created by planner-priti at 2026-09-19T19:43:00Z
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/mission_type.py
create_intent:
- tests/integration/test_issue_4765_close_guard.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/mission_type.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before ANY other action, load the `python-pedro` profile via `/ad-hoc-profile-load` (skill `spk-doctrine-profile-load`, or `spec-kitty charter context --action implement` + `spec-kitty agent profile show python-pedro`). Adopt its identity, implementer-only boundaries, and TDD/type-safety discipline. Do not proceed until the profile is loaded.

## Objective

Two coupled changes on `mission_type.py`'s `close_cmd`:

1. **Fail-closed `is_mission_merged` guard** at the TOP of the non-discard `else` branch (before `_teardown_coordination_worktree`): refuse an unmerged mission with `Exit(1)` via `_emit_mission_error`, pointing at `--discard`, committing NO retrospective and emitting NO completion event (FR-004, FR-005). Fixes #4765 (today the non-discard branch fabricates a `runtime_post_completion` retrospective on the mainline for an unmerged mission).
2. **Orphan robustness** — tolerate an orphaned `coordination_branch` marker (no traceback), fix the doubled-slug render, and honor `--json` (FR-013, #2745 facet 3).

Delivers **FR-004, FR-005, FR-013**.

## Context

- **Spec**: US2 (mission close refuses an unmerged mission instead of fabricating completion) — US2-1 (unmerged non-discard close exits non-zero, writes no retrospective/commit, leaves coord worktree intact, points at `--discard`), US2-2 (a merged mission → existing teardown), US2-3 (`--discard` path unchanged). US5-3 (orphaned `coordination_branch` marker tolerated, slug rendered once, `--json` honored). Edge Case: an all-cancelled-but-unmerged mission must refuse and go via `--discard`, NOT be torn down as completed.
- **Contract**: `contracts/terminus-safety-contract.md` → **C-CLOSE** (PRE/REFUSE/PASS/ROBUST).
- **Data model**: `data-model.md` → **merged** predicate (`is_mission_merged`, `status/lifecycle.py:294`) is `mission close`'s guard (FR-004); `coordination_branch` field — close tolerates an orphaned marker (FR-013). **D4**: guard on `is_mission_merged`, NOT `is_mission_completed` (an all-terminal-but-unmerged mission must go via `--discard`).
- **Research** (`research.md`): the non-discard branch has zero preconditions today despite the docstring; it commits a `runtime_post_completion` retrospective via `coordination/teardown.py` and tears down the coord worktree. Mirror the existing `reopen_cmd` guard.
- **Seam anchors** (verified on this branch):
  - `src/specify_cli/cli/commands/mission_type.py:503` — `def close_cmd(...)`
  - `src/specify_cli/cli/commands/mission_type.py:514` — the `--discard` help ("Without --discard, requires that the mission has already been merged (no-op cleanup otherwise)")
  - `src/specify_cli/cli/commands/mission_type.py:639` — the non-discard `else` branch (guard goes at the TOP, before teardown)
  - `src/specify_cli/cli/commands/mission_type.py:644` — `_teardown_coordination_worktree(repo_root, mission_slug, mid8_value)` (the mutation to guard before)
  - `src/specify_cli/cli/commands/mission_type.py:1270` — `_emit_mission_error(message, *, code, json_output)` (the structured error envelope; honors `--json`)
  - `is_mission_merged` — import via the `specify_cli.status` facade (C-002)

## Per-Subtask Guidance

### T017 — RED-first #4765 + orphan tests

Create `tests/integration/test_issue_4765_close_guard.py`, `@pytest.mark.regression`, issue-pinned to #4765. Drive through the pre-existing `mission close` CLI entry point (C-004):
- **#4765 core**: an unmerged mission (no merge baseline) with an in-progress WP, `mission close` WITHOUT `--discard` ⇒ exits non-zero; commits NO `retrospective.yaml`; emits NO `RetrospectiveCaptured`/completion event; leaves the coordination worktree intact; the message points at `--discard` (US2-1, FR-004, FR-005).
- **Merged path non-regression**: a genuinely merged mission → the existing teardown still runs (US2-2).
- **Orphan robustness**: a mission left with an orphaned `coordination_branch` marker ⇒ `mission close` tolerates it (no traceback), renders the slug once (not doubled), and honors `--json` (US5-3, FR-013).

**Harness caveat**: for hook-routed errors, drive the app/error-hook seam (not a bare `CliRunner`). A plain `Exit(1)` is fine via `CliRunner`. Check how `_emit_mission_error` routes before choosing the harness.

RED before T018/T019, GREEN after.

### T018 — Fail-closed `is_mission_merged` guard

At the TOP of the non-discard `else` branch (:639), BEFORE `_teardown_coordination_worktree` (:644), call `is_mission_merged(feature_dir)` (facade import, C-002). If not merged: `_emit_mission_error(<message pointing at --discard>, code=<structured code>, json_output=json)` and raise `Exit(1)`. Write NOTHING (no retrospective, no commit, no completion event) and tear down NOTHING. This mirrors the existing `reopen_cmd` guard. Use `is_mission_merged`, NOT `is_mission_completed` (D4).

### T019 — Orphan tolerance + doubled-slug + `--json`

- Tolerate an orphaned `coordination_branch` marker: the close path must not raise a traceback when the coordination branch/worktree is already gone but the marker persists.
- Fix the doubled-slug render (the mission slug printed twice).
- Ensure `--json` is honored on this path (structured output, not human-only text).

## Branch Strategy

- **Planning base branch** and **merge target branch**: `issue-4764-terminus-safety-invariant`.
- Implement on the **single mission branch** directly — NOT lane worktrees. PR to `main` opens later; the operator merges.
- Commit the T017 red-first test as a distinct commit before T018/T019.

## ATDD / Test Strategy (red-first defect)

- **#4765** issue-pinned `@pytest.mark.regression` (T017): unmerged non-discard close → Exit(1), no retrospective, coord intact; RED before the fix (fabricated completion observable), GREEN after. Plus the orphan-branch close with `--json`.
- Run `tests/integration/test_mission_close.py` and the other close tests (`test_mission_close_discard_coord_teardown.py`, `test_issue_3716_discard_transactional_close_guard.py`) plus the mission_type CLI command tests. Record commands + counts. Do NOT regress the `--discard` path.

## Definition of Done

- [ ] `is_mission_merged` guard at the top of the non-discard `else`, before teardown; unmerged close refuses with `Exit(1)` via `_emit_mission_error`, points at `--discard`, writes/commits/emits NOTHING, leaves coord worktree intact (FR-004, FR-005).
- [ ] Guard uses `is_mission_merged`, NOT `is_mission_completed` (D4); the merged path and the `--discard` path are unchanged.
- [ ] Orphaned `coordination_branch` marker tolerated (no traceback); slug rendered once; `--json` honored (FR-013).
- [ ] T017 regression tests green; existing close/discard tests green.
- [ ] Import via the `specify_cli.status` facade (C-002); no new escaping error type (C-003).
- [ ] `ruff` + `ruff format --check` + `mypy` clean; C901 ≤ 15.
- [ ] `[Unreleased]` CHANGELOG note (impact-first, no version — C-005).

## Risks

- **Wrong predicate** — using `is_mission_completed` would tear down an all-cancelled-unmerged mission that should go via `--discard`. Mitigation: use `is_mission_merged` (D4); test the all-cancelled boundary.
- **Harness mismatch** — hook-routed errors not observable via a bare `CliRunner`. Mitigation: drive the app/error-hook seam for hook-routed errors.
- **`--discard` regression** — the guard leaking into the discard path. Mitigation: guard only the non-discard `else`; run the discard tests.

## Reviewer Guidance (reviewer-renata)

- Confirm the guard is at the TOP of the non-discard branch, before ANY write/commit/teardown, and refuses via the structured `_emit_mission_error` envelope honoring `--json` (C-003).
- Confirm `is_mission_merged` (not `is_mission_completed`) — D4; an all-cancelled-unmerged mission refuses and is pointed at `--discard`.
- Confirm no fabricated retrospective/completion event on refusal (FR-005).
- Confirm orphan tolerance (no traceback), single-slug render, `--json`.
- Confirm the #4765 test uses the correct harness (app/error-hook seam if hook-routed) and is genuinely red-first.
