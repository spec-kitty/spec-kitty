---
work_package_id: WP01
title: A bounded opaque failure identity
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-003
- C-002
- SC-001
- SC-002
- SC-003
- SC-005
planning_base_branch: issue-6751-opaque-failure-identity
merge_target_branch: issue-6751-opaque-failure-identity
branch_strategy: Planning artifacts for this mission were generated on issue-6751-opaque-failure-identity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6751-opaque-failure-identity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-opaque-failure-identity-01M67HQA
base_commit: 9f4e2411f086c00304e3615e3e1d8bcbf0718f90
created_at: '2026-10-30T23:22:30.024588+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Failure identity
history:
- timestamp: '2026-10-30T23:30:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/review/baseline.py
create_intent:
- src/specify_cli/review/baseline.py
- src/specify_cli/review/scope_source.py
- tests/review/test_opaque_failure_identity.py
- tests/review/test_scope_source.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/review/baseline.py
- src/specify_cli/review/scope_source.py
- tests/review/test_opaque_failure_identity.py
- tests/review/test_scope_source.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '6751'
---

# Work Package Prompt: WP01 – A bounded opaque failure identity

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (`spec-kitty agent profile show python-pedro`) and run
`spec-kitty charter context --action implement --json`; apply both before coding.

## Objectives & Success Criteria

Give the synthetic whole-run failure a real, comparable identity, so two opaque
declared-command failures are the same failure only when they actually are.

1. **Red first (T001).** Create `tests/review/test_opaque_failure_identity.py` and prove the
   issue's counterexample on the pre-fix tree: a baseline opaque failure
   (`exit 2`, `error: no build.zig file found ...`) and a candidate opaque failure
   (`exit 1`, `src/example.zig:1:1: error: expected type 'u64', found '[]const u8'`)
   classified through `DeclaredCommandScopeSource.parse_results` →
   `_classify_current_failures` returns `no_new_failures` today. The file MUST also carry,
   on the same fixture table:
   - the **identical-opaque** case (same exit status, same summary) → `no_new_failures`
     with one pre-existing failure (the positive control for the repro);
   - the **exit-status mismatch** case (same summary, different exit status) → new failure;
   - a **new named failure** vs a **pre-existing named failure** pair;
   - a **clean exit-0** candidate (`parse_results` → `()`), which must stay `no_new_failures`.
   Commit the failing repro as its own commit before any product edit and record the red
   command output in the commit body or the WP prompt's validation note.

2. **Identity fields (T002).** In `src/specify_cli/review/baseline.py`:
   - `OPAQUE_FAILURE_TEST_ID = "<declared-command>"` becomes the single canonical constant,
     defined beside `BaselineFailure` (the data model that owns the identity).
   - `BaselineFailure` gains `opaque: bool = False` and `exit_code: int | None = None`.
   - `to_dict` emits `opaque` only when true and `exit_code` only when not `None`, so a
     pre-change record round-trips byte-identically.
   - `from_dict` reads both with `data.get(...)` and, when `opaque` is absent, infers it from
     `test == OPAQUE_FAILURE_TEST_ID` — a legacy artifact must never silently regain the
     name-only collision and must never raise `KeyError` (NFR-003).

3. **Carry the exit status (T003).** In `src/specify_cli/review/scope_source.py`:
   - `_whole_run_failure` returns `BaselineFailure(test=OPAQUE_FAILURE_TEST_ID,
     error=summary, file="unknown", opaque=True, exit_code=raw.returncode)`.
   - The local `_UNPARSEABLE_FAILURE_TEST_ID` literal is deleted in favour of the canonical
     constant (imported lazily next to `BaselineFailure`, as the module already does).
   - Update `tests/review/test_scope_source.py` assertions to name the canonical constant and
     assert `opaque is True` / `exit_code == 2`; do not weaken the existing "never swallowed"
     assertion.

4. **Bound-identity comparison (T004).** In `diff_baseline`:
   - A named candidate failure is pre-existing iff a **named** baseline failure has the same
     `test` name (incumbent name-set semantics, duplicates included).
   - An opaque candidate failure is pre-existing iff a **named-or-opaque** baseline entry is
     opaque with the same `exit_code` and the same `error` summary. Everything else is new.
   - A named and an opaque entry never match, even if their text collides.
   - Add a legacy-artifact test: a `from_dict` record with `test="<declared-command>",`
     `error="no build.zig ..."` and no `opaque`/`exit_code` keys loads, is inferred opaque,
     and does **not** match a candidate opaque failure whose exit status is known.

## Constraints

- No gate is skipped, xfailed or retried; no timeout default changes (C-001 is WP02's, but
  do not regress it here either).
- Never classify an unparseable nonzero candidate result as a pass on the placeholder name
  alone (C-002).
- Do not touch `src/specify_cli/review/pre_review_gate.py` or the transition-gate renderer —
  those are WP02's owned files.

## Validation (targeted test surface)

- `.venv/bin/python -m pytest tests/review/test_opaque_failure_identity.py tests/review/test_scope_source.py tests/review/test_baseline.py -q`
- `make format-check-files FILES=src/specify_cli/review/baseline.py src/specify_cli/review/scope_source.py tests/review/test_opaque_failure_identity.py tests/review/test_scope_source.py`
- mypy on the two product modules (the repository's usual `uv run mypy` invocation for the
  touched package).
- Record in the WP completion note: the red command + output (pre-fix) and the green
  command + counts (post-fix).
