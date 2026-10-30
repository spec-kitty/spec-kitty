---
work_package_id: WP01
title: Doctor --repair refuses a busy decisions lock
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- NFR-003
- C-001
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6763-decisions-lock-timeout-refusal
merge_target_branch: issue-6763-decisions-lock-timeout-refusal
branch_strategy: Planning artifacts for this mission were generated on issue-6763-decisions-lock-timeout-refusal. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6763-decisions-lock-timeout-refusal unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-decisions-lock-timeout-refusal-01M66YMG
base_commit: f7407d91cc4c20c83a80b5631214f3c23aa92ced
created_at: '2026-10-30T17:50:25.145485+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Doctor refusal
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/_decisions_doctor.py
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/decisions/service.py
- src/specify_cli/cli/commands/_decisions_doctor.py
- tests/decisions/test_decisions_reconciler.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Doctor `--repair` refuses a busy decisions lock

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the
frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before
starting. Address every feedback item before declaring the work complete.

---

## Objectives & Success Criteria

- `spec-kitty doctor decisions --mission <m> --repair` (human and `--json`) reports a
  decisions-lock timeout as the doctor family's C2 refusal and exits 1 — never a
  `kernel.locks.LockAcquireTimeout` traceback, and never a partial report document.
- The same holds for the doctor's second acquisition, the additive coordination-only ledger
  copy, which must refuse before copying anything.
- The decisions sidecar lock has ONE timeout translation in the codebase
  (`decisions/service.py::_decisions_lock`) and ONE wait constant
  (`_LOCK_ACQUIRE_TIMEOUT_S`), so the doctor and the write path cannot drift apart.

Acceptance criteria come from [spec.md](../spec.md) FR-001, FR-002, FR-003 and C-001;
reproduction steps are in [quickstart.md](../quickstart.md).

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6763. Sibling mission #6764 works on `doctor decisions`
  *findings*; do not touch finding semantics.
- `decisions/service.py::_decisions_lock(lock_path, *, timeout_s, mission_slug, decision_id)`
  is the existing seam. It translates ONLY the acquire into
  `DecisionError(code=DecisionErrorCode.LOCK_TIMEOUT)` whose message already says
  `Nothing was written; retry the command.`
