---
work_package_id: WP11
title: The glossary defines topic branch, Mission and Mission Run consistently
dependencies:
- WP17
requirement_refs:
- FR-021
- NFR-005
- C-006
planning_base_branch: issue-5883-mission-writer-followups
merge_target_branch: issue-5883-mission-writer-followups
branch_strategy: Planning artifacts for this mission were generated on issue-5883-mission-writer-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5883-mission-writer-followups unless the human explicitly redirects the landing branch.
subtasks:
- T048
- T049
- T050
phase: Phase 5 - Wording
history:
- at: '2026-10-08T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/context/
create_intent: []
execution_mode: code_change
model: claude-sonnet
owned_files:
- docs/context/orchestration.md
- docs/context/execution.md
- docs/context/spec-driven.md
- docs/context/historical-terms.md
- docs/context/glossary-conventions.md
- docs/context/contextive-glossaries.md
- .kittify/traceability/contextive-map.yaml
- .kittify/glossaries/spec_kitty_core.yaml
- packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml
- packs/built-in/pack-manifest.yaml
- src/specify_cli/.contextive/**
- packs/built-in/*.graph.yaml
- tests/architectural/test_no_legacy_terminology.py
tags: []
tracker_refs: []
---
# Work Package Prompt: WP11 – The glossary defines topic branch, Mission and Mission Run consistently

## Objective

topic branch is added, Mission and Mission Run are rewritten, and feature branch becomes an alias of topic branch. All of this is consistent across `docs/context`, the YAML seed, the built-in glossary pack and the regenerated contextive glossaries. The R9 and C11 inconsistencies are fixed.

## Independent test

The glossary parity gates (`test_glossary_pack_parity.py`, `test_glossary_authority_parity.py`, `tests/glossary/test_seed_validation.py`) and `tests/architectural/test_no_legacy_terminology.py`; the regenerate-graph roundtrip.

## Subtasks

- **T048**: Entries: topic branch (new), Mission, Mission Run, feature branch → alias of topic branch, across the four surfaces
- **T049**: Fix the R9 and C11 inconsistencies
- **T050**: Regenerate the contextive glossaries (`scripts/generate_contextive_glossaries.py`) and the graph (`spec-kitty doctrine regenerate-graph`); the `test_no_legacy_terminology` baseline only shrinks

## Notes and risks

If a `docs/context` file named here does not exist, find the real one. This WP has no code-behaviour change, so red-first does not apply beyond the parity gates.

## Dependencies

WP17

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
