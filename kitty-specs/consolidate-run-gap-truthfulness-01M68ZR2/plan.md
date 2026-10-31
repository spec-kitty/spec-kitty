# Implementation Plan: Consolidate run-gap truthfulness

**Branch**: `issue-6450-consolidate-run-gap-truthfulness` | **Date**: 2026-10-31 | **Spec**: `kitty-specs/consolidate-run-gap-truthfulness-01M68ZR2/spec.md`
**Input**: Mission specification from `kitty-specs/consolidate-run-gap-truthfulness-01M68ZR2/spec.md`

## Summary

Three independent message/persistence defects from #6450, each in an end-of-mission surface, each
fixed at its own seam with a red-first regression test:

1. **Consolidation leaves tracked deletions uncommitted** (item 4). `_remove_lane_worktrees`
   tombstones `.kittify/workspaces/<slug>-<lane>.json` **after** `_phase_commit_and_assert`, the
   run's only bookkeeping commit, so a tracked context leaves the target dirty. Fix: the cleanup
   phase commits the tombstones it made, through the existing `commit_merge_bookkeeping` seam, one
   scoped commit, none when nothing tracked was removed.
2. **Accept suggests a pull request on coordination topology** (item 6).
   `_build_acceptance_instructions`' `pr`/integration-branch arm tells the operator to push and open
   a pull request; on coordination topology the Mission lands through `spec-kitty consolidate`.
   Fix: the arm branches on the Mission's topology and names the consolidation.
3. **The `done` issue-matrix refusal prints a verdict remedy when every row has a verdict**
   (item 7). `issue_matrix_done_outcome` renders one header and one remedy for two different
   failure families. Fix: choose the header and the remedy by cause, keeping the FAIL decision
   identical for both families.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: `typer`, `rich`, `kernel.git`, `mission_runtime`
(`MissionArtifactKind`, placement), `specify_cli.git.bookkeeping_commit`
(`commit_merge_bookkeeping`), `specify_cli.workspace.delete_context`
**Storage**: git refs + `kitty-specs/<slug>/` JSON documents; `.kittify/workspaces/*.json` in the
consumer project's checkout (no database)
**Testing**: pytest — the existing merge-completion tombstone harness
(`tests/specify_cli/test_workspace_context_tombstone.py::_run_cleanup_phase`) extended with a real
git repo, plus the real-git coord fixtures in `tests/policy/test_merge_gates_issue_matrix.py` and
the unit helpers in `tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py`
**Target Platform**: Linux/macOS CLI (no OS-specific code)
**Project Type**: single project (Python CLI)
**Performance Goals**: at most one extra commit per consolidation run, none when no tracked
context was tombstoned (NFR-002)
**Constraints**: no new guarded commit call site (NFR-001); no gate decision changes (C-002); the
rewritten refusal stays within the size of the message it replaces (NFR-003)
**Scale/Scope**: 3 production modules (`consolidation/phase_teardown.py`,
`acceptance/__init__.py`, `tasks/issue_matrix_approval.py`), ~60 lines of production change,
~250 lines of test change, 3 test modules touched (2 existing + 1 new)

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Status | Note |
|---|---|---|
| Single canonical authority | PASS | The tombstone commit reuses `commit_merge_bookkeeping` (the one sanctioned protected-flow seam) and `workspace.delete_context`; the accept fix reuses the existing topology read; the message fix reuses the existing `_ISSUE_VERDICT_REMEDY` constant and only decides whether to print it. |
| Architectural alignment | PASS | No new module boundary; each change stays inside the package that already owns the surface. |
| ATDD-first / DIRECTIVE_034 | PASS | Every defect gets a failing test through its pre-existing entry point before the fix. |
| Terminology canon (Mission vs feature) | PASS | "coordination topology", "bookkeeping commit", "issue matrix", "terminal verdict" as already used in these modules. |
| DIRECTIVE_024 Locality of Change | PASS | One seam per item; no drive-by reformatting. |
| DIRECTIVE_025 Boy Scout Rule | PASS | The two message surfaces are corrected where they are produced, not wrapped by a caller. |
| DIRECTIVE_041 (test only real behaviour) | PASS | Each test asserts an observable outcome (a clean working tree, a rendered instruction list, a returned blocker) rather than call shape. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | PASS | Targeted suites only: `tests/specify_cli/test_workspace_context_tombstone.py`, `tests/consolidation/`, `tests/policy/test_merge_gates_issue_matrix.py`, `tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py`, acceptance regression tests. |
| Pre-existing Failure Reporting Rule | PASS | Pre-existing reds are cited in the PR, never skipped or xfailed. |

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/consolidate-run-gap-truthfulness-01M68ZR2/
├── plan.md                    # This file
├── research.md                # Discovery + grounding (D-01..D-04, evidence, open questions)
├── spec.md                    # Mission specification
├── issue-matrix.json          # One row for #6450 and its final verdict
├── traces/                    # approach.md, design-decisions.md, tooling-friction.md
├── tasks.md                   # /spec-kitty.tasks output
└── tasks/                     # Work-package files
```

### Source Code (repository root)

```
src/specify_cli/consolidation/
└── phase_teardown.py          # _remove_lane_worktrees: commit the tombstoned contexts it made

