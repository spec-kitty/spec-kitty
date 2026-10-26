---
work_package_id: WP01
title: Typed "not authored" leg on the coordination ref reader
dependencies: []
requirement_refs:
- FR-003
- FR-004
- NFR-001
- NFR-002
- C-004
planning_base_branch: issue-6653-terminality-all-rows
merge_target_branch: issue-6653-terminality-all-rows
branch_strategy: Planning artifacts for this mission were generated on issue-6653-terminality-all-rows. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6653-terminality-all-rows unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-issue-matrix-terminality-all-rows-01M5X1ZJ
base_commit: 1b6fcc79f3424b002d85a81f85d67b9010fd1935
created_at: '2026-10-26T22:20:41.672044+00:00'
subtasks:
- T001
- T002
- T003
history:
- at: '2026-10-26T22:30:00Z'
  action: created
  actor: claude
agent_profile: python-pedro
authoritative_surface: src/mission_runtime/
create_intent: []
execution_mode: code_change
owned_files:
- src/mission_runtime/resolution.py
- tests/mission_runtime/test_issue_matrix_ref_read.py
- src/specify_cli/cli/commands/review/ERROR_CODES.md
role: implementer
tags: []
tracker_refs: []
---

# WP01 — Typed "not authored" leg on the coordination ref reader

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile with the `/spk-charter-profile-load` skill:
`spec-kitty agent profile show python-pedro`, then `spec-kitty charter context --action implement --json`.
Apply its initialization, boundaries, directives and tactics, and say which ones you applied.

## Objective

`mission_runtime.resolution.read_issue_matrix_ref_content` reads the issue-matrix content from
git (`git show <ref>:<path>`) when the coordination worktree is gone. Today, when the ref is
valid but no matrix file was ever committed there, it raises
`IssueMatrixRefReadError(ISSUE_MATRIX_PROBE_ERROR)`. That is the same code as a timeout, a
missing git executable or an unreadable object. WP02 needs to treat "no matrix authored" as
nothing to enforce, but only for a Mission with zero gating references, while every real probe
failure stays fail closed. This WP adds that distinction as a typed code on the existing
reader. It does not add a second reader (C-004; Decision `01M5X498X3ATTAB12KQWMDPZRV`).

Requirements: FR-003, FR-004, NFR-001, NFR-002, C-004.

## Context

- Reader: `src/mission_runtime/resolution.py`, around lines 2060–2300.
  - Codes: `_ISSUE_MATRIX_REF_ABSENT_CODE`, `_ISSUE_MATRIX_PROBE_ERROR_CODE`,
    `_ISSUE_MATRIX_EMPTY_CONTENT_CODE`.
  - Helpers: `_ensure_issue_matrix_ref_exists` (deleted-ref leg),
    `_read_issue_matrix_ref_content` (`git show`, which raises PROBE_ERROR on any non-zero
    exit), `_ensure_issue_matrix_content_authored` (empty leg).
  - The `.json` → `.md` failover lives in `read_issue_matrix_ref_content` itself.
- Presence discipline to reuse: `src/mission_runtime/lifecycle_phase.py::_git_object_present`
  (a valid-rev check, then a path check) and `_path_present_at_rev`. The rev is already
  confirmed by `_ensure_issue_matrix_ref_exists`, so only the path check is needed. Read
  `_path_present_at_rev` and confirm how it treats a timeout or an OSError. A probe that
  cannot run must NOT be read as "absent".
- Callers: `mission_runtime.issue_matrix_partition.resolve_issue_matrix_partition`,
  `specify_cli/cli/commands/review/__init__.py:481` (catches the type, code-agnostic), and the
  merge gates (through the partition). No caller in `src/` branches on `PROBE_ERROR`
  outside the reader itself (`git grep -n "_PROBE_ERROR_CODE\|\.code ==" -- src`).

## Subtask T001 — Red-first reader tests

**Purpose**: pin the new contract before the change.

**Steps** (in `tests/mission_runtime/test_issue_matrix_ref_read.py`; reuse its fixtures):
1. A post-consolidation coordination Mission whose coordination ref resolves but holds
   neither `issue-matrix.json` nor `issue-matrix.md`: expect `IssueMatrixRefReadError` with
   `code == "ISSUE_MATRIX_NOT_AUTHORED"`. This is RED today: the code is PROBE_ERROR.