- `_decisions_doctor.py` keeps a private `_LOCK_FILENAME`, `_LOCK_ACQUIRE_TIMEOUT_S` and
  `_decisions_lock_path()` copy of the service's. This WP removes the duplicated *timeout
  constant* (import the service's) and leaves `_decisions_lock_path` in place: two existing
  lockstep tests pin it as the doctor's own symbol.
- The doctor family's `--json` failure contract is C2:
  `{"ok": false, "error": {"code", "message"}}` (`specify_cli/cli/json_contract.py::json_error`,
  emitted through `console.emit_json`). Human mode uses a Rich `Error:` line. See
  `_doctor_shared._emit_not_in_project` for the precedent.
- ADR `docs/adr/4.x/2026-10-27-2-owned-refusals-use-the-c2-error-contract.md`: do not invent a
  new envelope.

## Branch Strategy

- **Strategy**: `lanes` mission on branch `issue-6763-decisions-lock-timeout-refusal`; merge target is the same branch.
- **Planning base branch**: `issue-6763-decisions-lock-timeout-refusal`
- **Merge target branch**: `issue-6763-decisions-lock-timeout-refusal`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not edit by hand.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first test for `doctor decisions --repair`

- **Purpose**: Prove the defect through the real CLI before fixing it.
- **Steps**:
  1. In `tests/decisions/test_decisions_reconciler.py`, add a test near the other real-CLI
     tests: build the flat fixture (`_setup_meta(tmp_path)` plus at least one resolvable
     divergence, e.g. an index entry with no backing event, so `report.clean` is False and
     `--repair` actually takes the lock).
  2. `monkeypatch.setattr("specify_cli.cli.commands._decisions_doctor._LOCK_ACQUIRE_TIMEOUT_S", 0.2)`
     — or, after T004, patch the service constant the doctor imports. Hold the lock with
     `kernel.locks.machine_file_lock(doctor_lock_path, blocking=True, timeout_s=5)`.
  3. Invoke `doctor decisions --mission <m> --repair --json` (see
     `_invoke_doctor_decisions_json`) and assert: exit code 1; stdout parses as ONE JSON
     document; `document["ok"] is False`; `document["error"]["code"] == "DECISION_LOCK_TIMEOUT"`;
     the message names the lock path and contains "retry"; the decisions directory is
     byte-identical to before (reuse the tree-snapshot helper style already in this module or
     `_tree_bytes` from `tests/specify_cli/cli/commands/test_decision.py`).
  4. Capture the pre-fix output (`LockAcquireTimeout` escaping; `CliRunner` returns exit 1 with
     a `LockAcquireTimeout` exception and no JSON) for the PR's "Tests run" section.
- **Files**: `tests/decisions/test_decisions_reconciler.py`
- **Parallel?**: no.
- **Notes**: `machine_file_lock` contention is real in-process because each acquire opens its
  own descriptor — hold the lock with the helper, never by pre-creating the file.

### Subtask T002 – Red-first test for the coordination-only ledger copy site

- **Purpose**: The copy is a second acquisition with its own failure mode: it must refuse
  before copying a single `DM-*.md`.
- **Steps**:
  1. Call `_copy_coordination_only_ledger(repo_root, mission_slug, ledger_dir)` directly with
     the lock held and the wait shortened.
  2. Assert it raises `DecisionError` with `code is DecisionErrorCode.LOCK_TIMEOUT` before
     T004 (it will instead raise `LockAcquireTimeout`), and that the ledger directory is
     unchanged.
  3. Once T005 lands, extend the assertion to the rendered outcome where practical, or leave
     this test at the seam (the CLI-level rendering is pinned by T001).
- **Files**: `tests/decisions/test_decisions_reconciler.py`
- **Parallel?**: no.
- **Notes**: keep the fixture minimal; the copy path needs a coordination ledger stub — reuse
  `_fork.read_coordination_ledger_raw`'s existing test fixtures if one fits, otherwise patch it.

### Subtask T003 – Widen the seam's slug annotation

- **Purpose**: `_repair` is typed `mission_slug: str | None`; the seam must accept what its
  callers have instead of forcing an invented slug.
- **Steps**: in `src/specify_cli/decisions/service.py`, change
  `_decisions_lock(..., mission_slug: str, ...)` to `mission_slug: str | None`. Keep the
  `details` payload unchanged. Update the docstring only if it now says something untrue.
- **Files**: `src/specify_cli/decisions/service.py`
- **Parallel?**: no.
- **Notes**: this is a private helper; no public contract changes and no new error code.

### Subtask T004 – Route both doctor acquisitions through `_decisions_lock`

- **Purpose**: one translation, one wait constant.
- **Steps**:
  1. In `src/specify_cli/cli/commands/_decisions_doctor.py`, import
     `_LOCK_ACQUIRE_TIMEOUT_S` and `_decisions_lock` from `specify_cli.decisions.service`
     (module import is fine; the module already imports `_ledger_dir` from there).
  2. Delete the module's own `_LOCK_ACQUIRE_TIMEOUT_S = 10.0` and its now-stale comment.
  3. Replace both `with machine_file_lock(lock_path, blocking=True, timeout_s=_LOCK_ACQUIRE_TIMEOUT_S):`
     blocks with
     `with _decisions_lock(lock_path, timeout_s=_LOCK_ACQUIRE_TIMEOUT_S, mission_slug=mission_slug, decision_id=None):`
     — in `_repair` (`mission_slug` is a parameter) and in `_copy_coordination_only_ledger`
     (which also has `mission_slug`). Drop the now-unused `machine_file_lock` import if
     nothing else uses it.
- **Files**: `src/specify_cli/cli/commands/_decisions_doctor.py`
- **Parallel?**: no.
- **Notes**: do not add a local `try/except LockAcquireTimeout`; that is a second authority.
  Keep the in-lock behaviour byte-identical.

### Subtask T005 – Render the doctor's lock-timeout refusal

- **Purpose**: the operator (and a `--json` script) gets the actionable refusal, exit 1.
- **Steps**:
  1. In `run_decisions_reconciliation`, wrap the `--repair` block (`_repair` and
     `_copy_coordination_only_ledger`) in `try: ... except DecisionError as exc:` — placed so
     the catch runs BEFORE `_emit_human` / `_emit_json`, and so nothing is printed twice.
  2. Emit exactly one document: under `json_output`, `console.emit_json(json_error(exc.code.value, str(exc)))`
     (C2 shape); otherwise `console.print(f"[red]Error:[/red] {exc}")`. Then
     `raise typer.Exit(1) from exc`.
  3. Document the refusal in the `run_decisions_reconciliation` docstring: a lock timeout is a
     refusal, not a report, and nothing was written.
  4. Re-run T001/T002 and the rest of `tests/decisions/` — the free-lock repair path must still
     print its normal report and exit 0/1 exactly as before.
- **Files**: `src/specify_cli/cli/commands/_decisions_doctor.py`,
  `tests/decisions/test_decisions_reconciler.py`
- **Parallel?**: no.
- **Notes**: catch `DecisionError` (the seam's own type), not `Exception`, and do not change
  the fork/malformed-fold refusal behaviour that already exits 1 with a report.

## Test Strategy

- `uv run pytest tests/decisions/ -q` (fast tier; no full heavy suite).
- `uv run ruff check src/specify_cli/cli/commands/_decisions_doctor.py src/specify_cli/decisions/service.py`
- `uv run mypy src/specify_cli/cli/commands/_decisions_doctor.py` (the repo's configured
  typecheck; a passing test run does not replace it).
- Capture the pre-fix failure of T001/T002 for the PR body (red-first proof).

## Risks & Mitigations

- Double report (a partial JSON document plus an error document) → the catch precedes every
  `_emit_*` call.
- `_repair` called with `mission_slug=None` → the widened annotation; never fabricate a slug.
- Removing the local timeout constant could break a test that patches it → grep
  `_decisions_doctor._LOCK_ACQUIRE_TIMEOUT_S` first; patch the service constant instead.

## Review Guidance

- Verify there is exactly ONE `try/except LockAcquireTimeout` in the repo for this lock (in
  `service.py`), and that the doctor has no remaining local wait constant.
- Verify the refusal path writes nothing: compare the decisions tree before/after.
- Verify human and `--json` both exit 1 with the code, and that a free lock still reports and
  repairs.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
