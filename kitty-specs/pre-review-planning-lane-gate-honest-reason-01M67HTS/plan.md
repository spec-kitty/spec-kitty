# Implementation Plan: An honest pre-review gate reason for a planning-lane WP

**Branch**: `issue-6792-planning-lane-gate-honest-reason` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/pre-review-planning-lane-gate-honest-reason-01M67HTS/spec.md`

## Summary

The `for_review` pre-review gate short-circuits on an empty changed-file set
(`tasks_move_task_gates.py:1039`) and records "no changed files detected for this
WP". For a `planning_artifact` WP the changed-file set is empty *by
construction* — the WP's workspace is the checkout that already sits on the
target branch, so the merge-base diff against that branch is empty and a
committed, clean tree adds no dirty paths ([research.md](research.md), D-1). The
plan fixes the record, not the gate: before falling back to the empty-diff
wording, the short-circuit asks the existing planning-lane authorities whether
this WP is a planning-lane WP, and if so records a reason that names the
planning lane and states that the committed diff was not inspected. Outcome,
dispatch, blocking semantics and the non-planning wording are unchanged.

## Technical Context

**Language/Version**: Python 3.11+ (project floor `>=3.11`; CI also runs 3.13)
**Primary Dependencies**: stdlib only for this change (`pathlib`, `dataclasses` already in the module); no new package
**Storage**: N/A — reads the mission's `lanes.json` (`kitty-specs/<mission>/lanes.json`) and WP frontmatter
**Testing**: pytest; a real git repository fixture (branch = mission target branch) driving the production `move-task --to for_review` entry point through Typer's `CliRunner`, plus the existing pre-review gate modules
**Target Platform**: Linux/macOS developer hosts and CI (`spec-kitty` CLI)
**Project Type**: single project — CLI package `src/specify_cli/`
**Performance Goals**: the new classification adds at most one frontmatter scalar read and at most one `lanes.json` read; no git subprocess, no test run (NFR-001)
**Constraints**: non-blocking `no_coverage` outcome preserved; no new CLI flag/config/env/dependency; no gate weakened or silenced (NFR-002, C-001, C-003)
**Scale/Scope**: one production module (`tasks_move_task_gates.py`), one new focused test module, one how-to doc paragraph, one changelog entry

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — planning-lane identity is asked through
  `specify_cli.lanes.compute.is_planning_lane` (the documented seam, whose
  docstring forbids comparing the `PLANNING_LANE_ID` literal) and
  `WorkProductKind.PLANNING_ARTIFACT` (the existing execution-mode authority used
  by `_is_confined_planning_wp`). `lanes.json` is read through
  `lanes.persistence.read_lanes_json` at the `placement_seam(...).read_dir(
  MissionArtifactKind.LANE_STATE)` location — the same reader and the same
  placement seam the workspace resolver uses. No second reader, no new literal:
  PASS.
- **Architectural alignment / locality of change** — the edit lands inside the
  gate seam that already owns the string, next to the short-circuit it explains;
  no cross-package boundary moves: PASS.
- **ATDD-first / red-first** — the reproduction test is written against the real
  `move-task` entry point and run red before the production edit: PASS (see
  Tasks).
- **Test policy (`NO_FULL_HEAVY_SUITES_IN_MISSION`)** — targeted modules only;
  no whole-repo sweep: PASS.
- **Pre-existing Failure Reporting Rule** — any red outside this diff is
  classified and cited, never skipped: PASS.
- **Terminology Canon** — "Mission", "work package", `planning_artifact`,
  `lane-planning` are used as canonical values; the new operator-facing string
  names no retired term: PASS.

No violations; **Complexity Tracking** is therefore intentionally empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/pre-review-planning-lane-gate-honest-reason-01M67HTS/
├── spec.md              # Mission specification
├── research.md          # Discovery + Phase 0 decisions (D-1 … D-6)
├── plan.md              # This file
├── reasons-canvas.md    # SPDD/REASONS canvas
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/
├── cli/commands/agent/
│   └── tasks_move_task_gates.py   # EDIT: reason selection for the empty-diff arm
├── lanes/
│   ├── compute.py                 # READ-ONLY authority: is_planning_lane
│   └── persistence.py             # READ-ONLY authority: read_lanes_json
└── ownership/models.py            # READ-ONLY authority: WorkProductKind.PLANNING_ARTIFACT

tests/specify_cli/cli/commands/agent/
├── test_tasks_move_task_pre_review_planning_lane_reason.py   # NEW: reproduction + control
├── test_tasks_move_task_pre_review_gate_observability.py     # must stay green, unmodified
└── test_tasks_move_task_pre_review_gate_escape_hatch.py      # must stay green, unmodified

docs/
├── development/how-to/review-gates.md    # EDIT: state the planning-lane reason
└── changelog/CHANGELOG.md                # EDIT: [Unreleased] entry (#6792)
```

