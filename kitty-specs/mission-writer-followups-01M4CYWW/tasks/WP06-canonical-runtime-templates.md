---
work_package_id: WP06
title: next reads the pack runtime templates; in-flight runs keep working
dependencies:
- WP05
- WP02
requirement_refs:
- FR-017
- FR-018
- FR-020
- FR-023
- NFR-006
- C-001
- C-004
- C-008
- NFR-005
- C-006
planning_base_branch: issue-5883-mission-writer-followups
merge_target_branch: issue-5883-mission-writer-followups
branch_strategy: Planning artifacts for this mission were generated on issue-5883-mission-writer-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5883-mission-writer-followups unless the human explicitly redirects the landing branch.
subtasks:
- T025
- T026
- T027
- T029
- T059
phase: Phase 3 - Runtime
history:
- at: '2026-10-08T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/runtime_bridge_io.py
create_intent:
- tests/runtime/test_pack_runtime_template_parity.py
- tests/runtime/fixtures/runtime_template_baseline.json
execution_mode: code_change
model: claude-sonnet
owned_files:
- src/runtime/next/runtime_bridge_io.py
- src/runtime/next/runtime_bridge_query.py
- src/specify_cli/mission_loader/command.py
- src/specify_cli/missions/software-dev/mission-runtime.yaml
- src/specify_cli/missions/documentation/mission-runtime.yaml
- src/specify_cli/missions/research/mission-runtime.yaml
- src/specify_cli/missions/plan/mission-runtime.yaml
- packs/built-in/missions/software-dev/mission-runtime.yaml
- packs/built-in/missions/plan/mission-runtime.yaml
- packs/built-in/pack-manifest.yaml
- tests/architectural/test_layer_rules.py
- tests/architectural/_baselines.yaml
- tests/next/test_plan_mission_runtime.py
- tests/contract/test_plan_mission_yaml_validates.py
- tests/specify_cli/missions/test_mission_template_consistency.py
- tests/runtime/test_pack_runtime_template_parity.py
- packs/built-in/*.graph.yaml
- tests/runtime/test_bridge_io.py
- tests/research/test_research_plan_missions_integration.py
- tests/specify_cli/events/test_runtime_moments.py
- tests/specify_cli/test_documentation_template_resolution.py
- tests/specify_cli/orchestrator_api/test_answer_decision.py
- tests/specify_cli/orchestrator_api/test_planning_client_journey.py
- tests/specify_cli/next/test_next_invocation_lifecycle_seam.py
- tests/integration/test_research_runtime_walk.py
- tests/integration/test_documentation_runtime_walk.py
- tests/doctrine/test_shipped_profiles.py
- tests/next/test_next_command_integration.py
- tests/next/test_runtime_bridge_unit.py
- tests/runtime/fixtures/runtime_template_baseline.json
tags: []
tracker_refs: []
---
# Work Package Prompt: WP06 – next reads the pack runtime templates; in-flight runs keep working

## Objective

The runtime resolves built-in runtime templates from `packs/built-in/missions` through `charter.activation.mission_type_profile_repository.builtin_missions_root()`, with the same tier order. The four `src` `mission-runtime.yaml` copies are deleted, and the runtime→specify_cli ledger drops from 23 to 22. Each pack runtime template matches what the CLI runs today (FR-023): software-dev and plan take the src content, while the documentation and research bytes stay unchanged. In-flight runs keep working.

## Independent test

`tests/runtime/test_pack_runtime_template_parity.py`: for each type, the resolved template plans the same step sequence and the same dispatch route per step as the committed baseline fixture recorded from today's resolver (NFR-006, SC-009). The software-dev analyze step is exempt from the start, so WP07 does not have to edit this test. A persisted run whose recorded src path is gone still advances and answers query mode (B1).

## Subtasks

- **T025**: Red-first: record today's resolved template plan per type (step sequence and dispatch route) into the committed fixture `tests/runtime/fixtures/runtime_template_baseline.json` BEFORE any copy is deleted; then show the pack software-dev/plan templates diverge (agent-profile routing widening, plan does not load) and that query mode on a run with a vanished recorded path raises `QueryModeValidationError`
- **T026**: Built-in tier via `builtin_missions_root()`, `PackRootNotFound` failing closed with a named error and a test; `mission_loader/command.py` switches to the same accessor and its `write_meta` goes through `locked_update_meta` (FR-020); both bare `import specify_cli` edges removed; the ledger entry removed, cap 23→22, and the `_baselines.yaml` justification updated (B8)
- **T027**: Reconcile the pack runtime templates per B2: software-dev and plan take the src content; documentation and research stay byte-unchanged. Delete the four src `mission-runtime.yaml` copies and the deprecation banner. Move every test that hard-codes the src runtime path (the owned test list) to the pack path, then run `spec-kitty doctrine regenerate-graph` if the manifest hashes them (B8)
- **T029**: Query mode loads `run_dir/mission_template_frozen.yaml`; the live path is used only for drift (B1); confirm the planner drift-skip keeps an in-flight software-dev run on its frozen order (FR-017)
- **T059**: CLI-entry red test: edit a pack runtime-template fixture (a copied pack root) and show that `spec-kitty next` ignores it today and honours it after the change (FR-018)

## Notes and risks

Only `mission-runtime.yaml` moves (C-008). Before trusting `tests/doctrine/test_doctrine_regenerate_graph_roundtrip.py`, reinstall with `pip install -e .` or `uv sync --frozen` (C13). Handoffs: WP14 does `mission.yaml` parity; WP07 edits `runtime_bridge_query.py`, `runtime_bridge_io.py` and the pack software-dev runtime template again (analyze); WP14, WP17 and WP11 edit `pack-manifest.yaml` and the graph files again.

## Dependencies

WP05, WP02

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
