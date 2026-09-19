---
work_package_id: WP03
title: next catches corrupt-meta at the real escape site
dependencies: []
requirement_refs:
- FR-001
- FR-004
- FR-005
planning_base_branch: fix/4642-corrupt-state-file-guards
merge_target_branch: fix/4642-corrupt-state-file-guards
branch_strategy: Planning artifacts for this mission were generated on fix/4642-corrupt-state-file-guards. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/4642-corrupt-state-file-guards unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-corrupt-state-file-guards-01M2VZS0
base_commit: 81b4cce3c194ce4d16df7b23a8ff359c84b7e514
created_at: '2026-09-19T05:08:38.768277+00:00'
subtasks:
- T010
- T011
- T012
- T013
history:
- by: orchestrator
  at: '2026-09-19T05:00:00Z'
  note: 'Authored from IC-3 (mission corrupt-state-file-guards, #4642).'
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/next_cmd.py
create_intent:
- tests/specify_cli/next/test_next_meta_corruption.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/next_cmd.py
- tests/specify_cli/next/test_next_meta_corruption.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile via `/ad-hoc-profile-load` (profile: `python-pedro`, role: `implementer`). Adopt its identity, boundaries, and TDD discipline.

## Objective

Make `spec-kitty next` present `MissionMetaReadError` as a clean fail-closed error on a corrupt `meta.json`, instead of crashing with an uncaught traceback. `next` is the central agent control loop, so this is the highest-impact arm of #4642.

## Context — CRITICAL correction to the issue's suggested fix

The issue and a naive reading suggest adding `MissionMetaReadError` to the `next_cmd.py:215` except-list. **That is the WRONG location and will NOT catch the crash.** Verified on current main by three independent traces:
- The `next_cmd.py:195-217` try/except only wraps `_resolve_mission_slug`, which resolves the mission *directory* (`PRIMARY_METADATA.read_dir`) and never parses `meta.json` content.
- The corrupt-meta parse escapes **downstream**, via `query_current_state → runtime_bridge → load_meta_fail_closed`, from the UNWRAPPED calls: `_run_query_mode(...)` (~`next_cmd.py:232`) and `decide_next(...)` (~`next_cmd.py:252`).
- `MissionMetaReadError` subclasses `RuntimeError` (not `ValueError`), so it slips past the existing `except ValueError` arm.

So the catch MUST wrap the query-mode / `decide_next` call sites, using the **exact** `MissionMetaReadError` type (NOT a broad `except RuntimeError` — that would swallow the unrelated owned-checkout `RuntimeError`s at ~L314/324).

## Subtasks

### T010 — Red-first entry-point regression test (write FIRST, must be RED)
Create `tests/specify_cli/next/test_next_meta_corruption.py` with `@pytest.mark.regression` pinned to #4642, driving the REAL `spec-kitty next --mission <slug>` via typer `CliRunner` against a mission whose `meta.json` is corrupt:
- malformed JSON and non-UTF-8 byte (2 cases), plus a `--json` case.
Assertions: `result.exit_code == 1`; `result.exception is None` or `SystemExit`/`typer.Exit`; output names the corrupt file + `run: spec-kitty doctor` hint; no `"Traceback (most recent call last)"`; `--json` payload parses.
Confirm RED first (uncaught `MissionMetaReadError` traceback today).

### T011 — `_emit_meta_read_error(exc, json_output)`
Add a small emitter near `_emit_internal_resolution_error` (`next_cmd.py:582`) honoring the dual `--json`/plain output contract: print the fail-closed message (already carried by `MissionMetaReadError`) + doctor hint; under `--json` emit a valid JSON error payload.

### T012 — Catch at the real escape site
Wrap the query-mode path (`_run_query_mode(...)`, ~L232) and the `decide_next(...)` call (~L252) so an escaping `MissionMetaReadError` is caught with an **exact** `except MissionMetaReadError as exc:` → `_emit_meta_read_error(exc, json_output)` + `raise typer.Exit(1) from exc`. Import `MissionMetaReadError` from `specify_cli.core.paths`. Keep the wrap tight; do not catch broad `RuntimeError`.

### T013 — Confirm green + no sibling regression
Regression test passes. Confirm the graceful siblings (`accept`, `review`, `mission list`, `agent status show`, `materialize`) still behave as before and `next` happy path is unaffected.

## Branch Strategy

Planning/base branch and final merge target: `fix/4642-corrupt-state-file-guards`. Enter the workspace `spec-kitty implement WP03` resolves from `lanes.json`.

## Test Strategy (red-first, ADR 2026-07-17-1)

```
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/next/test_next_meta_corruption.py -q
```

## Definition of Done

- [ ] `next` presents `MissionMetaReadError` cleanly (exit 1, no traceback) on corrupt meta.json (malformed + non-UTF-8).
- [ ] Catch is the exact type, wrapping the query-mode/`decide_next` calls — NOT the `:215` slug try, NOT broad `RuntimeError`.
- [ ] `--json` payload parses; message carries doctor hint.
- [ ] `@pytest.mark.regression` #4642 test green (was RED before the fix).
- [ ] ruff + mypy clean; complexity ≤ 15; no new suppressions.

## Risks / Reviewer guidance

- The escape site is the crux: verify the test is RED against the pre-fix code specifically because the catch is at query-mode/`decide_next`, not slug resolution.
- Do not broaden to `except RuntimeError`.