**Structure Decision**: single-project CLI layout. The production edit is
confined to `src/specify_cli/cli/commands/agent/tasks_move_task_gates.py` (the
gate seam that owns the string); the authorities it consults
(`lanes/compute.py`, `lanes/persistence.py`, `ownership/models.py`) are imported,
never modified. Tests live beside the existing pre-review gate modules so the
blast-radius run is a directory-scoped command.

**Interface sketch** (internal, not a public contract; the shipped names are the
source of truth in `tasks_move_task_gates.py`):

```python
_PRE_REVIEW_NO_CHANGED_FILES_REASON = "no changed files detected for this WP — skipping the gate cheaply"
_PRE_REVIEW_PLANNING_LANE_REASON = (
    "planning-lane WP — committed diff not inspected (a planning_artifact WP commits on the target branch, so no workspace diff exists)"
)

def _mt_declared_execution_mode(st: _MoveTaskState) -> str: ...
def _mt_lanes_manifest_marks_planning_artifact(st: _MoveTaskState) -> bool: ...
def _mt_pre_review_planning_lane_wp(st: _MoveTaskState) -> bool: ...
def _mt_empty_changed_files_reason(st: _MoveTaskState) -> str: ...
```

`_mt_empty_changed_files_reason` returns the incumbent literal unless
`_mt_pre_review_planning_lane_wp` is true, so the non-planning path is
byte-identical to today.

## Complexity Tracking

*No Charter Check violations — intentionally empty.*

## Implementation Concern Map

### IC-01 — The planning-lane classification and the reason it selects

- **Purpose**: replace one false sentence with a true one for exactly the WP
  shape that produces it, using the authorities that already decide planning-lane
  identity.
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-001, NFR-003, C-001,
  C-002.
- **Affected surfaces**: `src/specify_cli/cli/commands/agent/tasks_move_task_gates.py`
  (`_mt_collect_transition_gate_verdicts` empty-diff arm + the new helpers);
  read-only imports from `lanes/compute.py`, `lanes/persistence.py`,
  `ownership/models.py`.
- **Sequencing/depends-on**: none.
- **Risks**: a classification that guesses from lane membership alone would
  mislabel a `single_branch` mission's repo-root **code** WP (documented in
  `workspace/context._resolve_repo_root_lane_arm`); the declared
  `execution_mode` therefore wins, and lane membership is only the fallback when
  the frontmatter is silent. A corrupt/absent `lanes.json` must degrade to
  today's wording, never raise.

### IC-02 — Red-first reproduction and the same-fixture control

- **Purpose**: prove the fix where the operator sees it (the recorded verdict)
  and prove it did not spread (the code-change control), on one fixture.
- **Relevant requirements**: FR-003, FR-004, SC-001 … SC-004.
- **Affected surfaces**: new
  `tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_planning_lane_reason.py`.
- **Sequencing/depends-on**: IC-01 (test may be authored first and run red).
- **Risks**: a fixture that patches `_mt_pre_review_changed_files` would not
  reproduce the reported shape; the fixture must use a real git repo whose HEAD
  is the target branch, so the empty diff is produced by git, not by a mock.
  Dispatch must be observable (spy) to assert the cheap skip still costs nothing.

### IC-03 — The operator-facing record

- **Purpose**: the changelog and the review-gates how-to must describe what the
  record now says, so the next maintainer reading gate output is not surprised by
  the new wording.
- **Relevant requirements**: FR-001, NFR-003.
- **Affected surfaces**: `docs/development/how-to/review-gates.md`,
  `docs/changelog/CHANGELOG.md` ([Unreleased]).
- **Sequencing/depends-on**: IC-01.
- **Risks**: the how-to already carries the inherited-limitation note (#2741) —
  the new paragraph must extend it, not contradict it, and must not claim the
  gate now inspects the committed diff.
