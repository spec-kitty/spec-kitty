# Implementation Plan: Terminality gate judges every issue-matrix row

**Branch**: `issue-6653-terminality-all-rows` | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)
**Input**: `kitty-specs/issue-matrix-terminality-all-rows-01M5X1ZJ/spec.md`; research in [research.md](research.md).

## Summary

At `done`, the issue-matrix blocker and the `issue_matrix_verdict_terminality` merge gate judge every row, not only rows whose issue is a discovered gating reference. When a matrix exists, the whole matrix is judged (diagnostics and `in-mission` rows), even with zero gating references. A Mission with no authored matrix still needs none. On the coordination ref read, the case "matrix absent at a valid ref" gets its own typed code, `ISSUE_MATRIX_NOT_AUTHORED`, so it is not mistaken for a failed probe, and every other read error still fails closed. A PASS reports what was judged. `approved` behaviour and the completeness gate are unchanged.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml, git CLI (no dependency added, upgraded or removed; DIRECTIVE_051 not triggered)
**Storage**: issue-matrix artifacts in git (`issue-matrix.json` with the legacy `issue-matrix.md` failover) on the primary or coordination partition
**Testing**: pytest (real git repositories, built with the fixtures of `tests/policy/test_merge_gates_issue_matrix.py`)
**Target Platform**: spec-kitty CLI on Linux, macOS and Windows
**Project Type**: single project
**Performance Goals**: NFR-001. A zero-ref Mission with no matrix costs at most two object-presence probes and no content read.
**Constraints**: C-001 to C-005 in spec.md; complexity ≤ 15; ruff, ruff format and mypy clean
**Scale/Scope**: about four source files and three test files, plus docs

## Charter Check

- **Single canonical authority**: the "absent at a valid ref" fact is added to the existing reader, `read_issue_matrix_ref_content`, as a typed code. No second reader is added (C-004, Decision `01M5X498X3ATTAB12KQWMDPZRV`). PASS.
- **Architectural alignment**: `mission_runtime` gains the code; `specify_cli` consumes it. The import direction `mission_runtime <- specify_cli` is unchanged. PASS.
- **ATDD / red-first**: each WP starts with failing tests through the pre-existing entry points (`evaluate_merge_gates`, `_issue_matrix_approval_blocker`, `read_issue_matrix_ref_content`), committed before the fix. PASS.
- **Terminology**: Mission, work package, issue-matrix; no `feature` wording in new text. PASS.
- **NO_FULL_HEAVY_SUITES_IN_MISSION**: targeted tests plus `make test-fast` only. PASS.
- **Standing Order #8 (mission hygiene)**: #6653 gets an issue-matrix row in this Mission. PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/issue-matrix-terminality-all-rows-01M5X1ZJ/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks/
```

### Source Code (repository root)

```
src/mission_runtime/resolution.py                # read_issue_matrix_ref_content + new NOT_AUTHORED leg
src/specify_cli/tasks/issue_matrix_approval.py   # _issue_matrix_in_mission_rows, _issue_matrix_approval_blocker
src/specify_cli/policy/merge_gates.py            # _evaluate_issue_matrix_verdict_terminality_gate
docs/adr/4.x/2026-10-26-1-done-judges-every-issue-matrix-row.md   # new decision record
docs/development/reference/issue-matrix-verdicts.md               # "What `done` enforces"
docs/changelog/CHANGELOG.md
tests/mission_runtime/ (reader tests; exact file chosen at task time)
tests/policy/test_merge_gates_issue_matrix.py
tests/specify_cli/... move-task done-gate tests (located at task time by grep)
```

**Structure Decision**: single project; changes stay in the three owning modules above.

## Complexity Tracking

None.

## Implementation Concern Map

### IC-01 — Typed "not authored" leg on the coord ref reader

- **Purpose**: let callers tell "the matrix file is absent at a valid ref" (both `.json` and `.md`) apart from a deleted ref, an unreadable object or a git failure.
- **Relevant requirements**: FR-003, FR-004, NFR-001, NFR-002, C-004
- **Affected surfaces**: `src/mission_runtime/resolution.py` (`_ISSUE_MATRIX_NOT_AUTHORED_CODE`; after the `.md` failover's probe error, an object-presence check through `lifecycle_phase`'s valid-rev-then-path discipline; a positive absence raises NOT_AUTHORED, and anything else keeps PROBE_ERROR).
- **Sequencing/depends-on**: none
- **Risks**: callers that catch `IssueMatrixRefReadError` and branch on `code` must keep failing closed for the gating-ref case. A caller that matches `PROBE_ERROR` exactly would now see a new code: audit every `.code ==` use.

### IC-02 — Done judges every row

- **Purpose**: collect `in-mission` rows over all rows at `done`. With zero gating refs, judge a present matrix and treat a missing one as nothing to enforce.
- **Relevant requirements**: FR-001, FR-002, FR-006, C-001, C-002, C-003
- **Affected surfaces**: `src/specify_cli/tasks/issue_matrix_approval.py`
- **Sequencing/depends-on**: none (dir-based presence only)
- **Risks**: the blocker also serves `approved`. The zero-refs early return must stay in force for every non-DONE target (C-001).

### IC-03 — Gate reads the matrix with zero refs and reports what it judged

- **Purpose**: replace the zero-refs PASS in the terminality gate with a partition read that maps NOT_AUTHORED to "nothing to enforce", and make the PASS detail name the judged row count.
- **Relevant requirements**: FR-002, FR-003, FR-005, SC-001, SC-003
- **Affected surfaces**: `src/specify_cli/policy/merge_gates.py`, plus a row-count accessor in `issue_matrix_approval.py`
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: #5222 F1. A fresh coord Mission (coordination worktree materialized, no matrix) must take the dir-based path and PASS. The completeness gate's zero-refs early return stays as it is (C-002).

### IC-04 — Decision record, reference doc, changelog

- **Purpose**: record what `done` enforces and the accepted behaviour change.
- **Relevant requirements**: FR-007, C-005
- **Affected surfaces**: `docs/adr/4.x/`, `docs/development/reference/issue-matrix-verdicts.md`, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-02, IC-03
- **Risks**: the docs freshness date and the Divio type frontmatter.
