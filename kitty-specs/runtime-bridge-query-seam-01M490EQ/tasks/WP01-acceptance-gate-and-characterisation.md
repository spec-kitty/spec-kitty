---
work_package_id: WP01
title: Acceptance gate and characterisation
dependencies: []
requirement_refs:
- FR-007
- FR-004
- SC-003
planning_base_branch: issue-2560-runtime-bridge-query-seam
merge_target_branch: issue-2560-runtime-bridge-query-seam
branch_strategy: Planning artifacts for this mission were generated on issue-2560-runtime-bridge-query-seam. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2560-runtime-bridge-query-seam unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Red-first contract
history:
- at: '2026-10-06T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/runtime/test_runtime_bridge_query_
create_intent:
- tests/runtime/test_runtime_bridge_query_seam_layout.py
- tests/runtime/test_runtime_bridge_query_characterisation.py
execution_mode: code_change
model: claude-opus-5-5
owned_files:
- tests/runtime/test_runtime_bridge_query_seam_layout.py
- tests/runtime/test_runtime_bridge_query_characterisation.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Acceptance gate and characterisation

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission runtime-bridge-query-seam-01M490EQ`) or the Activity Log below. Address all feedback before the work is complete.

## Branch Strategy

- Planning/base branch: `issue-2560-runtime-bridge-query-seam` (stacked on `issue-2561-retire-runtime-bridge-delegates`, PR #5822).
- Final merge target: `issue-2560-runtime-bridge-query-seam`.
- Topology `single_branch`: the WP runs in the repository root checkout; there is no lane worktree.

## Shared rules (all WPs)

- Behaviour-preserving (spec C-001). The one accepted delta is logger names for moved code (plan "Accepted deltas").
- Source changes stay inside `src/runtime/next/` (C-002). No forwarding delegate or self-alias in `runtime_bridge.py` (C-003). New modules follow the `runtime_bridge_<name>.py` convention.
- Moved code is moved **verbatim** (cut/paste plus import fix-ups only). Do not "improve" moved bodies.
- The bridge calls a moved name as `<alias>.<name>` (`_mapping`, `_decision_log`, `_query`). Drop every import the bridge no longer uses (ruff F401), so a stale `runtime_bridge.<name>` patch raises AttributeError.
- **Patch review rule (squad T-1/T-2):** when a test's import or patch of a moved name is repointed, review every other patch in the same test and `with` block by call path. A patch that steered moved code via the bridge must target the owning module now, and the test must assert its fake ran (`.assert_called()`, a call counter, or an observable effect only the fake produces).
- Complexity ≤ 15, no new `noqa`/`type: ignore`. `ruff check`, `ruff format --check --force-exclude <changed files>`, mypy over `src/runtime/next/` adds no error beyond the 21 on the base.

## Objective

Land the acceptance gate for the whole mission (red where the move has not happened, as strict-xfail rows), and pin the thin-coverage branches of the code that will move, before any code moves.

## Context

- Contract: `contracts/module-layout.md`; ownership table: `data-model.md`; move lists: plan D-1/D-2.
- Baseline coverage over the 111-path surface (research R-5) found missed lines in: `_reduced_wp_lane` (None snapshot), `_count_wp_endings` (no `tasks/`), `_resolve_wp_board_review_action` (re-read race), `_resolve_wp_board_action` (`ActionContextError` decline, unknown board step), `_build_decision_required_prompt_file` (no question; builder raises), `_map_wp_step_decision` (blocked reason), `_wrap_with_decision_git_log` (owned re-raise of `CoordinationWorkspaceUnavailable`), `answer_decision_via_runtime` (missing feature dir).

## Subtasks

### T001 — Module-layout contract test

File `tests/runtime/test_runtime_bridge_query_seam_layout.py`. Implements contracts §1–§5:
- per-owner "name defined by owner" rows, "bridge defines none / keeps no private attribute" rows, re-export identity rows, `__all__` unchanged, import-direction rows (AST, function-local imports included), "engine imports mapping" row;
- self-mutation rows: a planted bridge import (6 shapes) in the engine source is reported.
- A module-level `_EXTRACTED: dict[str, bool]` (mapping / decision_log / query, all `False` here) drives `pytest.param(..., marks=pytest.mark.xfail(strict=True, reason=...))` for every row that depends on a not-yet-extracted owner. Later WPs flip one key each; a row that starts passing before its flip fails the run (strict).
- Red-first evidence: before the xfail marks are applied, the file gives 56 failed / 7 passed on the base (research R-5).

### T002 — Characterise mapping gaps [P]

File `tests/runtime/test_runtime_bridge_query_characterisation.py`. Through the functions as reachable today (import from `runtime.next.runtime_bridge` via a single module-level `_owner(name)` helper, so WP02–WP04 repoint one lookup table, not each test):
- `_build_decision_required_prompt_file`: `question` falsy → `None`; builder returns a path → `str(path)`; builder raises → `None` (patch `runtime.next.prompt_builder.build_decision_prompt`, a module below the moved code; assert the fake ran).
- `_reduced_wp_lane(None)` → `"uninitialized"` lane string; `_count_wp_endings` on a feature dir with no `tasks/` → `(0, 0)`.
- `_resolve_wp_board_action` declines: an unresolvable mission → `_WP_BOARD_DECLINE`; board step `accept` → decline. Use a real fixture mission when practical; otherwise patch only `mission_runtime.resolve_action_context` / `runtime.next.decision._compute_wp_progress`-level collaborators, never bridge attributes.

### T003 — Characterise read-path gaps [P]

- `answer_decision_via_runtime` when the resolved feature dir does not exist: raises `MissionRuntimeError` whose text contains `cannot answer decision` (exact phrase); when `resolve_action_context` raises `ActionContextError`, the same typed exception (same `.code`) propagates.
- `query_current_state` when a temporary query run is started: the temp run store is removed afterwards (assert the dir is gone).
- `_query_read_runtime_plan` re-raises `QueryModeValidationError` unchanged.

### T004 — Characterise the decision-log owned re-raise [P]

`_wrap_with_decision_git_log` with `owned` set and `CoordinationWorkspace.resolve` raising `CoordinationWorkspaceUnavailable`: the typed exception propagates unwrapped (not `DecisionGitLogUnavailable`). With `owned=None` the same failure becomes `DecisionGitLogUnavailable`.

## Definition of Done

- Both files pass on the base; the layout file reports its contract rows as xfailed (strict) and the self-mutation rows as passed.
- No test in either file patches an attribute of `runtime.next.runtime_bridge`.

## Reviewer guidance

- Check the characterisation tests would actually fail if the branch changed (e.g. flip an expected value mentally).
- Check `_owner(name)` is the single lookup point.
