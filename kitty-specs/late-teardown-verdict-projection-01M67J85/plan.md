# Implementation Plan: Late teardown verdict projection

**Branch**: `issue-6791-late-teardown-verdict-projection` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/late-teardown-verdict-projection-01M67J85/spec.md`
**Input**: Mission specification from `kitty-specs/late-teardown-verdict-projection-01M67J85/spec.md`

## Summary

`consolidate --resume`'s late-teardown projection (#5570) drops an `issue-verdict` commit because
its path selector (`_post_checkpoint_mission_paths`) excludes the two gate-matrix kinds. That
exclusion protects the *mid-merge* window, where the coordination ref holds a stale
finalize-time placeholder and `accept` authored the real fill on the primary surface. In the
*post-teardown* window every commit is newer than the target's copy, so the exclusion silently
destroys operator work.

The fix is scoped to the late window, in three parts:

1. **Project the gate matrices** in that window (a dedicated seam-stage call, not a change to the
   mid-merge selector whose output feeds the reconciliation squash proof).
2. **Guard the projection** so it never loses or downgrades an established judgement the target
   already holds (terminal issue verdicts; `pass` acceptance criteria; terminal negative-invariant
   results), and never expresses a deletion.
3. **Prove the window landed** after the projection commit and before the branch delete: every
   coordination record changed in `pre_mutation_coord_sha..coord-tip` must be byte-identical on the
   target, or the run refuses with the branch, worktree and marker intact.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: `typer`, `rich`, `kernel.git` (`changed_paths`, `run_git`), `mission_runtime`
(`kind_for_mission_file`, `MissionArtifactKind`), `specify_cli.coordination.coherence`
**Storage**: git refs + `kitty-specs/<slug>/` JSON/YAML documents (no database)
**Testing**: pytest — real-CLI integration fixtures (`tests/terminus/conftest.build_coord_mission`,
`run_terminus`) for the end-to-end refusal/resume path, plus seam-level unit tests
**Target Platform**: Linux/macOS CLI (no OS-specific code)
**Project Type**: single project (Python CLI)
**Performance Goals**: no measurable change; the window walk is bounded by the paths changed in a
handful of coordination commits (NFR-001)
**Constraints**: mid-merge projection path set must stay byte-identical (C-001); no new writer, no
new commit seam (NFR-003)
**Scale/Scope**: 2 modules touched (`consolidation/bookkeeping_projection.py`,
`consolidation/phase_teardown.py`), ~250 lines of production change, 1 new test module

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Status | Note |
|---|---|---|
| Single canonical authority | PASS | Reuses `is_coordination_kind_file` / `kind_for_mission_file` for classification, `IssueMatrixVerdict`'s documented terminal set, and the existing `commit_merge_bookkeeping` seam. No parallel classifier, no new writer. |
| Architectural alignment | PASS | Change stays inside `specify_cli.consolidation`; the placement seam and `mission_runtime` are read-only imports. |
| ATDD-first / DIRECTIVE_034 | PASS | The red test drives the real CLI through the pre-existing refusal→resume entry point before the fix exists. |
| Terminology canon (Mission vs feature) | PASS | Uses "coordination branch", "coordination record", "gate matrix", "late window" as already used in the module docstrings. |
| DIRECTIVE_024 Locality of Change | PASS | Two modules, both already own the late-window projection. |
| DIRECTIVE_041 (test only real behaviour) | PASS | Each added test asserts an observable landing/refusal outcome, not internal call shape. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | PASS | Targeted suites only: `tests/consolidation/`, `tests/coordination/`, plus the touched-module unit tests. |
| Pre-existing Failure Reporting Rule | PASS | Any pre-existing red is cited in the PR, never papered over. |

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/late-teardown-verdict-projection-01M67J85/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 grounding (reproduction, decisions D1–D5)
├── spec.md              # Mission specification
├── tasks.md             # /spec-kitty.tasks output
└── tasks/               # Work-package files
```

### Source Code (repository root)

```
src/specify_cli/consolidation/
├── bookkeeping_projection.py   # + late-window gate-matrix projection, evidence-preservation
│                               #   guard, late-window completeness assertion
└── phase_teardown.py           # _land_late_coordination_commits: call the new stage, wrap its
                                #   refusal as CoordinationTeardownError (branch kept)

tests/consolidation/
├── test_issue_6791_late_verdict_projection.py   # NEW: real-CLI repro + guard/refusal cases
└── test_teardown_refusal_resume.py              # existing #5965 fixture family (reused)
```

**Structure Decision**: single project; the change is a window-scoped fix inside the existing
consolidation package, so no new package or module boundary is introduced.

## Implementation Concern Map

### IC-01 — Late-window gate-matrix projection

- **Purpose**: Carry a gate-matrix commit made after a teardown refusal onto the target instead of
  deleting it with the coordination branch.
- **Relevant requirements**: FR-001, FR-005, NFR-001, NFR-003, C-001
- **Affected surfaces**: `consolidation/bookkeeping_projection.py`
  (new `project_late_gate_matrix_commits`, a `include_gate_matrices` widening of the window path
  selector), `consolidation/phase_teardown.py::_land_late_coordination_commits`
- **Sequencing/depends-on**: none
- **Risks**: the mid-merge selector is shared; widening it by default would change the
  reconciliation squash proof. Keep the widening opt-in and default-off.

### IC-02 — Evidence-preservation guard

- **Purpose**: Refuse a projection that would lose or downgrade an established judgement the target
  already holds, so lifting the exclusion cannot regress accepted evidence.
- **Relevant requirements**: FR-004, FR-005, SC-004, NFR-002
- **Affected surfaces**: `consolidation/bookkeeping_projection.py` (kind-aware established-judgement
  map + `LateProjectionRefused`)
- **Sequencing/depends-on**: IC-01 (same call site)
- **Risks**: a second terminal-set definition would drift from the gate; derive the terminal set
  from `IssueMatrixVerdict` and the acceptance matrix's documented verdict constants.

### IC-03 — Whole-window completeness proof and refusal

- **Purpose**: After projecting, prove every coordination record changed in the late window reached
  the target; refuse (keeping branch/worktree/marker) otherwise, so no future exclusion hole can
  silently drop a commit.
- **Relevant requirements**: FR-002, FR-003, SC-002, SC-003
- **Affected surfaces**: `consolidation/bookkeeping_projection.py`,
  `consolidation/phase_teardown.py::_land_late_coordination_commits`
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: the status pair is owned by the union/rematerialize stage that runs *after* this one —
  exclude it by its canonical filename constants rather than by "kind", and assert on the working
  tree of the target checkout (which is where the projection writes).

### IC-04 — Red-first proof and documentation

- **Purpose**: Land the reproduction as a regression test through the real CLI, and record the
  user-facing change in the changelog plus the docs the behaviour touches.
- **Relevant requirements**: SC-001, SC-003, DIRECTIVE_034
- **Affected surfaces**: `tests/consolidation/test_issue_6791_late_verdict_projection.py`,
  `docs/changelog/CHANGELOG.md`, the consolidation docs that describe `--resume` teardown recovery
- **Sequencing/depends-on**: IC-01..IC-03 for the green assertion; the red commit lands first
- **Risks**: the fixture must produce a real `issue-verdict` commit (not a hand-written matrix) or
  the test would not guard the production writer path.

## Phase 0 / Phase 1 notes

Phase 0 research is `research.md` (discovery + reproduction + decisions D1–D5). Phase 1 design
artifacts are not separately scaffolded for this mission type; the data model (late window,
coordination record, gate matrix) and the seam contract are captured in `spec.md` "Key Entities"
and in this plan's concern map.
