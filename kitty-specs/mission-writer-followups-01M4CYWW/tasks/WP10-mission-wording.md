---
work_package_id: WP10
title: Operator-facing text and generated commits say mission
dependencies:
- WP03
- WP04
requirement_refs:
- FR-012
- FR-013
- FR-014
- NFR-005
- C-006
planning_base_branch: issue-5883-mission-writer-followups
merge_target_branch: issue-5883-mission-writer-followups
branch_strategy: Planning artifacts for this mission were generated on issue-5883-mission-writer-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5883-mission-writer-followups unless the human explicitly redirects the landing branch.
subtasks:
- T044
- T045
- T046
- T047
- T061
phase: Phase 5 - Wording
history:
- at: '2026-10-08T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/mission_finalize_planning_pin.py
create_intent:
- tests/specify_cli/test_no_for_feature_operator_text.py
execution_mode: code_change
model: claude-sonnet
owned_files:
- src/specify_cli/cli/commands/agent/mission_finalize_planning_pin.py
- src/specify_cli/cli/commands/agent/mission_setup_plan.py
- src/specify_cli/core/mission_creation_commit.py
- src/specify_cli/status/uninitialized_hint.py
- src/specify_cli/task_utils/support.py
- src/specify_cli/acceptance/__init__.py
- src/specify_cli/plan_validation.py
- src/specify_cli/cli/commands/validate_tasks.py
- src/specify_cli/cli/commands/validate_encoding.py
- src/specify_cli/cli/commands/agent/mission_branch_context.py
- src/specify_cli/lanes/consolidation.py
- src/specify_cli/cli/commands/implement.py
- src/specify_cli/cli/commands/implement_phases.py
- src/specify_cli/core/mission_creation_identity.py
- src/specify_cli/cli/helpers.py
- src/specify_cli/cli/commands/mission_type.py
- commitlint.config.cjs
- tests/specify_cli/test_no_for_feature_operator_text.py
- tests/specify_cli/test_canonical_acceptance.py
- tests/core/golden/**
- tests/tasks/conftest.py
- src/specify_cli/verify_enhanced.py
- tests/core/test_mission_creation_probe_order.py
- tests/core/test_mission_creation_fanout_commit_boundary.py
- tests/specify_cli/cli/commands/agent/test_finalize_tasks_commit_surface.py
- tests/specify_cli/cli/commands/agent/test_sc6_planning_placement_e2e.py
- tests/cli/commands/test_agent_mission_commit_to_branch.py
tags: []
tracker_refs: []
---
# Work Package Prompt: WP10 – Operator-facing text and generated commits say mission

## Objective

The five planning commit builders and the operator-facing CLI errors say "mission". The finalize drift check accepts both the new and the legacy subjects. An AST scan keeps "for feature" out of operator text. commitlint covers every planning subject for both words.

## Independent test

`tests/specify_cli/test_no_for_feature_operator_text.py` (FR-014, C9): scans every non-docstring string constant under `src/specify_cli` for "for feature" or a leading "Feature:"; a synthetic offender per construction form (f-string, concatenation, variable).

## Subtasks

- **T044**: Red-first: the FR-014 scan fails on today's tree, and so does the drift check on a legacy-subject Mission. The scan gets two structural exemptions, each with a test: the legacy-subject constant the drift check must keep (a module-level constant named for that purpose), and hosted-only modules (`tracker/saas_*`, C-007)
- **T045**: Commit builders: finalize planning pin, `mission_setup_plan` (spec/plan setup, gap analysis, generator config), `core/mission_creation_commit`; the drift check accepts the old and new subjects (FR-013)
- **T046**: CLI errors from R8 and C9; `FEATURE_CONTEXT_UNRESOLVED` stays (machine contract) and is filed as a follow-up
- **T047**: commitlint: the planning-subject rule covers the scaffold, gap-analysis, generator-config and origin-ticket-binding subjects for both words; update tests and goldens that assert the old text (R8, C7)
- **T061**: CLI-entry test: `spec-kitty agent mission finalize-tasks` on a fixture Mission writes a commit whose subject says "for mission" (FR-012)

## Notes and risks

Golden and fixture files that assert the old subjects (R8, C7 wording pins) change in this WP. Find them with `grep -rn "for feature" tests`. `src/specify_cli/verify_enhanced.py` (`"   Feature: "`) is in scope. Handoff: `acceptance/__init__.py` and `mission_type.py` were last edited in WP02 or WP03, `mission_setup_plan.py` in WP03, and `implement_phases.py` in WP13. `tests/next/test_next_command_integration.py:556` asserts the old "Canonical status not found for feature" text but is owned by WP06; update that one assertion here and record the handoff in the Activity Log.

## Dependencies

WP03, WP04

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
