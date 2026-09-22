---
work_package_id: WP03
title: Red-first + re-anchor the divergence pins
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- NFR-001
planning_base_branch: fix/acceptance-matrix-merge-fail-closed
merge_target_branch: fix/acceptance-matrix-merge-fail-closed
branch_strategy: Planning artifacts for this mission were generated on fix/acceptance-matrix-merge-fail-closed. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/acceptance-matrix-merge-fail-closed unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-acceptance-matrix-merge-fail-closed-01M34HG8
base_commit: 603239ddbc8108080493a24f77b718a7d10db097
created_at: '2026-09-22T14:11:35.811932+00:00'
subtasks:
- T007
- T008
- T009
- T014
history:
- '2026-09-22: authored by /spec-kitty.tasks'
agent_profile: python-pedro
authoritative_surface: tests/
create_intent: []
execution_mode: code_change
owned_files:
- tests/specify_cli/cli/commands/test_row_aware_merge_driver.py
- tests/merge/test_gate_artifact_merge_drivers_2804.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load your assigned profile via `/ad-hoc-profile-load` (profile: `python-pedro`) before
anything else.

## Objective

Prove the fix witnesses the bug (red-first) and re-anchor the three tests that currently
**green-pin** the corruption so they expect a refusal (FR-003). Depends on WP01.

## Context

Three tests assert marker-embed + "must not raise" — each is a genuine same-key
both-sides field conflict that RAISES under WP01 and must be re-anchored:

1. `tests/specify_cli/cli/commands/test_row_aware_merge_driver.py::test_acceptance_matrix_same_field_conflict_never_silent_pick` (~:379) — acceptance `pass_fail` pending→pass/fail (the direct #4880 repro).
2. `tests/specify_cli/cli/commands/test_row_aware_merge_driver.py::test_issue_matrix_same_field_divergence_is_structured_conflict_not_silent_pick` (~:194) — issue-matrix `verdict` unknown→fixed/wontfix.
3. `tests/merge/test_gate_artifact_merge_drivers_2804.py::test_a3_evidence_survives_inside_conflict_marker` (~:178) — the lesser variant: `pass_fail` equal, prose diverges → markers embedded today.

### Subtask T007 — Red-first proof

- Before re-anchoring, demonstrate the pins genuinely witness the bug: check out the
  pre-fix `merge_driver.py` and confirm the three currently assert marker-embed; then
  restore WP01's version. Record the before/after in the PR evidence (per the landing
  runbook's red-first step). Use file-scoped runs only:
  `PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_row_aware_merge_driver.py tests/merge/test_gate_artifact_merge_drivers_2804.py -q`

### Subtask T008 — Re-anchor the three pins to expect refusal

- Rewrite each of the three tests to assert the reconciler now RAISES `RowMatrixMergeError`
  (e.g. `with pytest.raises(RowMatrixMergeError): reconcile_*(...)`) rather than returning a
  marker string. Update docstrings to state the fail-closed contract and cite #4880 / the
  amended ADR 2026-07-23-2.

### Subtask T009 — Keep the controls green

- **Keep green, do not weaken**: `test_a4_control_invalid_pass_fail_still_fails` (an
  *authored* out-of-domain token → `fail` is correct), the disjoint-key add/add tests,
  `test_issue_3231_*` (disjoint keys → no field conflict), and all review-cycle driver tests.
- **No distinct 01KZPG7V FR-004 negative control green-pins the flip.** The post-tasks
  review confirmed `tests/acceptance/test_post_consolidation.py` pins negative-invariant
  *provenance* (C6/C7), never calls the reconcile driver, and does not assert a
  `pass_fail`-conflict→`fail` flip — it is a red herring and is NOT owned by this WP. The
  flip is already fully pinned by the two same-field pins in T008. Do a quick confirming
  grep (`git grep -n "overall_verdict.*fail" tests/`) and record in the PR that no
  additional un-owned red exists; do **not** edit `test_post_consolidation.py`.

### Subtask T014 — CLI-entry refusal test (FR-002 / SC-001)

- FR-002 (refusal ⇒ non-zero exit, target ref not advanced) must have an OWNING test, not
  just "confirmed by reading." In the owned `tests/specify_cli/cli/commands/test_row_aware_merge_driver.py`,
  add a test that invokes the CLI entrypoint `merge_driver_acceptance_matrix(base, ours, theirs)`
  on a both-sides `pass_fail` conflict and asserts it raises `typer.Exit` with code 1 (mirror
  the existing corrupt-JSON `Exit(1)` tests at ~:278/:293, which only cover the malformed-JSON
  path). Add the issue-matrix twin against `merge_driver_issue_matrix` if cheap.
- If a real-git-merge both-sides refusal is feasible in-suite (mirror the disjoint-success
  git-merge tests at ~:505/:543 but with a same-field conflict), add one asserting the merge
  aborts and the target ref is unchanged. If that is heavier than it's worth here, note the
  gap in the PR rather than faking it.

## Branch Strategy

Planning/base + merge target: `fix/acceptance-matrix-merge-fail-closed`. WP03 branches
from WP01's lane (dependency); enter the workspace `spec-kitty implement WP03` resolves.

## Definition of Done

- The three named pins expect a `RowMatrixMergeError` refusal and pass on WP01's code.
- Red-first evidence captured (pins fail against pre-fix product file).
- Controls (`test_a4`, disjoint-key, review-cycle) untouched and green.
- 01KZPG7V FR-004 negative control located and re-anchored (or explicitly reported absent).
- File-scoped runs green; `ruff` clean.

## Risks / reviewer guidance

- Never green-wash: prove each re-anchored assertion reflects the *new intended behavior*
  (refusal), not a silenced failure.
- Do not touch product code (WP01/WP02 own it) — tests only.
