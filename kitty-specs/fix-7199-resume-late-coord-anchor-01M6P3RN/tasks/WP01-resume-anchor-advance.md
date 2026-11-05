---
work_package_id: WP01
title: The approved-tip advance on a resume
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- C-001
- C-002
- C-003
- SC-001
- SC-003
planning_base_branch: issue-7199-resume-late-coord-anchor
merge_target_branch: issue-7199-resume-late-coord-anchor
branch_strategy: Planning artifacts for this mission were generated on issue-7199-resume-late-coord-anchor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7199-resume-late-coord-anchor unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Core fix
history:
- timestamp: '2026-11-05T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/specify_cli/consolidation/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/phase_teardown.py
- src/specify_cli/consolidation/run_state.py
- tests/coordination/test_projection_teardown.py
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 – The approved-tip advance on a resume

## ⚡ Do This First: Load Agent Profile

Load the implementer profile before reading anything else:

```bash
spec-kitty agent profile show python-pedro
```

## Objective

Make a `--resume` that proves it landed its late coordination window advance
`run.coord_tip_after_projection` to the proven tip — the same step PR #7124 added for a first
run — so the projection teardown gate and the branch-delete compare-and-swap anchor on a tip
whose coordination records are on the target instead of refusing a landing the run just
completed.

## Context

- `src/specify_cli/consolidation/phase_teardown.py`, end of
  `_land_late_coordination_commits`:

  ```python
  if not run.is_resume and projected_tip and _resolve_ref_sha(run.main_repo, coord_ref) == projected_tip:
      run.coord_tip_after_projection = projected_tip
  ```

  That `not run.is_resume` is the whole defect (#7199, reviewer finding B5 on #7124).
- `_teardown_coord_worktree` builds `ProjectionTeardownGate(expected_coord_sha=run.coord_tip_after_projection
  or checkpoint.sha)`; `_delete_mission_branch` compare-and-swaps the same value. A stale anchor
  therefore refuses with `the coordination tip moved since projection captured its window
  (compare-and-swap failed)`.
- `_late_window_base` gives a resume `state.pre_mutation_coord_sha`, i.e. a base at or before the
  anchor the claim/bookkeeping phase captured. The resume window is a superset of the first-run
  window, and `assert_late_window_landed` proves every coordination record in it is byte-identical
  on the target — so the advance is justified by the same proof it already runs.
- A resume that short-circuits the phase list (`_resume_reconciliation_already_passed`) never
  captures `coord_tip_after_projection`; it falls back to `checkpoint.sha`. The advance must work
  from that state too (no "only advance if the previous value exists" rule).
- The fail-closed leg: the advance requires the live ref to still equal the tip the window read.
  A commit landing *during* the projection leaves the old anchor and the gate refuses. Keep it.
- `src/specify_cli/consolidation/run_state.py` documents the field as advancing "on a first run
  only"; that comment and the `_late_window_base` / `_land_late_coordination_commits` docstrings
  are the prose to correct.

## Subtasks

### T001 — Red: a resume advances the proven tip and finishes

In `tests/coordination/test_projection_teardown.py`, next to
`test_first_run_lands_a_coordination_commit_made_between_the_gate_and_teardown`:

- reuse `_first_run_with_coord_worktree(tmp_path)` to get a real repo, real coordination worktree,
  gated run state and captured tip;
- flip the run to a resume: `run.is_resume = True`, `run.state.pre_mutation_coord_sha = tip`;
- commit one late coordination record inside the Mission directory in the coordination worktree
  (that is the "commit after the run's own capture" the issue describes);
- call `phase_teardown._teardown_coordination_triple(run)`;
- assert: exit-0 shape (no exception), branch gone, the record's bytes committed on the target
  ref, the coordination marker flattened from `meta.json`, and
  `run.coord_tip_after_projection == late_tip`.

At the base commit this test must fail with the gate's `compare-and-swap failed` refusal. Record
the failure text in the PR.

### T002 — Red: a commit landing during the projection still refuses

Mirror `test_first_run_does_not_approve_a_tip_that_moved_during_the_projection` for the resume
fixture: patch `phase_teardown._commit_projection_and_carry` so a foreign coordination commit
(`meta.json` only, which the assertion exempts) lands while the projection runs, then assert
`ProjectionTeardownAbort` with `compare-and-swap failed`, the anchor still at the pre-window tip,
and the branch kept. This is the non-vacuity control for T001: it proves the advance is a
compare-and-swap, not a "whatever was last read".

### T003 — Drop the run-kind guard, keep the compare-and-swap

In `_land_late_coordination_commits`:

```python
if projected_tip and _resolve_ref_sha(run.main_repo, coord_ref) == projected_tip:
    run.coord_tip_after_projection = projected_tip
```

Update the comment above it: the advance is per proof, not per run kind; a resume window covers at
least the first-run window. Do not touch `_refuse_unbuildable_late_window`, the unreadable-ref
refusal, the window base, or the assertion.

### T004 — Correct the prose that states the old rule

- `src/specify_cli/consolidation/run_state.py`: the `coord_tip_after_projection` comment says
  "Teardown may also ADVANCE it, on a first run only" — make it run-kind-neutral and state the
  compare-and-swap condition.
- `src/specify_cli/consolidation/phase_teardown.py`: `_late_window_base` and
  `_land_late_coordination_commits` docstrings that frame the advance as first-run-only; keep the
  #6871/#7121 references accurate.

### T005 — Existing cases unchanged

Run, and do not edit the assertions of, the pre-existing cases:
`test_resume_with_nothing_landed_late_commits_nothing`,
`test_resume_with_an_unreadable_window_refuses_and_keeps_the_branch`,
`test_a_clean_first_run_projects_nothing`,
`test_first_run_does_not_approve_a_tip_that_moved_during_the_projection`,
`test_first_run_lands_a_coordination_commit_made_between_the_gate_and_teardown`,
`test_first_run_refuses_rather_than_skips_a_window_it_cannot_read`.

```bash
uv run --frozen pytest tests/coordination/test_projection_teardown.py -q -p no:randomly -n 4
```

## Branch Strategy

- Planning branch: `issue-7199-resume-late-coord-anchor`.
- Merge target: `issue-7199-resume-late-coord-anchor` (this Mission's topic branch; the PR targets
  `main`).
- Execution lanes come from `kitty-specs/fix-7199-resume-late-coord-anchor-01M6P3RN/lanes.json`;
  do not create a worktree by hand.

## Definition of Done

- T001 and T002 exist, T001 was red at the base commit, and both pass with the change.
- Only the one behavioural condition changed in `_land_late_coordination_commits`; no gate,
  refusal or assertion was weakened.
- `uv run --frozen ruff check <changed files>` and
  `uv run --frozen mypy src/specify_cli/consolidation/phase_teardown.py src/specify_cli/consolidation/run_state.py`
  are clean.
- Docstrings and the field comment describe the rule that the code implements.

## Risks

- Stamping a foreign tip approved: T002 is the guard; if it goes green without the
  compare-and-swap, the change is wrong.
- `_resolve_ref_sha` collapses "absent" and "unreadable" to `""`; the advance must not treat that
  as a match (it cannot — `projected_tip` is non-empty by then).

## Reviewer Guidance

- Confirm the diff is one condition plus prose, and that the `is_resume` early return for the
  *window* (which must stay resume-only) was not touched.
- Confirm T001's fixture really has an anchor older than the late commit (assert
  `tip != late`) and that the record's bytes are read from the target ref, not the working tree.