2. Controls that must stay as they are (GREEN today, GREEN after):
   - a deleted ref → `ISSUE_MATRIX_REF_ABSENT`;
   - an empty authored matrix → `ISSUE_MATRIX_EMPTY_CONTENT`;
   - a legacy `.md`-only matrix at the ref → content returned.
3. A probe that cannot run: patch `subprocess.run` (or the reader's git call) to raise
   `subprocess.TimeoutExpired` / `OSError` on the content probe AND on the presence probe.
   Expect `ISSUE_MATRIX_PROBE_ERROR`, never NOT_AUTHORED (NFR-002).
4. A `git show` that fails for a reason other than absence while the object IS present (for
   example, patch the content probe to fail while the presence probe sees the object): expect
   PROBE_ERROR.

Commit the tests first (ATDD, a separate commit), and show they fail for the right reason.

## Subtask T002 — The NOT_AUTHORED leg

**Steps**:
1. Add `_ISSUE_MATRIX_NOT_AUTHORED_CODE = "ISSUE_MATRIX_NOT_AUTHORED"` next to the other codes.
2. In `read_issue_matrix_ref_content`: when the `.md` failover's content probe also raises
   PROBE_ERROR, run an object-presence check for BOTH object paths at the already-validated
   ref. Raise NOT_AUTHORED only when both checks positively report "absent". When the
   presence check itself fails or cannot run, re-raise the original PROBE_ERROR.
   - Keep the function under complexity 15: extract a small helper such as
     `_raise_not_authored_if_absent(main_root, ref, object_paths, original)`.
3. Do not touch the deleted-ref or empty-content legs.
4. NFR-001: the extra probes run only on that failure path, which is at most two
   object-presence checks, so a successful read costs nothing extra.
5. Update the docstrings of `read_issue_matrix_ref_content` and `IssueMatrixRefReadError` so
   they list the four codes and state that NOT_AUTHORED means "the ref is valid and neither
   file was ever committed there", which callers may treat as "no matrix" only where an absent
   matrix is legitimately nothing to enforce.

## Subtask T003 — Document the code and audit callers

**Steps**:
1. `src/specify_cli/cli/commands/review/ERROR_CODES.md` (~line 163): add NOT_AUTHORED to the
   list of reader failures, and note that a Mission WITH gating references still fails closed
   on it.
2. Audit: `git grep -n "IssueMatrixRefReadError" -- src`. Confirm every caller either treats
   the type as fail closed or will be updated by WP02 (merge gates). Record the audit result in
   your WP handoff note.
3. Run `tests/architectural/test_mission_runtime_surface.py` and, if a new public symbol is
   exported, `tests/architectural/test_no_dead_symbols.py`. Prefer keeping the code private
   (module constant) and exposing it only through `exc.code`.

## Test strategy

Run, and record counts:
- `uv run --frozen pytest -q tests/mission_runtime/`
- `uv run --frozen pytest -q tests/specify_cli/cli/commands/review/test_issue_matrix_partition.py tests/status/test_doctor_issue_matrix_coord_partition.py tests/integration/test_coord_unprotected_lifecycle_loop.py`
- `uv run --frozen pytest -q tests/architectural/test_mission_runtime_surface.py`
- `make test-fast`
- `uv run --frozen ruff check src/mission_runtime/resolution.py tests/mission_runtime/test_issue_matrix_ref_read.py`;
  `uv run --frozen ruff format --check --force-exclude <same>`; `uv run --frozen mypy src/mission_runtime/resolution.py`

## Branch strategy

Planning/base branch `issue-6653-terminality-all-rows`, final merge target
`issue-6653-terminality-all-rows`. The execution worktree is allocated per computed lane from
`lanes.json`. Run `spec-kitty agent action implement WP01 --agent <name> --mission issue-matrix-terminality-all-rows-01M5X1ZJ`.
Never pick a base branch by hand.

## Definition of Done

- [ ] T001 tests committed first, red on the base for the right reason, green at the end.
- [ ] NOT_AUTHORED is raised only on positive absence of both files at a valid ref.
- [ ] Timeout, OSError, unreadable object and deleted ref keep their existing codes.
- [ ] Docstrings and `ERROR_CODES.md` updated; caller audit recorded.
- [ ] ruff, format and mypy clean; complexity ≤ 15; no new `noqa` / `type: ignore`.

## Reviewer guidance

Check that no code path maps a probe that could not run to NOT_AUTHORED. Read the presence
helper's exception handling: a bare `except` that returns False would be a defect. Check that
the successful-read path is byte-identical.
