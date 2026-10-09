---
work_package_id: WP04
title: Frontmatter, finalize and matrix writers take the lock
dependencies:
- WP02
requirement_refs:
- FR-002
- FR-003
- FR-004
- FR-005
- FR-020
- NFR-001
- NFR-005
- C-006
planning_base_branch: issue-5883-mission-writer-followups
merge_target_branch: issue-5883-mission-writer-followups
branch_strategy: Planning artifacts for this mission were generated on issue-5883-mission-writer-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5883-mission-writer-followups unless the human explicitly redirects the landing branch.
subtasks:
- T015
- T016
- T017
- T018
- T019
- T058
phase: Phase 2 - Writers
history:
- at: '2026-10-08T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/frontmatter.py
create_intent:
- tests/specify_cli/test_locked_frontmatter_writers.py
- tests/specify_cli/test_matrix_writer_locks.py
execution_mode: code_change
model: claude-sonnet
owned_files:
- src/specify_cli/frontmatter.py
- src/specify_cli/cli/commands/agent/tasks_map_requirements.py
- src/specify_cli/cli/commands/agent/mission_finalize.py
- src/specify_cli/cli/commands/agent/mission_finalize_bootstrap.py
- src/specify_cli/cli/commands/agent/mission_finalize_commit.py
- src/specify_cli/cli/commands/agent/mission_finalize_branch_contract.py
- src/specify_cli/tasks/issue_matrix.py
- src/specify_cli/acceptance/matrix.py
- src/specify_cli/cli/commands/agent/issue_verdict.py
- src/specify_cli/task_metadata_validation.py
- src/specify_cli/lanes/implement_support.py
- src/specify_cli/migration/backfill_ownership.py
- src/specify_cli/migration/strip_frontmatter.py
- src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py
- tests/specify_cli/test_locked_frontmatter_writers.py
- tests/specify_cli/test_matrix_writer_locks.py
tags: []
tracker_refs: []
---
# Work Package Prompt: WP04 – Frontmatter, finalize and matrix writers take the lock

## Objective

map-requirements, the finalize flush, the finalize write-scope restore, the issue-matrix scaffold, the matrix helpers and the remaining frontmatter writers read and write inside one Mission-lock hold. `locked_update_frontmatter(wp_path, mutate, *, feature_dir, ...)` is the helper. The finalize restore is a compare-and-swap on every branch.

## Independent test

`tests/specify_cli/test_locked_frontmatter_writers.py` (US2): map-requirements overlap; finalize vs a concurrent map-requirements ref and a concurrent body note; the compare-and-swap restore for rewrite, unlink and `restore_meta_text`. `tests/specify_cli/test_matrix_writer_locks.py` (US3): the scaffold vs a recorded verdict; the two-worktree matrix writers on the bare-directory coordination fixture.

## Subtasks

- **T015**: Red-first: map-requirements overlap (FR-002); finalize erasing a concurrent frontmatter field and body note (FR-003, A9); the scaffold overwriting a verdict (FR-004); matrix helpers on the bare-directory coordination fixture, identifying key vs root as the cause (FR-005, A9)
- **T016**: `locked_update_frontmatter` in `frontmatter.py`, preserving the body byte for byte; map-requirements uses it (re-read refs under the lock)
- **T017**: Finalize flush applies its field delta to the freshly read frontmatter and body under the lock; the write-scope restore (rewrite and unlink branches) and `restore_meta_text` become compare-and-swap inside the lock and report kept files (A8); `mission_finalize_branch_contract.py` meta writes use `locked_update_meta`
- **T018**: `scaffold_issue_matrix` exists-check and write in one hold; `acceptance/matrix.py` (re-read helper and `locked_acceptance_verdict_guard`, A13) and `issue_verdict.py` lock through `mission_write_lock` keyed via WP01
- **T019**: Other frontmatter and `tasks.md` writers: `task_metadata_validation.py` (`validate-tasks` repair), `lanes/implement_support.py` `update_fields`, the frontmatter migrations (`backfill_ownership`, `strip_frontmatter`, `m_2_0_6_consistency_sweep` including its `tasks.md` write), and the finalize `tasks.md` write in `mission_finalize_bootstrap.py` (A10); the lane mirror in `emit.py` stays as it is (runtime-locked; WP15 recognizes it)
- **T058**: CLI-entry overlap test: two overlapping `spec-kitty agent tasks map-requirements` invocations (via the Typer runner on two threads with an injected pause) keep both refs (FR-002, US2 through the CLI)

## Notes and risks

`review/prompt_metadata.write_frontmatter` is out of scope (C-007): it writes a per-invocation temporary file. Finalize keeps a long in-memory window, so apply deltas rather than writing back the model.

## Dependencies

WP02

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
