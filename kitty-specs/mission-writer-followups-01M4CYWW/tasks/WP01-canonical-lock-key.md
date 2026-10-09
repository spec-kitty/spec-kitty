---
work_package_id: WP01
title: 'One canonical Mission lock key: the key function and the core doors'
dependencies: []
requirement_refs:
- FR-005
- C-002
- NFR-002
- NFR-003
- C-006
- NFR-005
planning_base_branch: issue-5883-mission-writer-followups
merge_target_branch: issue-5883-mission-writer-followups
branch_strategy: Planning artifacts for this mission were generated on issue-5883-mission-writer-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5883-mission-writer-followups unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Lock key
history:
- at: '2026-10-08T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- tests/status/test_mission_lock_key.py
execution_mode: code_change
model: claude-sonnet
owned_files:
- src/specify_cli/status/mission_write.py
- src/specify_cli/status/locking.py
- src/specify_cli/status/__init__.py
- src/specify_cli/missions/_read_path_resolver.py
- src/specify_cli/coordination/transaction.py
- src/specify_cli/coordination/status_transition.py
- src/specify_cli/lanes/branch_naming.py
- tests/status/test_mission_lock_key.py
- src/specify_cli/coordination/legacy_resolution.py
tags: []
tracker_refs: []
---
# Work Package Prompt: WP01 – One canonical Mission lock key: the key function and the core doors

## Objective

`mission_lock_key(feature_dir)` exists and the core doors use it: `mission_write_lock`, `_holds_mission_lock`/`capture_rollback_point`, `mission_write_lock_dir`, `BookkeepingTransaction` and `coord_status_lock`. On a legacy bare-directory coordination Mission (`060-test` primary with a `060-test-<mid8>` coordination surface), these resolve one lock file. WP13 then moves every remaining caller onto the key.

## Independent test

`tests/status/test_mission_lock_key.py`: key equality across primary, coordination, flat and bare-directory coordination Missions; the mid8 cascade; the empty-mid8 typed error; key stability inside a hold; capture under a held primary lock; the subprocess-count check.

## Subtasks

- **T001**: Red-first: the bare-directory coordination fixture shows the transaction and `mission_write_lock`/emit resolving different lock files, and `capture_rollback_point` raising under a held primary lock after a naive rekey (plan A1, A2)
- **T002**: `mission_lock_key(feature_dir)` in `status/mission_write.py`, using the transaction's mid8 cascade through one shared helper (with `branch_naming`/`resolve_transaction_mid8`); a typed error for a coordination-routed Mission with no resolvable mid8, and the transaction's trailing-dash key (`status_transition.py` legacy NNN arm) fixed to use the same function; the key read from the canonical primary `meta.json` via the read-path resolver (A3, A4)
- **T003**: Thread-local held-key reuse: nested entries for the same Mission reuse the held key; a test with `flatten_coordination_metadata`-style meta mutation inside a hold (A4)
- **T004**: Route the core doors through the key: `mission_write_lock`, `_holds_mission_lock`/`capture_rollback_point`, `mission_write_lock_dir`, `BookkeepingTransaction._mission_specs_dir_name`, `coord_status_lock`; the NFR-003 subprocess delta with a warmed `git_common_dir` cache (A12)

## Notes and risks

Keep `feature_status_lock`'s signature. Handoff: the remaining direct `feature_status_lock` callers and `hold_mission_write_lock` move in WP13, and `implement_phases.py` is later edited for wording by WP10.

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
