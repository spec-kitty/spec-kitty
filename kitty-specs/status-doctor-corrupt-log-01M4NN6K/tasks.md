# Work Packages: Status Doctor Corrupt Log

**Inputs**: `kitty-specs/status-doctor-corrupt-log-01M4NN6K/`  
**Prerequisites**: plan.md, spec.md, research.md, reasons-canvas.md, data-model.md, contracts/status-doctor.md, quickstart.md  
**Tests**: Required by approved scope and charter: failing-first contract before implementation, targeted validation and independent review.  
**Organization**: One bounded WP01; six sequential subtasks, no parallel file writers. Status/completion is event-sourced, not markdown checkboxes.  
**Audience**: software-engineer and automation-agent.

## Subtask Format: `[Txxx] [P?] Description`

Plain Txxx rows are reference rows. Use canonical `agent tasks mark-status` to record completion; do not edit a checkbox or lane field. No [P] markers because one local defect shares one production/test surface.

## Path Conventions

All source/test paths are repository-root-relative; artifact paths resolve under this Mission. Current/base/mission target are `issue-5924-status-doctor-corrupt-log`, single_branch. Final PR targets main. No merge/consolidation or main push.

## Work Package WP01: Status Doctor Log Errors (Priority: P1)

**Goal**: Deliver #5924: corrupt/unreadable authority becomes an actionable read-only ERROR with or without snapshot; healthy existing checks remain.
**Independent Test**: Real run_doctor and text/JSON CLI tests cover five failure classes in both snapshot states, physical line/path/reason, evidence preservation, safe recovery, independent checks and accepted-history controls.
**Prompt**: `kitty-specs/status-doctor-corrupt-log-01M4NN6K/tasks/WP01-status-doctor-log-errors.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, C-004, SC-001, SC-002, SC-003, SC-004
**Issue Owner**: Ivan-Melck; canonical issue-matrix row initially in-mission, WP01.

### Included Subtasks

T001 Review touched campsite and preserve baseline evidence; record focused no-enabler conclusion or distinct behavior-preserving tidy-first step.
T002 Author/run/commit failing-first acceptance tests for both snapshot paths through existing run_doctor and CLI, before production edits.
T003 Implement strict canonical log read independent of snapshot, translate exactly StoreError/OSError/UnicodeError to an ERROR and retain independent checks.
T004 Complete truthful location/recovery, five-class matrix, byte-preservation, accepted mixed/blank/missing/empty and drift/WP reconciliation controls; remove transitional regression markers with fix.
T005 Run every changed test, status fast tier, shared fast baseline, scoped lint/strict typing/format and changed-line coverage; self-review and record exact results.
T006 Prepare independent-review handoff with red→green commits and full bounded diff; address findings, leave approved/accepted mission pending PR integration, never merge/consolidate.

### Implementation Notes

- Canonical store reader supplies physical row lines including blanks. Parent witnessed malformed annotation delta=[] escaping as AttributeError; approved store.py change adds AttributeError only to existing annotation decoder catch tuple, preserving line-bearing StoreError, with direct test_store.py and doctor delta/subtasks tests. Note PR #5953 overlap.
- Read failure must not trigger log-dependent initialization/backfill/drift/membership suggestions. Also skip reviewer-self-approval because it reads the same log. Independent issue-matrix/sparse/frontmatter checks continue.
- Use same-fixture repaired controls and separate snapshot-half proofs. Real files for parse/decode, deterministic filesystem boundary injection for I/O; do not mock away diagnosis.
- Allowed production doctor.py plus approved annotation catch tuple in store.py; test_doctor.py and test_store.py plus optional test_doctor_log_errors.py. No decision doctor (see #5304 for context only), reducer, CLI adapter, schemas, dependencies or versions.
- Failing-first commit precedes production fix. Transitional regression markers are not final acceptance; remove on fix and run ordinary targeted tests without opt-in.

### Parallel Opportunities

None for implementation; reviewer is a separate role/session after handoff. No concurrent duplicate test runs. Planner owns planning only and performs no product edits.

### Dependencies

None. Sequential single_branch execution uses resolver-returned write checkout, no lane-worktree or dependency merge.

### Risks & Mitigations

Snapshot mask/crash → test halves separately; inaccurate location → physical-row fixtures; broad fallback → exact exception boundary; destructive recovery → action assertions; false healthy controls → same fixture repaired; overreach → scope reviewed; baseline environment residue → parent evidence and named gate, not product cleanup.

## Dependency & Execution Summary

- **Sequence**: WP01 T001 → T002 RED commit → T003/T004 bounded fix → T005 targeted GREEN/self-review → T006 independent review.
- **Parallelization**: None among writing tasks.
- **MVP Scope**: Entire WP01 is the approved bounded fix; no separate setup/platform/polish WP needed.
- **Handoff**: Analyze readiness gate before implementation. Planner stops before implement. Parent uses independent reviewer, opens PR only.

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| FR-005 | WP01 |
| FR-006 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP01 |
| C-004 | WP01 |
| SC-001 | WP01 |
| SC-002 | WP01 |
| SC-003 | WP01 |
| SC-004 | WP01 |

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Campsite/baseline review | WP01 | P1 | No |
| T002 | RED acceptance-test commit | WP01 | P1 | No |
| T003 | Canonical read-failure finding | WP01 | P1 | No |
| T004 | Matrix/controls/marker removal | WP01 | P1 | No |
| T005 | Targeted validation/self-review | WP01 | P1 | No |
| T006 | Independent-review handoff | WP01 | P1 | No |
