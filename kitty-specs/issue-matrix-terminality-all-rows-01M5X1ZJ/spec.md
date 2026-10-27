# Mission Specification: Terminality gate judges every issue-matrix row

**Mission Branch**: `issue-6653-terminality-all-rows`
**Created**: 2026-10-26
**Status**: Draft
**Input**: #6653, plus the operator rulings of 2026-10-26. Research: [research.md](research.md).

## Intent Summary (confirmed 2026-10-26)

An operator or agent lands a Mission with `spec-kitty consolidate`, or moves a work package with `move-task --to done`.

**At `done`:**
- Every `in-mission` issue-matrix row blocks in `block` mode and warns in `warn` mode, whether or not its issue is cited in the Mission's artifacts.
- When a matrix exists, the whole matrix is judged: malformed rows and unknown verdicts count as unresolved too. This holds even for a Mission with zero gating references (Decision `01M5X206M989YE99MA0KHRFTNP`).

**At `approved`:** nothing changes.

**Without a matrix:** a Mission that never authored one still needs none (#5222 F1). A missing matrix is told apart from a git probe that failed, and a failed probe still fails closed.

**Reporting:** a PASS states what it judged and never describes rows it did not check.

**Deliverables:** a short decision record, and a "What `done` enforces" section in the issue-matrix reference doc.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An uncited in-mission row cannot land (Priority: P1)

An operator consolidates a Mission. Its issue-matrix has a row whose verdict is still `in-mission`, and that issue is not cited in `spec.md` or any other scanned artifact. Because the row says the Mission still owes a fix, the consolidation must stop in block mode.

**Why this priority**: today this case lands on the target branch with exit 0 and a PASS line claiming no rows are unresolved. That is the defect #6653 reports.

**Independent Test**: build a Mission that cites `#1234` (`fixed`), with an uncited `#5678` row left `in-mission`. Run the merge gates in block mode.

**Acceptance Scenarios**:

1. **Given** a matrix `{#1234: fixed, #5678: in-mission}` and only `#1234` cited, **When** the merge gates run in block mode, **Then** the terminality gate FAILs, its blocking flag is set, and its message names `#5678`.
2. **Given** the same Mission, **When** the gates run in warn mode, **Then** the gate FAILs without blocking and the warning names `#5678`.
3. **Given** the same Mission with `#5678` set to `fixed`, **When** the gates run in block mode, **Then** the gate PASSes (positive control on the same fixture).

### User Story 2 - A Mission with no gating references still has its matrix judged (Priority: P1)

A Mission cites no gating issue, or only a one-digit issue the reference detector skips, but its matrix holds an `in-mission` row recorded with `agent issue-verdict`.

**Why this priority**: today the gate returns "No gating issue references discovered — nothing to enforce" without reading the matrix. This is how the defect showed up in a real Mission.

**Independent Test**: a Mission with no cited issue and the matrix `{#5678: in-mission}`; a second Mission citing `#8` with `{#8: in-mission}`.

**Acceptance Scenarios**:

1. **Given** zero gating references and a matrix holding an `in-mission` row, **When** the gates run in block mode, **Then** the terminality gate FAILs and names the row.
2. **Given** a cited one-digit `#8` row left `in-mission`, **When** the gates run, **Then** the gate FAILs and names `#8`.
3. **Given** zero gating references and a matrix holding a malformed row (for example, an unknown verdict), **When** the gates run, **Then** the gate FAILs and surfaces the row's diagnostic.
4. **Given** zero gating references and a matrix whose rows are all terminal, **When** the gates run, **Then** the gate PASSes and reports how many rows it judged.

### User Story 3 - A Mission without a matrix is still unaffected (Priority: P1)

A coordination-topology Mission that cites no gating issue and never authored a matrix is consolidated, before or after its coordination worktree is gone.

**Why this priority**: #5222 F1. Such a Mission must never fail on a coordination probe for a matrix that was never written.

**Independent Test**: the existing `TestZeroGatingReferencesNeverProbesCoordination` cases, plus a post-consolidation coord Mission with no matrix at its ref.

**Acceptance Scenarios**:

1. **Given** a coord Mission with zero gating references and no matrix anywhere, **When** the gates run in block mode, **Then** both issue-matrix gates PASS.
2. **Given** a coord Mission after consolidation, whose coordination ref is valid but holds no matrix file, **When** the gates run, **Then** the terminality gate PASSes ("no issue-matrix authored").
3. **Given** a coord Mission after consolidation whose matrix at the ref holds an `in-mission` row, **When** the gates run, **Then** the gate FAILs.
4. **Given** a git probe that fails for a reason other than "file absent at a valid ref", **When** the gates run, **Then** the gate FAILs with the probe's message and never PASSes.

### User Story 4 - `move-task --to done` enforces the same rule (Priority: P2)

An agent moves a work package to `done`.

**Why this priority**: `move-task` calls the same blocker, so it has the same gap. It is P2 because consolidation is the main landing path.

**Independent Test**: move-task done-gate tests with an uncited `in-mission` row.

**Acceptance Scenarios**:

1. **Given** an uncited `in-mission` row, **When** `move-task --to done` runs, **Then** it is refused, and the message names the row and the remedy (`agent issue-verdict`).
2. **Given** the same matrix, **When** `move-task --to approved` runs, **Then** it is not blocked by that row (approval semantics are unchanged).
3. **Given** a Mission with zero gating references and no matrix, **When** `move-task --to approved` or `--to done` runs, **Then** no issue-matrix refusal occurs.

### Edge Cases

- An uncited row with a terminal verdict (`fixed`, `verified-already-fixed`, `deferred-with-followup`, `not-applicable`) never blocks.
- A `context_only` citation (for example `see #12`) with an `in-mission` row blocks at `done`: the verdict decides resolution, not the classification.
- The completeness gate (which rows are REQUIRED) is unchanged: an uncited issue is never reported as missing.
- A matrix that cannot be parsed at all, with zero gating references, FAILs at `done` with its diagnostic, the same as for a Mission with gating references.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Every in-mission row blocks at done | As an operator, I want every `in-mission` row in the issue-matrix to fail the `done` check, whether or not its issue is cited, so that a Mission never lands while its own ledger says it still owes a fix. | High | Open | [build] | no — the uncited-row case FAILs only after the change, paired with a same-fixture `fixed` control that PASSes |
| FR-002 | Matrix judged with zero gating references | As an operator, I want the `done` check to read and judge an existing matrix (in-mission rows and row diagnostics) even when no gating reference is discovered, so that a Mission citing nothing, or only one-digit refs, cannot skip the check. | High | Open | [build] | no — zero-ref plus in-mission row FAILs, paired with a zero-ref all-terminal matrix that PASSes |
| FR-003 | No matrix means nothing to enforce | As an operator, I want a Mission with zero gating references and no authored matrix to pass the issue-matrix checks without any coordination probe failure, so that #5222 F1 keeps holding. | High | Open | [ratchet] | yes — pinned by the existing zero-refs tests plus a new post-consolidation no-matrix case; the paired positive control is FR-002's matrix-present case on the same coord fixture |
| FR-004 | Absent matrix told apart from a failed probe | As an operator, I want a matrix file that is absent at a valid ref to read as "no matrix", while a deleted ref, an unreadable object or a git failure still fails closed, so that a broken probe never turns into a PASS. | High | Open | [build] | no — a simulated probe failure FAILs, while absence at a valid ref PASSes |
| FR-005 | PASS states what was judged | As an operator, I want a PASS of the terminality gate to say how many rows it judged, or that no matrix was authored, so that the output never describes rows that were not checked. | Medium | Open | [build] | no — the PASS detail text changes and is asserted |
| FR-006 | move-task done uses the same rule | As an agent, I want `move-task --to done` to refuse an uncited `in-mission` row, while `--to approved` keeps accepting it, so that both landing paths enforce one rule. | Medium | Open | [build] | no — the done refusal is new, paired with the approved control on the same matrix |
| FR-007 | Decision record and reference doc | As a maintainer, I want a short decision record and a "What `done` enforces" section in the issue-matrix reference doc, so that the rule and the accepted behaviour change are written down. | Medium | Open | [build] | yes — docs only; reviewed in the PR, not by a test |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No extra probe cost without a matrix | A Mission with zero gating references and no matrix adds at most one git object-presence probe per matrix filename (2) to a gate run, and never a content read. | Performance | Medium | Open |
| NFR-002 | Fail closed | 0 code paths turn a probe error (deleted ref, unreadable object, git failure, timeout) into a PASS. Each is asserted by a test. | Reliability | High | Open |
| NFR-003 | Code quality | Touched functions stay at cyclomatic complexity ≤ 15. ruff, ruff format and mypy are clean on touched files, with no new `noqa` or `type: ignore`. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Approval semantics unchanged | At `approved` the blocker's behaviour is unchanged: `in-mission` is accepted there, and a Mission with zero gating references never needs a matrix to be approved. | Technical | High | Open |
| C-002 | Completeness unchanged | Classification still decides which rows are REQUIRED. The completeness gate's set of required rows does not change. | Technical | High | Open |
| C-003 | Compat names kept | The frozen re-exported names (`_issue_matrix_approval_blocker`, `_issue_matrix_evaluation`, `_issue_matrix_in_mission_rows`) keep their names and stay importable from their current compat surfaces. | Technical | High | Open |
| C-004 | Single read authority | The coordination ref read stays in `mission_runtime` behind one authority. No second matrix reader is added in `specify_cli`. | Technical | High | Open |
| C-005 | Accepted behaviour change | Missions that pass today may be refused in block mode, including at `move-task --to done`. This is accepted by the operator and recorded in the changelog and the decision record. | Business | High | Open |

### Key Entities

- **Issue-matrix row**: an issue handle, a verdict (`in-mission`, `fixed`, `verified-already-fixed`, `deferred-with-followup`, `not-applicable`, or unknown) and an evidence reference.
- **Gating reference**: an issue cited as an implementation target in a PRIMARY Mission artifact. It decides whether a row is REQUIRED, not whether an existing row is resolved.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All three reproduction variants from #6653 (uncited row, zero gating references, one-digit cited ref) are refused in block mode, where today they land with exit 0. — [build] · no-op passable: no
- **SC-002**: 100% of the existing zero-gating-references, no-matrix gate tests still pass unchanged. — [ratchet] · no-op passable: yes
- **SC-003**: No terminality PASS message claims rows were checked that were not judged. Every PASS detail names a judged-row count or "no issue-matrix authored". — [build] · no-op passable: no

## Assumptions

- `in-mission` keeps its current meaning: the issue is closed by a later work package of the same Mission.
- The post-consolidation coordination ref read keeps its lifecycle-phase ref selection (#5171). Only the "file absent at a valid ref" leg becomes distinguishable.
