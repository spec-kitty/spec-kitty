---
work_package_id: WP07
title: next issues a guarded analyze step between tasks and implement
dependencies:
- WP14
requirement_refs:
- FR-016
- FR-017
- C-001
- C-004
- NFR-005
- C-006
planning_base_branch: issue-5883-mission-writer-followups
merge_target_branch: issue-5883-mission-writer-followups
branch_strategy: Planning artifacts for this mission were generated on issue-5883-mission-writer-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5883-mission-writer-followups unless the human explicitly redirects the landing branch.
subtasks:
- T030
- T031
- T032
- T033
- T056
- T060
phase: Phase 3 - Runtime
history:
- at: '2026-10-08T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/runtime_bridge_cores.py
create_intent:
- tests/runtime/test_analyze_step.py
execution_mode: code_change
model: claude-sonnet
owned_files:
- src/runtime/next/runtime_bridge.py
- src/runtime/next/runtime_bridge_query.py
- src/runtime/next/runtime_bridge_cores.py
- src/runtime/next/decision.py
- src/specify_cli/cli/commands/next_cmd.py
- src/specify_cli/orchestrator_api/decision_verbs.py
- packs/built-in/missions/software-dev/mission-runtime.yaml
- tests/runtime/test_analyze_step.py
- src/runtime/next/runtime_bridge_io.py
- src/runtime/next/runtime_bridge_composition.py
- tests/specify_cli/next/test_workflow_software_dev_default_is_byte_stable.py
- tests/specify_cli/next/test_runtime_bridge_composition.py
- tests/runtime/test_bridge_composition.py
- tests/runtime/test_composition_advance_alignment.py
- tests/runtime/test_runtime_seam.py
tags: []
tracker_refs: []
---
# Work Package Prompt: WP07 – next issues a guarded analyze step between tasks and implement

## Objective

The software-dev runtime order becomes `discovery → specify → plan → tasks → analyze → implement → review → accept`. `analyze` completes only while the analysis report is current. Otherwise it is re-issued with `error_code` `ANALYSIS_REPORT_MISSING`, `ANALYSIS_REPORT_STALE` or `ANALYSIS_CURRENCY_UNAVAILABLE`, and `guard_failures` naming each stale input. The finalized-board override and query mode apply the same check before they hand out implement.

## Independent test

`tests/runtime/test_analyze_step.py` (US7): missing, stale and current reports on the analyze step; the finalized-board override with hand-run specify/plan/tasks in both decide and query modes (B3); the orchestrator-api `decide_next` path; a missing callable failing closed; error-code precedence; `_state_to_action("analyze")` and `_build_prompt_or_error` resolving; `_with_guard_failure_paths` rendering stale inputs; an in-flight frozen run keeping its order.

## Subtasks

- **T030**: Red-first: today `next` after tasks returns implement while `agent action implement` refuses on the missing analysis report; the finalized-board override skips analyze (B3)
- **T031**: Add the analyze step to the pack software-dev runtime template (analyze stays `in_action_sequence: false`, C6)
- **T032**: Inject the analysis-currency callable inside the shared `next_cmd.decide_next` wrapper and route `orchestrator_api/decision_verbs.py` through it (B4); the bridge computes the verdict into `status_facts` only for `analyze` or the board override, so the cores module stays pure (B5)
- **T033**: `analyze` guard in `_evaluate_software_dev_guards`, error codes in `decision.py`, the precedence rule (a prompt-resolution failure wins), and the board override in decide and query modes (B3, B5)
- **T056**: Update the tests that pin the software-dev tasks→implement order and go red; check whether the `runtime_bridge_composition.py` tasks→implement advance can skip analyze, and add a red test and a fix if it can. Record every other test that turns red, and its fix, in the Activity Log
- **T060**: CLI-entry test: `spec-kitty next --json` after tasks issues analyze with `ANALYSIS_REPORT_MISSING`; after `record-analysis`, `next --result success` advances to implement (SC-005, US7)

## Notes and risks

The runtime gets the callable injected; it imports nothing new from `specify_cli` (C-001). The callable wraps `analysis_report.check_analysis_report_current`. `status_facts` is built in `runtime_bridge_io.py`, and B5 puts the verdict there. The WP06 parity test already exempts the analyze step.

## Dependencies

WP14

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
