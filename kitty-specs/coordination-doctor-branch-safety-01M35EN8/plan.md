# Implementation Plan: Coordination Doctor Branch Safety

**Branch**: `issue-4920-coordination-doctor-branch-safety` | **Date**: 2026-09-22 | **Spec**: `spec.md`
**Input**: Mission specification from `kitty-specs/coordination-doctor-branch-safety-01M35EN8/spec.md`

## Summary

Close issue #4920 by inserting the existing symbolic-HEAD branch identity check into
the `doctor coordination --fix` mutation path, converting a mismatch into the existing
structured blocked-fix error, and verifying the declared coordination ref reached the
target before printing success. Drive the change with a real-Git red-first acceptance
test that proves every involved ref is unchanged on refusal.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Typer, Git subprocess boundary, existing coordination workspace resolver  
**Storage**: Git refs and existing mission `meta.json`; no schema or persisted-data change  
**Testing**: pytest real-git integration contract plus owning subsystem and repository fast gate  
**Target Platform**: Linux, macOS, Windows 10+ with Git >= 2.25  
**Project Type**: Python CLI  
**Performance Goals**: One additional local `git symbolic-ref` precondition and one `git rev-parse` postcondition per eligible mission  
**Constraints**: Zero unintended ref mutation; no branch switching/reset; preserve multi-mission continuation  
**Scale/Scope**: Two production/test files plus mission artifacts; one work package

## Charter Check

| Gate | Plan response | Status |
|------|---------------|--------|
| Single canonical authority | Reuse `_coord_worktree_head_finding` and existing blocked-fix finding; add no duplicate resolver or error family. | PASS |
| ATDD-first | Commit the real-git #4920 regression while it is red, before source changes. | PASS |
| Campsite cleaning | The touched helper is cohesive and under the complexity ceiling; no domain-matched cleanup is needed before the functional change. | PASS |
| Minimal/local change | Limit production changes to `_coordination_doctor.py` and acceptance coverage to its existing owning test. | PASS |
| Git/workflow | Issue branch and PR to `main`; implementer does not merge. | PASS |
| Mission hygiene | #4920 is assigned, claimed, named in tracker comments, and recorded in `issue-matrix.md`; implement and review use distinct loaded profiles. | PASS |
| Tracer files | Seeded at plan time and appended through implementation/review/closeout. | PASS |

## Design

### Mutation precondition

After resolving the mission worktree and before dirty-state validation, call
`_coord_worktree_head_finding(worktree, coord_branch)`. A non-`None` result means the
mutation is unauthorized at that path. Translate it to
`_coord_staleness_fix_blocked_finding` with a reason that names the actual branch
mismatch. Returning a finding preserves the existing behavior where other mission
fixes continue.

### Mutation postcondition

After `git merge --ff-only`, re-read `refs/heads/<coord_branch>`. Print success only if
that SHA equals the previously resolved target SHA. If it does not, return a structured
blocked-fix error describing the failed postcondition. This is defensive against a
concurrent or unexpected Git state change and prevents false success.

### Error semantics

Keep the stable `COORDINATION_BRANCH_STALE_FIX_BLOCKED` machine code. The reason text
must include the branch mismatch or postcondition failure. This avoids expanding the
public error vocabulary for a new precondition of the same refused repair operation.

## Test Design

1. Extend the existing real-git fixture with a third branch checked out in the recorded
   worktree while the declared coordination branch remains stale.
2. Run `run_coordination_health(fix=True)` through the pre-existing command entry point.
3. Assert exit 1; blocked-fix code; mismatch detail; no `Fast-forwarded` text.
4. Assert the declared coordination ref, wrong checked-out ref, worktree `HEAD`, and
   target ref equal their pre-command SHAs.
5. Run the existing correct-branch control unchanged to prove safe recovery.

## Project Structure

### Documentation

```text
kitty-specs/coordination-doctor-branch-safety-01M35EN8/
├── spec.md
├── research.md
├── data-model.md
├── plan.md
├── quickstart.md
├── issue-matrix.md
├── tracer-approach.md
├── tracer-design-decisions.md
├── tracer-tooling-friction.md
├── tasks.md
└── tasks/
    └── WP01-guard-coordination-fix-branch.md
```

### Source and tests

```text
src/specify_cli/cli/commands/_coordination_doctor.py
tests/coordination/test_coord_staleness.py
```

**Structure Decision**: Keep the fix in the existing coordination doctor adapter and
its established real-Git contract. No new module, API, or dependency is justified.

## Implementation Concern Map

### IC-01 — Fail-closed repair identity

- **Purpose**: Prevent the repair subprocess from mutating any branch except the
  declared coordination ref.
- **Relevant requirements**: FR-001, FR-002, NFR-001, NFR-002, C-001, C-002, C-003
- **Affected surfaces**: `_coordination_doctor.py`, `test_coord_staleness.py`
- **Sequencing/depends-on**: none
- **Risks**: Error wording must remain useful without adding a second branch detector.

### IC-02 — Truthful successful repair

- **Purpose**: Tie the success message to the declared ref's verified postcondition.
- **Relevant requirements**: FR-003, FR-004, NFR-003
- **Affected surfaces**: `_coordination_doctor.py`, `test_coord_staleness.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: Do not weaken or replace the existing correct-branch fast-forward control.

## Verification

- Red-first: new #4920 acceptance test fails on `origin/main` behavior.
- Focused: `uv run --extra test pytest -q tests/coordination/test_coord_staleness.py`.
- Owning subsystem: `uv run --extra test pytest -q tests/coordination`.
- Shared baseline: `make test-fast`.
- Quality: targeted Ruff, formatter check, and strict MyPy for the changed source.
- Diff review: no unrelated files, no new suppressions, no legacy terminology.

## Complexity Tracking

No charter violation or architectural exception is planned.
