---
work_package_id: WP02
title: Read-side marker-reject guard (matrix.py)
dependencies: []
requirement_refs:
- FR-004
- NFR-001
planning_base_branch: fix/acceptance-matrix-merge-fail-closed
merge_target_branch: fix/acceptance-matrix-merge-fail-closed
branch_strategy: Planning artifacts for this mission were generated on fix/acceptance-matrix-merge-fail-closed. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/acceptance-matrix-merge-fail-closed unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-acceptance-matrix-merge-fail-closed-01M34HG8
base_commit: 61e0e1046385cea11a60e54a2ec8a25ae0c7d753
created_at: '2026-09-22T13:44:31.748498+00:00'
subtasks:
- T005
- T006
history:
- '2026-09-22: authored by /spec-kitty.tasks'
agent_profile: python-pedro
authoritative_surface: src/specify_cli/acceptance/
create_intent:
- tests/specify_cli/acceptance/test_matrix_marker_reject.py
execution_mode: code_change
owned_files:
- src/specify_cli/acceptance/matrix.py
- tests/specify_cli/acceptance/test_matrix_marker_reject.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load your assigned profile via `/ad-hoc-profile-load` (profile: `python-pedro`) before
anything else.

## Objective

Defense-in-depth (FR-004): make `AcceptanceMatrix.from_dict` reject any field value
containing a git conflict marker, so a marker-laden matrix from **any** source fails
loudly instead of silently recomputing `overall_verdict` to `fail`.

## Context

`src/specify_cli/acceptance/matrix.py`: `from_dict` (~:351-359) and the per-row
`AcceptanceCriterion.from_dict` (~:214-217) / `NegativeInvariant.from_dict` (~:265-268)
currently do **no** value validation — a marker string is a valid `str`, so it round-trips
and `overall_verdict` (~:311-335) coerces it to `"fail"`. `AcceptanceMatrixParseError`
already exists (~:129).

### Subtask T005 — Reject marker-laden values

- Add a guard (a small module-level helper, e.g. `_reject_conflict_markers(field, value)`)
  that raises `AcceptanceMatrixParseError` when a string field value contains any of
  `<<<<<<<`, `=======`, `>>>>>>>`. Apply it in `from_dict` across every criterion/invariant
  string field (name the offending field + row key in the message).
- Keep it independent of WP01 — this module must fail loudly on markers on its own.
- Do **not** change `overall_verdict`'s enumeration semantics (out-of-scope, C-001): an
  *authored* out-of-domain token still recomputes to `fail`; only markers are rejected.

### Subtask T006 — Focused test

- New `tests/specify_cli/acceptance/test_matrix_marker_reject.py`: construct a matrix
  dict with a marker string in (a) `pass_fail`, (b) a prose field like `notes`; assert
  each raises `AcceptanceMatrixParseError` naming the field. Add a negative case: a clean
  matrix parses fine, and an authored out-of-domain `pass_fail` still yields `overall_verdict == "fail"`
  (proves we did not over-reject).

## Branch Strategy

Planning/base + merge target: `fix/acceptance-matrix-merge-fail-closed`. Enter the
workspace `spec-kitty implement WP02` resolves; do not reconstruct the path.

## Definition of Done

- `from_dict` raises `AcceptanceMatrixParseError` on any conflict-marker value; clean
  matrices unaffected; authored-invalid-token→`fail` behavior preserved.
- New focused test passes:
  `PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/acceptance/test_matrix_marker_reject.py -q`
- `ruff` + `mypy` clean.

## Risks / reviewer guidance

- Parallel-safe with WP01 (different module). WP01 broadens the drivers' `except` to
  catch this exception — that is WP01's job, not yours.
- Keep the marker check narrow (the three canonical markers); do not invent a broader
  "looks suspicious" heuristic.
