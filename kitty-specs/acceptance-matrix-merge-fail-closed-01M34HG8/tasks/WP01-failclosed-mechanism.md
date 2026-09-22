---
work_package_id: WP01
title: Fail-closed mechanism (merge_driver.py)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-005
- NFR-002
- NFR-003
planning_base_branch: fix/acceptance-matrix-merge-fail-closed
merge_target_branch: fix/acceptance-matrix-merge-fail-closed
branch_strategy: Planning artifacts for this mission were generated on fix/acceptance-matrix-merge-fail-closed. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/acceptance-matrix-merge-fail-closed unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-acceptance-matrix-merge-fail-closed-01M34HG8
base_commit: 4f906b8444aeb828eb13d563cbc6d547718b2a38
created_at: '2026-09-22T13:42:05.508434+00:00'
subtasks:
- T001
- T002
- T003
- T004
history:
- '2026-09-22: authored by /spec-kitty.tasks'
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/merge_driver.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile via `/ad-hoc-profile-load`
(profile: `python-pedro`). Apply its identity, boundaries, and TDD/type-safety
discipline for the whole work package.

## Objective

Close the #4880 verdict-corruption class **by construction**: make the shared
field-merge step raise instead of embedding git conflict markers as JSON values,
delete the embed path, and harden the drivers' exception handling.

## Context

`src/specify_cli/cli/commands/merge_driver.py` reconciles matrix documents. Today
`_merge_field(base_v, ours_v, theirs_v)` returns `_field_conflict_marker(ours, theirs)`
(line ~424) when a field changed on **both** sides to different non-base values, and
the driver exits 0 — so a merge commits a matrix whose `overall_verdict` recomputes to
`fail`. The fail-closed spine already exists: `RowMatrixMergeError` is caught by both
`merge_driver_acceptance_matrix` (:693) and `merge_driver_issue_matrix` (:604) →
`typer.Exit(1)` → git leaves the conflict → `lanes/merge.py::_merge_branch_into` aborts.

### Subtask T001 — Raise on the both-sides-diverged branch

- In `_merge_field` (~:407-424), replace the final `return _field_conflict_marker(ours_v, theirs_v)`
  with `raise RowMatrixMergeError(...)`. The message must name the offending field
  and both candidate values (keep it human-actionable for the person resolving the
  conflict). Do **not** change the three preceding equality branches (identical /
  one-sided change resolve cleanly and must keep resolving).
- This makes both matrix drivers fail closed on a genuine field conflict — that is
  the intended behavior for verdict artifacts (see spec US1/US2).

### Subtask T002 — Delete the unreachable embed function ONLY

- Remove the `_field_conflict_marker` **function** (~:395-404) — T001 removed its only
  caller. Grep to confirm: `git grep -n "_field_conflict_marker"` should show only the
  definition + a narrative doc-comment in a test (not an import).
- **KEEP the three `_CONFLICT_MARKER_OURS/SEP/THEIRS` constants (:390-392).** They are
  **also consumed by `merge_driver_review_cycle`** (it builds its `conflict_document`
  from them at ~:796-804) — the review-cycle driver's marker-embed is *correct* prose
  behavior (NFR-002) and must not break. Deleting the constants would break it. Only the
  function goes.

### Subtask T003 — Harden the drivers' `except`

- Broaden the `except` in **both** `merge_driver_acceptance_matrix` (:693) and
  `merge_driver_issue_matrix` (:604) to also catch `AcceptanceMatrixParseError`
  (defined in `acceptance/matrix.py:129`, raised by WP02's read guard) → `typer.Exit(1)`.
  Rationale (brownfield finding): if a marker ever reaches `AcceptanceMatrix.from_dict`
  at :677, it must exit via the clean `Exit(1)` + `--abort` spine, not propagate
  uncaught. Import the exception where the driver already imports acceptance types.
  Note: the load-bearing catch is on `merge_driver_acceptance_matrix` (the only driver
  that calls `AcceptanceMatrix.from_dict`, at :677) — where it *also* fixes a pre-existing
  uncaught-crash path (a malformed row can already raise `AcceptanceMatrixParseError`
  today, uncaught by the `RowMatrixMergeError`-only clause). Adding it to
  `merge_driver_issue_matrix` too is harmless forward-compatibility (that driver does not
  call `from_dict`); keep both for symmetry but the acceptance arm is the real fix.

### Subtask T004 — Confirm the exit/abort path

- By reading (not a broad test run): confirm that after T001, a both-sides field
  conflict propagates `RowMatrixMergeError` out of `reconcile_*` → caught at
  :604/:693 → `Exit(1)`; and that `_merge_branch_into` treats a non-zero driver as a
  failed merge (`git merge --abort`). Leave a one-line code comment at the raise site
  citing #4880.

## Branch Strategy

Planning/base branch: `fix/acceptance-matrix-merge-fail-closed`. Final merge target:
`fix/acceptance-matrix-merge-fail-closed`. The execution worktree is allocated per the
computed lane in `lanes.json` — do not reconstruct the path; enter the workspace
`spec-kitty implement WP01` resolves.

## Definition of Done

- `_merge_field` raises `RowMatrixMergeError` on the both-sides-diverged branch; the
  three preceding resolve-branches are unchanged.
- `_field_conflict_marker` **function** deleted; the `_CONFLICT_MARKER_*` constants **retained** (review-cycle driver still uses them); no dangling reference to the function.
- Both matrix drivers' `except` catches `RowMatrixMergeError` **and** `AcceptanceMatrixParseError`; the `_CONFLICT_MARKER_*` constants are retained (review-cycle driver).
- **Expected-red gate (objectively checkable):** on WP01 alone, exactly the two same-field
  pins `test_acceptance_matrix_same_field_conflict_never_silent_pick` (:379) and
  `test_issue_matrix_same_field_divergence…` (:194) flip to red (they still assert the old
  marker-embed — WP03 re-anchors them). **No OTHER test in
  `tests/specify_cli/cli/commands/test_row_aware_merge_driver.py` may regress.** Verify that
  precise shape, do not "green-wash" by editing the tests here (WP03 owns them).
- `ruff` + `mypy` clean on the file.

## Risks / reviewer guidance

- **Do not touch** the review-cycle driver (`merge_driver_review_cycle`, ~:700+) — its
  non-aborting prose behavior is correct (NFR-002).
- Keep the change inside `specify_cli` (NFR-003) — no new cross-layer import.
- Reviewer: confirm the raise fires only on the genuine both-sides branch, not on
  one-sided/identical fields (which would abort legitimate clean merges).
