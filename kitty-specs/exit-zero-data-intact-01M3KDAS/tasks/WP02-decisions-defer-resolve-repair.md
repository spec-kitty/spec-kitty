---
work_package_id: WP02
title: Decisions survive defer-then-resolve and repair (#4919)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: claude/milestone-11-research-0rnnr4
merge_target_branch: claude/milestone-11-research-0rnnr4
branch_strategy: Planning artifacts for this mission were generated on claude/milestone-11-research-0rnnr4. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/milestone-11-research-0rnnr4 unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
- T011
phase: Phase 2 - Silent-loss fixes
history:
- at: '2026-09-28T09:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/decisions/
create_intent:
- tests/decisions/test_defer_resolve_repair_4919.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/decisions/index_fold.py
- src/specify_cli/decisions/service.py
- src/specify_cli/cli/commands/_decisions_doctor.py
- src/specify_cli/cli/commands/doctor.py
- tests/decisions/test_defer_resolve_repair_4919.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Decisions survive defer-then-resolve and repair (#4919)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (role `implementer`, agent `claude`) and follow it. Then `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission exit-zero-data-intact-01M3KDAS`). Feedback items are your TODO list.

---

## Objectives & Success Criteria

Issue #4919 (P0): the documented Decision Moment flow `open → defer → resolve` writes two `DecisionPointResolved` events for one decision (`defer` emits a real `DecisionPointResolved` with `terminal_outcome=deferred`; `resolve` emits a second with `terminal_outcome=resolved`). The canonical fold (`index_fold.fold_events`, ~line 219) rejects "more than one DecisionPointResolved", so whenever the index is rebuilt (`doctor decisions --repair` after the index is missing/diverged) the decision is **dropped** and the command exits 0.

Done means (spec FR-001–FR-004, contract `contracts/failure-surface.md`):
- FR-001: after open→defer→resolve and deleting `decisions/index.json`, `doctor decisions --repair` rebuilds the decision as `resolved` with its final answer.
- FR-002: a log already on disk with the (deferred, resolved) pair — in EITHER order — rebuilds as resolved.
- FR-003: the read-only `doctor decisions` reports a genuinely unfoldable decision (e.g. two `DecisionPointOpened`) as a problem (`clean: false`, id in `malformed_folds`) and also flags an index entry whose status differs from the folded status.
- FR-004: `doctor decisions --repair` never removes a decision it cannot fold; it exits **1** and names the decision(s). Under `--json` it emits exactly one JSON document, then exits 1.

## Context & Constraints

- Plan design decision **D3**; research **R1**; data-model "Decision Moment lifecycle" table.
- **Order-independence is mandatory**: the event-log git merge driver (`src/specify_cli/status/event_log_merge.py:62-68`) re-sorts the whole log by `(at, event_id)`, so after a merge the pair may appear resolved-before-deferred. Never rely on file order or on the wall-clock `at` (#4941 class).
- C-004: do NOT change `spec_kitty_events` or the emitter. The fix is in this repo's fold and doctor.
- Existing ratchets that must stay green: `tests/decisions/test_decisions_reconciler.py` (esp. `test_rebuild_index_from_log_omits_malformed_decision_with_no_prior_entry` ~:575 and `test_repair_reports_malformed_fold_instead_of_crashing` ~:499 — the latter calls `open_decision()` / `run_decisions_reconciliation()` directly and asserts `pytest.raises(typer.Exit)` without pinning a code, so exit 1 is compatible). Reuse those function-level fixtures for setup, but the FR-001 repro must ALSO run once through the real CLI (`CliRunner` on the root app).
- Fixtures must use **step_id-origin** decisions; slot_key-origin entries hit the `lossy_attribution` path (`_is_unrecoverable_slot_key_origin`, related #4817) and would misattribute the red.
- The service already refuses resolve-after-resolve and cancel-after-resolve (TERMINAL_CONFLICT, `service.py:~605-624`). Add no new transitions.

## Branch Strategy

- **Strategy**: lanes · **Planning base**: `claude/milestone-11-research-0rnnr4` · **Merge target**: `claude/milestone-11-research-0rnnr4`. Use `spec-kitty implement WP02`; work in the resolved lane workspace.

## Subtasks & Detailed Guidance

### Subtask T006 – Campsite (behaviour-preserving, separate commit)

- Fix the pre-existing mypy `no-any-return` findings in functions you will touch: `src/specify_cli/decisions/service.py:132, 151, 339` and `src/specify_cli/cli/commands/_decisions_doctor.py:154` (narrow with a typed local or `cast` only where the value is provably typed; prefer `bool(...)`/`Path(...)` wraps). Run `uv run --frozen mypy --strict` on both files before and after; commit this step alone ("refactor: campsite typing in decisions service/doctor").

### Subtask T007 – Red-first CLI repros (`tests/decisions/test_defer_resolve_repair_4919.py`)

Mark each `@pytest.mark.regression` and confirm each FAILS on unmodified code; paste failures into the Activity Log. Drive through the real CLI (`typer.testing.CliRunner` against the root app, or `subprocess` with the venv's `spec-kitty`) in a scratch repo (`tmp_path`, isolated HOME — reuse the fixtures of `tests/decisions/test_decisions_reconciler.py`).

1. **FR-001**: create a mission; `agent decision open --mission <m> --flow specify --slot-key <k> --input-key <k2> --question "…"` (check `agent decision open --help` for how to make it step_id-origin; the reconciler tests call `open_decision()` directly — mirror their origin choice) → `agent decision defer <id> --mission <m> --rationale "later"` (`--rationale` is required) → `agent decision resolve <id> --mission <m> --final-answer X`; delete `kitty-specs/<m>/decisions/index.json` (locate via the same helper the reconciler test uses — `_ledger_dir`); run `doctor decisions --mission <m> --repair --json`. Assert exit 0, the decision is in the rebuilt index with status `resolved` and final answer `X`, `malformed_folds == []`. (Today: `malformed_folds:[D]`, count 0.)
2. **FR-002 (existing logs, both orders)**: write the issue's on-disk shape directly into `status.events.jsonl` — one `DecisionPointOpened`, one `DecisionPointResolved(terminal_outcome=deferred)`, one `DecisionPointResolved(terminal_outcome=resolved)`; parametrise over (deferred-then-resolved) and (resolved-then-deferred) line order. Repair rebuilds as resolved.
3. **FR-003/FR-004 (truly unfoldable)**: a decision with two `DecisionPointOpened` events and an existing index entry. Read-only `doctor decisions --json` → `clean: false`, id in `malformed_folds`, exit 0. `--repair --json` → exit 1, exactly one JSON document on stdout, the index entry still present, id named. Same fixture with no prior index entry → exit 1, id named (we cannot fabricate an entry; refusing loudly is the contract).
4. **Stale status**: index entry says `deferred`, log folds to `resolved` → diagnose reports it (not clean); repair fixes it.
5. **Positive control (same fixture builder)**: a healthy open→resolve decision in the same log stays clean and untouched throughout.
6. **NFR-003**: every refusal assertion checks both the decision id AND the remedy text (the `agent decision list` / event-log pointer), not just the exit code.

### Subtask T008 – Shared transition rule + order-independent fold

- **Files**: `src/specify_cli/decisions/index_fold.py`, `src/specify_cli/decisions/service.py`.
- **Steps**:
  1. In `index_fold.py` define the rule once, e.g. `ALLOWED_TERMINAL_REOPEN: frozenset[tuple[DecisionStatus, DecisionStatus]] = frozenset({(DecisionStatus.DEFERRED, DecisionStatus.RESOLVED)})` and a predicate `is_allowed_terminal_reopen(current, target) -> bool`. Keep `index_fold` free of service imports (the service already imports `index_fold`; do not create a cycle).
  2. `service._is_allowed_terminal_reopen` delegates to it (single authority).
  3. `fold_events`: keep the "exactly one DecisionPointOpened" rule. For resolved events: 0 → opened state; 1 → fold as today; exactly 2 whose `terminal_outcome` set is `{deferred, resolved}` → fold the `resolved` one (the final answer comes from it) regardless of order; anything else (two resolved, resolved+canceled, 3+) → `FoldError` with a message naming the outcomes. Decide `resolved_at` from the resolved event's `state_entered_at`.
  4. Update the `fold_events` docstring to state the order-independence rule and why (merge driver re-sort).
  5. Keep complexity ≤15: extract `_select_terminal_event(resolved_events) -> Mapping | None`.

### Subtask T009 – Diagnose runs the fold and compares folded status

- **File**: `src/specify_cli/cli/commands/_decisions_doctor.py` (`_diagnose` ~:255-273, report type).
- **Steps**: after grouping events, fold each group (reuse the same loop shape as `_rebuild_index_from_log`: skip `_is_unrecoverable_slot_key_origin` entries into `lossy_attribution`); collect `malformed_folds` and `status_mismatch` (index status ≠ folded status). `report.clean` must be false when either is non-empty. Keep the read-only path read-only. `DecisionsReconciliationReport.clean` is a `@property` that today checks only missing/orphaned ids — extend that property to also be false when `malformed_folds` or `status_mismatch` is non-empty (add those as fields with empty defaults). Update `_emit_human`/`_emit_json` to print them.

### Subtask T010 – Repair refuses instead of erasing; help text

- **Files**: `_decisions_doctor.py` (`run_decisions_reconciliation` ~:370-420), `src/specify_cli/cli/commands/doctor.py` (the `decisions` subcommand help/docstring ~:1378-1414).
- **Steps**:
  1. Repair condition becomes `repair and not report.clean` (unchanged) but the rebuilt index must keep an existing entry for a malformed decision (it already does) — and when `malformed_ids` is non-empty after repair, emit the report then `raise typer.Exit(1)`. Do not raise a `GuardedReadError` after `_emit_json` (that prints a second JSON document).
  2. Human output: a clear line per malformed decision: id, "left in place", and how to inspect (`spec-kitty agent decision list --mission <m>` — there is no `show` subcommand — and the event log `status.events.jsonl`).
  3. Update the docstring ("Informational only… always exits 0") and the `doctor decisions` help in `doctor.py` to: diagnose always exits 0; `--repair` exits 1 when a decision cannot be reconciled (C-007).
- **Notes**: the read-only diagnose still exits 0 even when not clean (report-only), matching the contract table.

### Subtask T011 – Convert and gate

- Remove the `regression` markers after green; keep the tests as focused integration tests (the file name can stay).
- Run and record:

```bash
uv run --frozen pytest tests/decisions/ tests/specify_cli/decisions/ -q
uv run --frozen pytest $(grep -rl "doctor decisions\|_decisions_doctor" tests --include=*.py | sort -u) -q
uv run --frozen pytest tests/architectural/test_cli_error_surface_seam.py tests/architectural/test_status_module_boundary.py tests/architectural/test_layer_rules.py tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen ruff check <changed files> && uv run --frozen ruff format --check <changed files>
uv run --frozen mypy --strict src/specify_cli/decisions/index_fold.py src/specify_cli/decisions/service.py src/specify_cli/cli/commands/_decisions_doctor.py
make test-fast
```

## Risks & Mitigations

- Contract change (exit 1) may break an existing test that pinned exit 0 for a malformed repair: judge the test (stale pin → re-pin with a comment citing #4919; never delete a valid assertion).
- Event envelope shape: read one real event line produced by the CLI in T007 before hand-writing fixtures.

## Review Guidance

- NFR-001/NFR-002/NFR-003: red-first recorded; each destructive-fixture test has a positive control from the same fixture builder; refusals assert id + remedy text.

- NFR-001/NFR-002/NFR-003: red-first recorded; each destructive-fixture test has a positive control from the same fixture builder; refusals assert id + remedy text.

- Fold is order-independent (parametrised test proves both orders).
- One transition-rule definition, used by service and fold.
- Repair never drops; `--json` emits one document; exit codes per contract.
- Red-first failures recorded; markers removed.

## Activity Log

- 2026-09-28T09:40:00Z – system – Prompt created.
