---
work_package_id: WP03
title: Remaining meta.json writers take the lock
dependencies:
- WP02
requirement_refs:
- FR-020
- NFR-002
- NFR-005
- C-006
planning_base_branch: issue-5883-mission-writer-followups
merge_target_branch: issue-5883-mission-writer-followups
branch_strategy: Planning artifacts for this mission were generated on issue-5883-mission-writer-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5883-mission-writer-followups unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
- T014
phase: Phase 2 - Writers
history:
- at: '2026-10-08T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/specify_cli/test_remaining_meta_writers.py
execution_mode: code_change
model: claude-sonnet
owned_files:
- src/specify_cli/doc_analysis/doc_state.py
- src/specify_cli/cli/commands/agent/mission_setup_plan.py
- src/specify_cli/consolidation/phase_teardown.py
- src/specify_cli/consolidation/baseline.py
- src/specify_cli/consolidation/mission_number/bake.py
- src/specify_cli/migration/mission_state.py
- src/specify_cli/migration/runtime_state_cutover.py
- src/specify_cli/upgrade/feature_meta.py
- src/specify_cli/migration/backfill_mission_type.py
- src/specify_cli/migration/backfill_identity.py
- src/specify_cli/migration/backfill_topology.py
- src/specify_cli/upgrade/migrations/m_0_13_8_target_branch.py
- tests/specify_cli/test_remaining_meta_writers.py
tags: []
tracker_refs: []
---
# Work Package Prompt: WP03 – Remaining meta.json writers take the lock

## Objective

Every other read-modify-write of `meta.json` runs through `locked_update_meta`, so gate Rule 4 (WP08) passes on the real tree with no allowlist. This covers the documentation-state writers, consolidation teardown, baseline and mission-number bake, and the migrations and upgrades.

## Independent test

`tests/specify_cli/test_remaining_meta_writers.py`: one overlap test per writer family (documentation state, consolidation, migrations) and a parametrized check that each writer calls the locked helper.

## Subtasks

- **T011**: Red-first per family: a documentation-state writer, a consolidation writer and a migration writer each lose a concurrent locked write today (C-006 part by part)
- **T012**: `doc_analysis/doc_state.py` (`set_audit_metadata`, `set_generators_configured`, `set_iteration_mode`, `set_divio_types_selected`, `write_documentation_state`, `ensure_documentation_state`) and their `mission_setup_plan.py` callers
- **T013**: Consolidation: `phase_teardown` (flatten caller and `_clear_landed_single_branch_mission_branch`), `baseline.record_baseline_merge_commit`/`_stamp_pr_merge_provenance`, `mission_number/bake.py` (the scratch-checkout write locks the scratch Mission's key)
- **T014**: Migrations and upgrades: `migration/mission_state.py`, `runtime_state_cutover.py`, `upgrade/feature_meta.py`, raw meta writes in `backfill_mission_type.py`, `backfill_identity.py` (including the `open(meta_path, "w")`+`json.dump` form), `backfill_topology.py`, `m_0_13_8_target_branch.py`

## Notes and risks

Migrations get no exemption (plan D5); they write through the helper. The merge driver (`consolidation/drivers.py`) is out of scope: it writes the temporary path git hands it, and WP08 excludes it structurally. Re-derive line numbers (lens A10). Handoff: `mission_setup_plan.py` is edited again by WP10 (commit subjects).

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
