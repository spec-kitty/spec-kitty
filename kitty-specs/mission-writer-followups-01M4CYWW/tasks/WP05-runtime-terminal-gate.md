---
work_package_id: WP05
title: Runtime terminal gate runs before completion; speculative rollback removed
dependencies: []
requirement_refs:
- FR-009
- FR-010
- FR-011
- NFR-001
- NFR-005
- C-006
planning_base_branch: issue-5883-mission-writer-followups
merge_target_branch: issue-5883-mission-writer-followups
branch_strategy: Planning artifacts for this mission were generated on issue-5883-mission-writer-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5883-mission-writer-followups unless the human explicitly redirects the landing branch.
subtasks:
- T020
- T021
- T022
- T023
- T024
phase: Phase 3 - Runtime
history:
- at: '2026-10-08T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent:
- tests/runtime/test_terminal_gate_before_completion.py
execution_mode: code_change
model: claude-sonnet
owned_files:
- src/runtime/next/runtime_bridge.py
- src/runtime/next/runtime_bridge_retrospective.py
- src/runtime/next/runtime_bridge_engine.py
- src/runtime/next/_internal_runtime/engine.py
- src/runtime/next/_internal_runtime/retrospective_hook.py
- tests/runtime/test_bridge_decide_next.py
- tests/runtime/test_bridge_retrospective.py
- tests/runtime/test_bridge_decision_log_flush.py
- tests/runtime/test_bridge_no_compat_delegates.py
- tests/next/test_runtime_bridge_unit.py
- tests/runtime/test_terminal_gate_before_completion.py
tags: []
tracker_refs: []
---
# Work Package Prompt: WP05 – Runtime terminal gate runs before completion; speculative rollback removed

## Objective

On every legacy `next` path, including the stale-plan and no-plan fallbacks, the retrospective gate runs as the engine's abort-only `before_run_completed` hook before anything is appended to `run.events.jsonl` or `state.json`. A refusal reads as a typed retrospective-gate refusal. The speculative capture, the rollback and `_BufferingRuntimeEmitter` are deleted.

## Independent test

`tests/runtime/test_terminal_gate_before_completion.py` (US5): a refused terminal step leaves both files byte-identical to what other writers left, on `commit_advance`, the stale-plan fallback and the no-plan fallback; a concurrent append from another writer survives a refusal; the refusal decision shape on the legacy and composition paths; a terminal re-poll does not re-run the gate or the non-blocking capture.

## Subtasks

- **T020**: Red-first: a foreign append made between the speculative capture and the rollback is cut today; the stale-plan fallback appends completion before the gate (FR-009, FR-011)
- **T021**: `engine.next_step` takes `before_run_completed: Callable[[], None] | None`; `_dn_advance_engine` passes the retrospective hook to both `commit_advance` and `next_step`
- **T022**: One bridge-level adapter wraps every hook failure (`MissionCompletionBlocked(decision)`, the policy error, a capture exception) in one typed refusal on the legacy and composition paths, caught before the generic engine-error and `_advance_failed_decision` handlers (B6)
- **T023**: Delete `_dn_capture_pre_speculative_state`, `_dn_rollback_buffered_run_state`, `_BufferingRuntimeEmitter` and their tests; update the five test files R4 names (FR-010)
- **T024**: Pin the re-poll behaviour: the gate and the non-blocking learning capture fire only on the transition into terminal (B7)

## Notes and risks

`src/runtime` must not gain a `specify_cli` import (C-001). Keep `engine._append_event` append-only. Run `tests/runtime tests/next` plus `tests/architectural/test_layer_rules.py`. The T020 foreign-append reproduction is FR-010's red proof; the Rule 1 runtime scan arrives later in WP08. Handoff: `runtime_bridge.py` is edited again by WP07 (board override); `tests/next/test_runtime_bridge_unit.py` again by WP06 (template path).

## Dependencies

None.

## Rules for every WP in this Mission

- Read `.kittify/charter/charter.md`, then `kitty-specs/mission-writer-followups-01M4CYWW/spec.md` and `plan.md`. The plan's "Amendments after the post-plan squad" section (A*, B*, C* items) is binding and overrides D1–D10 where they disagree. `research.md` line numbers are indicative; re-derive them.
- **Red-first (C-006).** For every requirement marked "no-op passable: no", commit the reproduction first and show it failing against the pre-fix code; record the command and the failing output in the Activity Log. Compound requirements are proven part by part.
- **Concurrency tests (NFR-001).** Run the two writers on distinct threads or processes (the lock is re-entrant per thread), use injected pause points rather than sleeps, and pass 5 of 5 repeated runs. Mutation-check each one: remove the lock and confirm the test fails.
- **Quality (NFR-005).** `uv run --frozen ruff check <files>`, `uv run --frozen ruff format --check --force-exclude <files>` and `uv run --frozen mypy <files>` report no new issues. No new `noqa` or `type: ignore`. Every touched function has complexity ≤ 15. Every new branch or helper has a focused test.
- **Tests.** Run your own test files, the test directory of each owning subsystem and `make test-fast`. Never run `make test-full` or the bare `tests/architectural/` directory; run only the specific architectural gate files you implicate. Use `.venv/bin/python -m pytest ...` (not a bare `uv run` that re-syncs). Record the exact commands and the pass/fail counts in the Activity Log.
- **Baseline red.** Classify a failure you did not cause per CLAUDE.md (pre-existing P0, CI env, stale install, stale venv) before chasing it.
- **Commits.** Commit with explicit paths (never `git add -A`, never `git stash`), with a conventional subject scoped `(mission-writer-followups)`, and end every message with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01WiYizc1WL4ic8QMezcXUiy
  ```
  Commit after each subtask so a lost session loses nothing. Do not push; the orchestrator pushes.
- **Status.** Mark each subtask with `spec-kitty agent tasks mark-status <Txxx> --status done --mission mission-writer-followups-01M4CYWW`. When the WP is complete, move it with `spec-kitty agent tasks move-task <WP> --to for_review --mission mission-writer-followups-01M4CYWW --note "<summary>"`.
- **Pre-existing failures (charter).** If you hit a failure that is red on the base too and is not yours, do not chase it. Put the failing test id, the evidence that it is red on the base, and a proposed issue title in your final report; the orchestrator files the GitHub issue before work continues past it.
- **Tracer files (charter standing order).** Append at least one finding per WP with `spec-kitty agent tracer-append --mission mission-writer-followups-01M4CYWW --category approach|design-decisions|tooling-friction --entry "..." --actor <you>`. Record red-first evidence under approach, non-obvious choices under design-decisions, and CLI friction under tooling-friction.
- **Issue matrix.** Before moving the WP to for_review, record the verdict for each issue this WP finishes: `spec-kitty agent issue-verdict --mission mission-writer-followups-01M4CYWW --issue "#NNNN" --verdict in-mission --wp <WP> --actor <you>`. The issues are #5883 (writers and gate), #5884 (the runtime run log) and #5885 (planning flow and wording). The final WP of each issue's set records `fixed` instead.
- **Sources only (C-003).** Edit `packs/built-in/...` sources, never the generated agent copies.

## Definition of done

- Every subtask is done and marked; every red-first reproduction was shown failing on the pre-fix code and now passes.
- The owned tests, the owning subsystem test directories, the implicated architectural gate files and `make test-fast` pass, with the commands and counts recorded in the Activity Log.
- ruff, ruff format and mypy are clean on changed files; there are no new suppressions.
- Every change is committed with explicit paths.

## Activity Log

- 2026-10-08T12:00:00Z – system – Prompt created.
