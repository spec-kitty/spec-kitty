---
work_package_id: WP02
title: Locked meta.json helper, setters and accept restamps
dependencies:
- WP13
requirement_refs:
- FR-001
- FR-005
- FR-020
- NFR-001
- NFR-002
- NFR-005
- C-006
planning_base_branch: issue-5883-mission-writer-followups
merge_target_branch: issue-5883-mission-writer-followups
branch_strategy: Planning artifacts for this mission were generated on issue-5883-mission-writer-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5883-mission-writer-followups unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - Writers
history:
- at: '2026-10-08T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/mission_metadata.py
create_intent:
- tests/specify_cli/test_locked_meta_writers.py
execution_mode: code_change
model: claude-sonnet
owned_files:
- src/specify_cli/mission_metadata.py
- src/specify_cli/acceptance/__init__.py
- src/specify_cli/core/mission_creation_meta.py
- src/specify_cli/tracker/origin.py
- src/specify_cli/cli/commands/mission_type.py
- src/specify_cli/cli/commands/_coordination_doctor.py
- src/specify_cli/lanes/implement_support.py
- tests/specify_cli/test_locked_meta_writers.py
- tests/architectural/dead_symbol_allowlist.yaml
tags: []
tracker_refs: []
---
# Work Package Prompt: WP02 – Locked meta.json helper, setters and accept restamps

## Objective

Every `mission_metadata` read-modify-write and accept's direct restamp writes run through `locked_update_meta(feature_dir, mutate, ...)`: the lock is taken, `meta.json` is re-read under it, `mutate` is applied, and the result is written atomically. The acceptance verdict guard locks through `mission_write_lock`. The three dead setters are removed.

## Independent test

`tests/specify_cli/test_locked_meta_writers.py`: for each setter family a deterministic two-thread overlap keeps both writes (US1); nested use under `ensure_vcs_locked`; the bounded wait fails with `STATUS_LOCK_HELD` (NFR-002); the uncontended path adds one lock acquisition and no subprocess.

## Subtasks

- **T006**: Red-first: two overlapping `meta.json` writers (for example `record_acceptance` vs `set_target_branch`, `set_origin_ticket` vs `record_discard`) lose a write today (US1)
- **T007**: `locked_update_meta(feature_dir, mutate, *, repo_root=None, timeout=BOUNDED)` in `mission_metadata.py`; every setter (`record_acceptance`, `record_discard`, `flatten_coordination_metadata`, `clear_merge_metadata`, `set_target_branch`, `set_origin_ticket`, `set_documentation_state`, `set_vcs_lock`) uses it; `restore_meta_text` gets a compare-and-swap variant for WP04 (A8)
- **T008**: Remove `set_change_mode`, `clear_coordination_metadata` and `set_purpose_summary` with their `dead_symbol_allowlist.yaml` entries and tests
- **T009**: acceptance: the planning-only `record_acceptance` call and the direct restamp writes go through the helper (the verdict guard in `acceptance/matrix.py` is rekeyed in WP04, A13)
- **T010**: Callers: `core/mission_creation_meta.py`, `tracker/origin.py`, `cli/commands/mission_type.py` (discard, flatten, reopen), `_coordination_doctor.py`, `lanes/implement_support.py` (`set_vcs_lock` under `ensure_vcs_locked`, unbounded wait unchanged)

## Notes and risks

`mutate` is a pure function that is only called, never stored, returned or assigned (gate Rule 2). Watch for nesting: `ensure_vcs_locked` already holds the same per-thread re-entrant lock. A subprocess cannot re-enter its parent's hold; document that edge case if one exists. Edit `dead_symbol_allowlist.yaml` wherever it lives (`grep -rn set_change_mode tests`). Handoff: `implement_support.py` is edited again by WP04 (`update_fields`); `acceptance/__init__.py` and `cli/commands/mission_type.py` are edited again by WP10 (wording).

## Dependencies

WP13

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
