---
work_package_id: WP02
title: Decisions boundary presentation
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
planning_base_branch: fix/4642-corrupt-state-file-guards
merge_target_branch: fix/4642-corrupt-state-file-guards
branch_strategy: Planning artifacts for this mission were generated on fix/4642-corrupt-state-file-guards. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/4642-corrupt-state-file-guards unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-corrupt-state-file-guards-01M2VZS0
base_commit: 75df5a78eff7d7b9b961e705d2d0103f5d883416
created_at: '2026-09-19T05:27:15.389509+00:00'
subtasks:
- T006
- T007
- T008
- T009
history:
- by: orchestrator
  at: '2026-09-19T05:00:00Z'
  note: 'Authored from IC-2 (mission corrupt-state-file-guards, #4642).'
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/decision.py
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/decision.py
- tests/specify_cli/cli/commands/test_decision.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile via `/ad-hoc-profile-load` (profile: `python-pedro`, role: `implementer`). Adopt its identity, boundaries, and TDD discipline.

## Objective

Present `DecisionIndexReadError` (from WP01) as a single clean, operator-readable error at the `decision.py` command boundary for **all six** subcommands — `verify`, `resolve`, `open`, `list`, `defer`, `cancel` — so a corrupt `decisions/index.json` never escapes as a raw traceback.

## Context

- WP01 makes `load_index` raise `DecisionIndexReadError`. Every subcommand reaches `load_index` (verify → `verify()`; resolve/open/defer/cancel → service; list → directly).
- The boundary already has the right shape for the business taxonomy: `_handle_decision_error` (`decision.py:183`) catches `DecisionError`/`ActionContextError` and emits structured JSON `{error, code, details}` + `Exit(1)`. Mirror it.
- `--json` payloads must remain valid JSON (orchestrator-api consumers special-case decision error codes).

## Subtasks

### T006 — Red-first entry-point regression tests (write FIRST, must be RED)
In `tests/specify_cli/cli/commands/test_decision.py`, add `@pytest.mark.regression` tests pinned to #4642 that drive the REAL commands via typer `CliRunner` against a mission whose `decisions/index.json` is corrupt:
- `spec-kitty agent decision verify --mission <slug>` — malformed JSON, non-UTF-8, wrong-shape (3 cases)
- `spec-kitty agent decision resolve <id> --mission <slug> --final-answer a --rationale r --resolved-by z` — at least the malformed-JSON case
Assertions per case: `result.exit_code == 1`; `result.exception is None` or a `SystemExit`/`typer.Exit` (no raw traceback); output names the corrupt file + carries the `run: spec-kitty doctor` hint; output contains no `"Traceback (most recent call last)"`; under `--json`, the error payload parses as JSON.
Confirm RED first (raw `JSONDecodeError`/`UnicodeDecodeError`/`ValidationError` today).

### T007 — `_handle_index_read_error(exc, json_output)`
Add a handler mirroring `_handle_decision_error`: emit structured `{code: "DECISION_INDEX_UNREADABLE", error: <message>, details: {...}}` to stderr (and valid JSON under `--json`), include the fail-closed + doctor-hint text carried by the error, then `raise typer.Exit(1)`.

### T008 — Catch arms on all six subcommands
Co-located with each existing `except DecisionError` / `except ActionContextError`, add `except DecisionIndexReadError as exc: _handle_index_read_error(exc, json_output)` to `cmd_verify`, `cmd_resolve`, `cmd_open`, `cmd_list`, `cmd_defer`, `cmd_cancel`. Import `DecisionIndexReadError` from `specify_cli.decisions`.

### T009 — Confirm green
Run the regression tests; all pass (were RED before WP01+this).

## Branch Strategy

Planning/base branch and final merge target: `fix/4642-corrupt-state-file-guards`. Enter the workspace `spec-kitty implement WP02` resolves from `lanes.json`.

## Test Strategy (red-first, ADR 2026-07-17-1)

```
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_decision.py -q
```

## Definition of Done

- [ ] All six decision subcommands present `DecisionIndexReadError` cleanly; no traceback.
- [ ] `--json` error payload parses.
- [ ] `@pytest.mark.regression` #4642 tests green (were RED before the fix).
- [ ] ruff + mypy clean; complexity ≤ 15; no new suppressions.

## Risks / Reviewer guidance

- WP01 must be merged/available first (dependency). If `DecisionIndexReadError` import fails, the reader half is not in place.
- Do not swallow `DecisionError` semantics — the new arm is additive, alongside the existing ones.
