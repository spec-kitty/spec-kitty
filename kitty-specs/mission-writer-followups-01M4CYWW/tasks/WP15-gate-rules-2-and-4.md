---
work_package_id: WP15
title: 'Mission write discipline gate: Rules 2 and 4'
dependencies:
- WP08
requirement_refs:
- FR-006
- FR-019
- NFR-004
- NFR-005
- C-006
planning_base_branch: issue-5883-mission-writer-followups
merge_target_branch: issue-5883-mission-writer-followups
branch_strategy: Planning artifacts for this mission were generated on issue-5883-mission-writer-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5883-mission-writer-followups unless the human explicitly redirects the landing branch.
subtasks:
- T035
- T037
phase: Phase 4 - Gate
history:
- at: '2026-10-08T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/test_mission_write_discipline.py
create_intent: []
execution_mode: code_change
model: claude-sonnet
owned_files:
- tests/architectural/test_mission_write_discipline.py
tags: []
tracker_refs: []
---
# Work Package Prompt: WP15 – Mission write discipline gate: Rules 2 and 4

## Objective

Rule 2 treats every non-call reference to the callable parameter as an escape. New Rule 4 keeps `meta.json`, `tasks/WP*.md` and `tasks.md` writes inside a lock region or a registered locked helper, with region recognition that is structural, not name-based.

## Independent test

`tests/architectural/test_mission_write_discipline.py`: a synthetic offender, a near-miss negative and a self-mutation proof for Rules 2 and 4 (NFR-004); both rules pass on the real tree with an empty allowlist.

## Subtasks

- **T035**: Rule 2 (FR-006, A11): any non-call-func reference to the parameter, including passing it as an argument or keyword or capturing it in a nested def or lambda, is an escape; an unresolvable callee fails closed
- **T037**: Rule 4 (FR-019, A5). Regions: a lexical lock `with`, `ExitStack.enter_context(<lock cm>)`, `__enter__`..`__exit__`, a `with` on a name assigned from a lock cm, and `locked_acceptance_verdict_guard`. A sink in function F is accepted when F is a registered locked helper or every same-module call site of F sits in a region. Unresolvable cross-module callers fail closed. `write_frontmatter`/`update_fields` are sinks only when the target resolves to `tasks/WP*.md` or `tasks.md`, so `review/prompt_metadata.py`'s temporary file is a near-miss (C-007). No name-based exemptions; the merge-driver exclusion applies

## Notes and risks

Fix real-tree hits in the owning code, never by allowlisting. When a hit sits in a file this WP does not own, make the minimal fix, list the file in the Activity Log as a handoff, and name it in the review request. Rule 4's cross-call-site region analysis is the heavy part: keep each helper ≤ 15 complexity, with its own tests.

## Dependencies

WP08

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
