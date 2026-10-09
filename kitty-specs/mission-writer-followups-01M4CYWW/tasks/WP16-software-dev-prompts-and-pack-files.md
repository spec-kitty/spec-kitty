---
work_package_id: WP16
title: Other software-dev prompts and pack files
dependencies:
- WP09
requirement_refs:
- FR-022
- C-003
- NFR-005
- C-006
planning_base_branch: issue-5883-mission-writer-followups
merge_target_branch: issue-5883-mission-writer-followups
branch_strategy: Planning artifacts for this mission were generated on issue-5883-mission-writer-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5883-mission-writer-followups unless the human explicitly redirects the landing branch.
subtasks:
- T041
- T042
phase: Phase 5 - Pack
history:
- at: '2026-10-08T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: packs/built-in/missions/mission-steps/software-dev/
create_intent:
- tests/prompts/test_software_dev_prompt_sections.py
execution_mode: code_change
model: claude-sonnet
owned_files:
- packs/built-in/missions/mission-steps/software-dev/analyze/**
- packs/built-in/missions/mission-steps/software-dev/accept/**
- packs/built-in/missions/mission-steps/software-dev/implement/**
- packs/built-in/missions/mission-steps/software-dev/review/**
- packs/built-in/missions/mission-steps/software-dev/plan/**
- packs/built-in/missions/mission-steps/software-dev/specify/**
- packs/built-in/missions/mission-steps/software-dev/charter/**
- packs/built-in/missions/mission-steps/software-dev/research/**
- packs/built-in/missions/mission-steps/software-dev/tasks/prompt.md
- packs/built-in/missions/mission-steps/software-dev/tasks-outline/prompt.md
- packs/built-in/missions/mission-steps/software-dev/tasks-packages/prompt.md
- packs/built-in/missions/software-dev/README.md
- packs/built-in/missions/software-dev/expected-artifacts.yaml
- packs/built-in/missions/software-dev/governance-profile.yaml
- packs/built-in/missions/software-dev/templates/**
- packs/built-in/missions/software-dev/actions/**
- packs/built-in/missions/README.md
- tests/prompts/test_prompt_fragment_rendering.py
- tests/doctrine/missions/test_mission_steps_layout.py
- tests/specify_cli/cli/commands/test_analyze_surface_agreement.py
- tests/dossier/test_manifest_guard_parity.py
- tests/prompts/test_software_dev_prompt_sections.py
- packs/built-in/pack-manifest.yaml
- packs/built-in/*.graph.yaml
tags: []
tracker_refs: []
---
# Work Package Prompt: WP16 – Other software-dev prompts and pack files

## Objective

The analyze, accept, implement, review, plan and specify prompts, the README files, `expected-artifacts.yaml`, the governance profile and the analyze `step.yaml` describe what the CLI does: the R7 items plus C3, C4, C5 and C10.

## Independent test

`tests/prompts/test_software_dev_prompt_sections.py`: section-scoped asserts for each fixed item. These cover the accept worktree root, the implement analysis gate and its absence of retired paths, the analyze staleness rule and recovery recipe, `--mission` on `next` and `move-task`, and the "every command that accepts `--mission`" wording.

## Subtasks

- **T041**: Red-first, then the prompts: the analyze, accept, implement, review, plan and specify prompts get the R7 items plus C3 (`--mission` boilerplate), C4, C5 and C10 (the recovery recipe outside the checkout). **Scope extension (orchestrator, WP09-review handoff):** C3's `--mission` boilerplate reword applies to ALL NINE prompts that carry the "pass `--mission` to every command" wording — the six above PLUS the three tasks-family prompts now in owned_files (`tasks/prompt.md:58`, `tasks-outline/prompt.md:34`, `tasks-packages/prompt.md:20`). Reword each to "every command that accepts `--mission`"; `test_has_feature_flag_guidance` must stay green (the reworded line still contains `--mission`).
- **T042**: Pack files: `software-dev/README.md`, `missions/README.md`, `expected-artifacts.yaml` (retired tasks_* ids; the analysis report on implement), `governance-profile.yaml`, and `analyze/step.yaml`, which depends on tasks; update the pinning tests (C7)

## Notes and risks

The specify prompt change requires regenerating the rendered snapshots; WP17 owns those and regenerates them. Do not raise any provenance ratchet count (C8).

## Dependencies

WP09

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
