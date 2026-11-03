# Implementation Plan: A lane window that was never created names the shape it is in

**Branch**: `issue-7120-lane-window-never-created` | **Date**: 2026-11-03 | **Spec**: `kitty-specs/lane-window-never-created-recovery-01M6GRJ5/spec.md`
**Input**: Mission specification from `kitty-specs/lane-window-never-created-recovery-01M6GRJ5/spec.md`

## Summary

A `lanes`/`coord` Mission whose work packages were implemented on the target/topic branch has no
lane branches and never will, so the implementation-evidence window
`planning_commit..<lane branch>` cannot be diffed. Today every diff failure reaches the operator as
the same sentence ending in "Make the lane branch and the recorded planning commit readable, then
retry", which cannot be carried out. This Mission makes the refusal state the shape it detected —
the lane branch is absent, and if no lane of the Mission has a branch, the Mission ran on its
target branch — and the honest next step: report the shape, because what evidence such a Mission
may land on is exactly the open ruling on #7120, and constructing the branch now would fabricate
the evidence the gate checks.

No evidence window widens. `IMPLEMENTATION_UNREADABLE` keeps its code, meaning and machine
contract; only its human text gains the distinction. The absence probe and the cause text live in
`consolidation/wp_evidence.py`, which both refusing surfaces already call (`move-task` and
`accept`/`consolidate` through `evaluate_evidence`).

## Technical Context

**Language/Version**: Python 3.11+ (repository standard)
**Primary Dependencies**: `subprocess`/git for the ref probe; no new dependency
**Storage**: N/A (git refs and the Mission's `lanes.json`/`meta.json` are read, nothing is written)
**Testing**: pytest; unit tests with a real temporary git repository for the probe, one
integration test driving the real CLI for the end-to-end shape
**Target Platform**: the `spec-kitty` CLI on any OS git supports
**Project Type**: single Python package (`src/specify_cli`)
**Performance Goals**: zero added git calls on the passing path; at most one `git show-ref` per
absent candidate (plus one per further lane, only to classify the shape) on the failure path
**Constraints**: no new evidence code, no new CLI flag, no config key, no exit-code change; fail
closed on every unreadable probe
**Scale/Scope**: 2 source modules, ~2 tests files plus one integration file, 1 doc page, 1 changelog
fragment

## Charter Check

*GATE: pass before implementation.*

- **Single canonical authority** — satisfied by putting the probe and the text in
  `wp_evidence.py` (C-002), the module the axis already owns.
- **ATDD-first / red-first** (charter §ATDD-First Discipline, DIRECTIVE_034) — the new tests are
  written against the pre-existing entry points (`_mt_require_implementation_evidence`,
  `evaluate_evidence`, and the real `move-task` CLI) and fail before the fix.
- **change-apply-smallest-viable-diff / DIRECTIVE_024 locality** — one code path per surface, no
  refactor of neighbouring refusal lines.
- **No weakening of a gate** (C-001, NFR-002) — every existing refusal still refuses; the change is
  text plus one read-only probe. The evidence-window policy decision stays with the operator on
  #7120.
- **Terminology canon** — "lane branch", "evidence window", "Mission", "work package" used in
  their canonical senses; no `feature*` vocabulary.

## Project Structure

### Documentation (this mission)

```
kitty-specs/lane-window-never-created-recovery-01M6GRJ5/
├── plan.md              # this file
├── spec.md              # mission specification
├── tasks.md             # work-package index (tasks step)
├── tasks/               # one file per work package
└── traces/              # approach, design-decisions, tooling-friction
```

### Source Code (repository root)

```
src/specify_cli/
├── consolidation/
│   └── wp_evidence.py                 # branch_ref_absent (public), absent-lane-window cause,
│                                      # _unreadable_line, _RECOVERY
└── cli/commands/agent/
    └── tasks_move_task.py             # _mt_require_lane_evidence: probe on the failure path,
                                       # use the shared cause for an absent tip

tests/
├── consolidation/
│   └── test_wp_evidence.py            # absent-tip cause lines (never-created, pruned, unreadable)
├── specify_cli/cli/commands/agent/
│   └── test_move_task_evidence_gate.py # the move gate: absent lane branch, live-lane sibling,
                                        # present-but-unreadable (unchanged)
└── integration/
    └── test_7120_lane_window_never_created.py  # real CLI, the #7120 fixture end to end

docs/
├── api/orchestrator-api.md            # the IMPLEMENTATION_UNREADABLE recovery row
└── changelog/unreleased/<pr>.fixed.md # per-PR fragment
```

**Structure Decision**: extend the two existing modules the issue names; no new module, no new
package. The one new test file is the end-to-end CLI proof for the shape the issue recorded.

## Complexity Tracking

No charter violations. The one policy-adjacent question (may a `lanes` Mission be judged on its
target-branch window?) is deliberately **not** answered here; see `## Deferred` in the PR body and
#7120.

## Implementation Concern Map

### IC-01 — The absence probe and its classification

- **Purpose**: decide, on the failure path only, whether the window tip is a branch ref that is
  truly absent, and whether the Mission has any lane branch at all.
- **Relevant requirements**: FR-001, FR-002, FR-007, NFR-001, NFR-002
- **Affected surfaces**: `src/specify_cli/consolidation/wp_evidence.py`
  (`branch_ref_absent`, the never-created classifier, `_unreadable_line`)
- **Sequencing/depends-on**: none
- **Risks**: `git show-ref --verify` returns 128 for every non-absence failure; only exit 1 may be
  read as absent (#6780's rule). The classifier must not treat a planning lane's target-branch tip
  as a missing lane branch.

### IC-02 — The refusal texts on both surfaces

- **Purpose**: put the shape and the honest next step into the `IMPLEMENTATION_UNREADABLE` text at
  `move-task` (the quoted refusal) and in the shared recovery table, without changing any code or
  verdict.
- **Relevant requirements**: FR-003, FR-004, FR-005, FR-006, FR-008, NFR-003
- **Affected surfaces**: `src/specify_cli/consolidation/wp_evidence.py` (`_RECOVERY`),
  `src/specify_cli/cli/commands/agent/tasks_move_task.py` (`_mt_require_lane_evidence`)
- **Sequencing/depends-on**: IC-01
- **Risks**: `tests/consolidation/test_wp_evidence_recovery_wording.py` (PR #7124) pins facts about
  the `IMPLEMENTATION_MISSING`/`REVIEW_NOT_INDEPENDENT` rows only; the unreadable row is free to
  gain a clause but must keep naming a step an operator can run.

### IC-03 — Proof: red tests, the CLI shape, and the docs surface

- **Purpose**: prove the loop stops through the pre-existing entry points, and leave the operator
  documentation agreeing with the new text.
- **Relevant requirements**: FR-009, C-003, SC-001, SC-002, SC-003
- **Affected surfaces**: `tests/consolidation/test_wp_evidence.py`,
  `tests/specify_cli/cli/commands/agent/test_move_task_evidence_gate.py`,
  `tests/integration/test_7120_lane_window_never_created.py`, `docs/api/orchestrator-api.md`,
  `docs/changelog/unreleased/<pr>.fixed.md`
- **Sequencing/depends-on**: IC-02
- **Risks**: the integration case builds a real Mission; keep it one case with a documented
  timeout, and do not let it drift into the heavier #6715 fixtures' scope.
