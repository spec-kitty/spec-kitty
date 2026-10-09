---
work_package_id: WP13
title: Every per-Mission lock caller uses the canonical key
dependencies:
- WP01
requirement_refs:
- C-002
- NFR-001
- NFR-002
- NFR-005
- C-006
planning_base_branch: issue-5883-mission-writer-followups
merge_target_branch: issue-5883-mission-writer-followups
branch_strategy: Planning artifacts for this mission were generated on issue-5883-mission-writer-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5883-mission-writer-followups unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T053
- T054
phase: Phase 1 - Lock key
history:
- at: '2026-10-08T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- tests/status/test_mission_lock_order.py
execution_mode: code_change
model: claude-sonnet
owned_files:
- src/specify_cli/status/emit.py
- src/specify_cli/status/work_package_lifecycle.py
- src/specify_cli/status/lifecycle_events.py
- src/specify_cli/status/migrate_lifecycle_envelope.py
- src/specify_cli/coordination/coord_seed.py
- src/specify_cli/coordination/commit_router.py
- src/specify_cli/cli/commands/agent/workflow_executor.py
- src/specify_cli/cli/commands/implement_phases.py
- src/specify_cli/cli/commands/agent/tasks_move_task_executor.py
- src/specify_cli/cli/commands/agent/tasks_mark_status.py
- src/specify_cli/cli/commands/agent/status.py
- src/specify_cli/cli/commands/agent/finalize_status_surface.py
- src/specify_cli/decisions/emit.py
- src/specify_cli/retrospective/lifecycle_events.py
- src/specify_cli/review/cycle.py
- src/specify_cli/migration/backfill_runtime_state.py
- src/specify_cli/migration/rebuild_state.py
- src/specify_cli/migration/verdict_provenance_backfill.py
- tests/status/test_mission_lock_order.py
tags: []
tracker_refs: []
---
# Work Package Prompt: WP13 – Every per-Mission lock caller uses the canonical key

## Objective

Every remaining per-Mission lock caller takes its key from `mission_lock_key(...)` and its path from `mission_write_lock_dir(...)` or a function parameter. That covers every direct `feature_status_lock(root, X.name)` caller, `hold_mission_write_lock`, and the lock-path arguments in `workflow_executor`, `implement_phases` and `commit_router`. A legacy bare-directory coordination Mission locks one file in one order from every door.

## Independent test

`tests/status/test_mission_lock_order.py`: on the bare-directory coordination fixture, the lifecycle path and the implement claim path run on two threads without deadlocking and serialize on one lock file; a parametrized check over every converted caller.

## Subtasks

- **T005**: Red-first: on the bare-directory coordination fixture, after WP01, a direct `feature_status_lock(root, X.name)` caller (for example the lifecycle path) and `hold_mission_write_lock` take different lock files and can invert order against `BookkeepingTransaction` (A1)
- **T053**: Convert every direct `feature_status_lock` caller listed in A1 (emit, work_package_lifecycle, lifecycle_events, migrate_lifecycle_envelope, move-task, mark-status, agent status, decisions emit, finalize status surface, retrospective lifecycle events, review cycle, coord_seed, the migrations), and route `hold_mission_write_lock` plus the lock-path arguments in `workflow_executor.py` (`:230`, `:1085`, `:1888`), `implement_phases.py:415` and `commit_router.py:799` through `mission_write_lock_dir(...)` or a parameter (gate Rule 3 shape, A6)
- **T054**: Disposition the two Rule 1 whole-file rewrites: `migration/rebuild_state.py` (`os.replace` onto the events log) and `status/migrate_lifecycle_envelope.py` run their rewrite under the Mission lock (A7); the cross-thread lock-order test

## Notes and risks

Re-derive the caller list with `grep -rn "feature_status_lock(\|mission_write_lock(\|hold_mission_write_lock(\|coord_status_lock(" src`. Handoff: `implement_phases.py` is edited again by WP10 (wording).

## Dependencies

WP01

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
