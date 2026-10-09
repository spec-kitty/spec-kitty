---
work_package_id: WP17
title: Scripted prompt walk gate, ratchet, snapshots and graph
dependencies:
- WP16
requirement_refs:
- FR-022
- C-003
- NFR-005
- C-006
planning_base_branch: issue-5883-mission-writer-followups
merge_target_branch: issue-5883-mission-writer-followups
branch_strategy: Planning artifacts for this mission were generated on issue-5883-mission-writer-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5883-mission-writer-followups unless the human explicitly redirects the landing branch.
subtasks:
- T057
- T043
phase: Phase 5 - Pack
history:
- at: '2026-10-08T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/doctrine/test_software_dev_prompt_walk.py
create_intent:
- tests/doctrine/test_software_dev_prompt_walk.py
execution_mode: code_change
model: claude-sonnet
owned_files:
- tests/doctrine/test_software_dev_prompt_walk.py
- tests/architectural/_builtin_pack_provenance_baseline.yaml
- tests/specify_cli/regression/_twelve_agent_baseline/**
- tests/specify_cli/skills/__snapshots__/**
- packs/built-in/pack-manifest.yaml
- packs/built-in/*.graph.yaml
tags: []
tracker_refs: []
---
# Work Package Prompt: WP17 – Scripted prompt walk gate, ratchet, snapshots and graph

## Objective

SC-008 is enforced by a gate: a scripted walk of the software-dev step prompts and contracts finds 0 refused instructions and 0 non-existent references. The provenance ratchet baseline counts are lowered, the rendered snapshots are regenerated, and the graph is regenerated.

## Independent test

`tests/doctrine/test_software_dev_prompt_walk.py` (C12) extends `test_builtin_cli_command_references.py`:
  1. command paths and each `--option` resolve against Click;
  2. rendered step-contract `command:` values parse;
  3. every "next advances to X" claim matches the runtime order;
  4. consumer paths resolve against a `spec-kitty init` fixture with an explicit placeholder list.

  It covers the CLI-driven implement, review, accept and tasks-finalize prompts.

## Subtasks

- **T057**: Red-first: write the walk gate and show it failing against the pre-cleanup prompt tree (a temporary `git worktree add` at the WP09 base commit, removed afterwards), then passing on the current tree
- **T043**: Lower the ratchet baseline by hand, entry by entry, so the diff only goes down (C8). Regenerate the rendered snapshots with the repository's snapshot update flag. Run `spec-kitty doctrine regenerate-graph`, reinstall, then run the regenerate-graph roundtrip test and `tests/doctrine/test_builtin_cli_command_references.py`

## Notes and risks

Never `git stash`; use a temporary worktree for the pre-fix comparison and remove it. Handoff: WP11 edits `pack-manifest.yaml` and the graph files again.

## Dependencies

WP16

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