src/specify_cli/acceptance/
└── __init__.py                # _build_acceptance_instructions: topology-aware pr arm
                               # perform_acceptance: pass the topology fact in

src/specify_cli/tasks/
└── issue_matrix_approval.py   # issue_matrix_done_outcome: cause-dependent header + remedy

tests/specify_cli/
├── test_workspace_context_tombstone.py    # + tracked-context commit proof (real git repo)
└── test_acceptance_regressions.py         # + coord-topology guidance proof

tests/policy/test_merge_gates_issue_matrix.py   # + diagnostic-only refusal message proof
```

**Structure Decision**: single project; every change lands in the module that already owns the
surface being corrected. No new package, no new seam module.

## Implementation Concern Map

### IC-01 — Tombstoned workspace contexts are committed (item 4)

- **Purpose**: A landed consolidation leaves the target branch clean even when the project tracks
  `.kittify/workspaces/*.json`.
- **Relevant requirements**: FR-001, FR-002, SC-001, NFR-001, NFR-002
- **Affected surfaces**: `consolidation/phase_teardown.py::_remove_lane_worktrees` (collect the
  contexts it actually unlinked, drop untracked ones, commit the rest through
  `commit_merge_bookkeeping` with the resolved target as destination)
- **Sequencing/depends-on**: none
- **Risks**: (a) committing an untracked/deleted-from-index path would fail `safe_commit` — the
  path set must be filtered to paths that are tracked at the pre-run commit; (b) a failure here
  must not fail a landed merge — warn, keep the run's existing behaviour, and never claim a clean
  tree.

### IC-02 — Accept guidance follows the landing path (item 6)

- **Purpose**: An operator accepting a coordination-topology Mission is pointed at
  `spec-kitty consolidate`, never at a pull request.
- **Relevant requirements**: FR-003, FR-004, SC-002
- **Affected surfaces**: `acceptance/__init__.py::_build_acceptance_instructions`,
  `perform_acceptance` (compute the topology fact once, from the same meta read the target-branch
  decision already uses)
- **Sequencing/depends-on**: none
- **Risks**: the `pr`/integration-branch arm is shared with flat topologies; the change must be
  gated on the topology so the existing sentence survives for them (FR-004 positive control).

### IC-03 — The `done` refusal names its cause (item 7)

- **Purpose**: The verdict-recording remedy is printed only when a verdict is actually missing or
  unresolved; a diagnostic-only failure names the diagnostics.
- **Relevant requirements**: FR-005, FR-006, SC-003, SC-004, NFR-003
- **Affected surfaces**: `tasks/issue_matrix_approval.py::issue_matrix_done_outcome`
- **Sequencing/depends-on**: none
- **Risks**: the existing pins on "has unresolved entries" / "Fill in verdicts before done." for
  the missing/in-mission families must keep passing unchanged — the new arm is only reached when
  `missing_issues` and `unresolved_in_mission` are both empty.

### IC-04 — Changelog and the docs the behaviour touches

- **Purpose**: Record the user-facing change and update the recovery/how-to prose that describes
  consolidation teardown and acceptance next steps.
- **Relevant requirements**: C-003
- **Affected surfaces**: `docs/changelog/CHANGELOG.md` (`[Unreleased]`, `(#6450)` reference), the
  consolidation/recovery docs that mention workspace-context tombstones or accept next steps
- **Sequencing/depends-on**: IC-01..IC-03 (the entry describes what landed)
- **Risks**: the docs index must be regenerated only if a page is added; prefer editing existing
  pages so `check_docs_freshness --ci` stays clean.

## Phase 0 / Phase 1 notes

Phase 0 research is `research.md` (discovery, grounding on `dfe9efb0e8`, decisions D-01..D-04,
open questions Q-01..Q-03 with their resolutions). Phase 1 design artifacts are not separately
scaffolded for `software-dev`; the entities the work needs (workspace context, bookkeeping commit,
acceptance instruction list, issue-matrix refusal) are already named in `spec.md` "Key Entities"
and in the concern map above. No new data model is introduced, which is why `data-model.md` and
`contracts/` are absent rather than empty.
