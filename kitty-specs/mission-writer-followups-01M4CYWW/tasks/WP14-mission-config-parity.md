---
work_package_id: WP14
title: Pack mission.yaml equals the copy the CLI runs
dependencies:
- WP06
requirement_refs:
- FR-023
- NFR-005
- C-006
planning_base_branch: issue-5883-mission-writer-followups
merge_target_branch: issue-5883-mission-writer-followups
branch_strategy: Planning artifacts for this mission were generated on issue-5883-mission-writer-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5883-mission-writer-followups unless the human explicitly redirects the landing branch.
subtasks:
- T028
- T055
phase: Phase 3 - Runtime
history:
- at: '2026-10-08T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: packs/built-in/missions/
create_intent:
- tests/specify_cli/missions/test_pack_mission_config_parity.py
execution_mode: code_change
model: claude-sonnet
owned_files:
- src/specify_cli/missions/software-dev/mission.yaml
- src/specify_cli/missions/documentation/mission.yaml
- src/specify_cli/missions/research/mission.yaml
- src/specify_cli/missions/plan/mission.yaml
- packs/built-in/missions/software-dev/mission.yaml
- packs/built-in/missions/documentation/mission.yaml
- packs/built-in/missions/research/mission.yaml
- packs/built-in/missions/plan/mission.yaml
- packs/built-in/pack-manifest.yaml
- packs/built-in/*.graph.yaml
- tests/charter/test_compiler_charter_yaml.py
- tests/charter/fixtures/**
- tests/specify_cli/missions/test_pack_mission_config_parity.py
tags: []
tracker_refs: []
---
# Work Package Prompt: WP14 – Pack mission.yaml equals the copy the CLI runs

## Objective

Each built-in type's pack `mission.yaml` is byte-equal to the src copy the CLI reads today (operator ruling, FR-023). The unread `task_types` blocks and the documentation `deliverables: docs/output/` are dropped from the pack. Wording-only fixes ("feature" to "mission") land in both copies. The charter-bundle goldens that embed the pack `mission.yaml` are regenerated.

## Independent test

`tests/specify_cli/missions/test_pack_mission_config_parity.py`: pack and src `mission.yaml` are byte-equal for all four types while the src copy exists (SC-009).

## Subtasks

- **T028**: Red-first: the parity test fails on today's four pairs. Then confirm that no reader of the pack copy (`charter/offering/missions/repository.py`, `charter/activation/*`, `dossier/manifest.py`, the neutrality lint) consumes `task_types` or `paths.deliverables`; if one does, stop and raise an owner decision instead of dropping the key. Make the copies equal, with the wording fixes in both
- **T055**: Regenerate the charter-bundle goldens the compiler embeds (`compiler.py:1992-2005`) and run `spec-kitty doctrine regenerate-graph`; record every changed golden in the Activity Log, because the PR calls them out

## Notes and risks

`templates/` and the Python modules are out of scope (C-008). Handoff: WP17 and WP11 edit `pack-manifest.yaml` and the graph files again.

## Dependencies

WP06

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
