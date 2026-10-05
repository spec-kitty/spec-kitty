# Work Packages: Approved claim bound

**Inputs**: Design documents from `kitty-specs/approved-claim-bound-01M444QR/`
**Prerequisites**: plan.md, spec.md, research.md, research/code-grounding.md, data-model.md, contracts/consolidate-refusals.md, quickstart.md

**Tests**: requested by the operator brief and the charter (ATDD-first): a red-first reproduction through the CLI, unit tests on the bound, existing pins kept.

**Organization**: 29 subtasks in 7 work packages. WP01 is the tidy-first enabler; WP02 is the fix at claim time, carries the red-first reproduction and defines everything the parallel packages share; WP03, WP04 and WP05 depend only on WP02 and run in parallel without touching each other's files; WP06 (documentation) and WP07 (integrated verification) close.

## Subtask Index

| ID | Description | WP | Parallel |
|---|---|---|---|
| T001 | Make the stamp readers public | WP01 | |
| T002 | Fold the inline stamp read in `canceled_attestation.py` | WP01 | |
| T003 | Restamp the terminus fixtures | WP01 | [P] |
| T004 | Restamp the consolidation unit-test builders | WP01 | [P] |
| T005 | Remove the self-comparison test; prove the suite unchanged | WP01 | |
| T006 | Red-first reproduction through the CLI (4 cells) | WP02 | |
| T007 | `approved_bound.py`: approval-stamp reader | WP02 | |
| T008 | `approved_bound.py`: lane check | WP02 | |
| T009 | Wire the check into the claim builder | WP02 | |
| T010 | Unit tests for the bound | WP02 | |
| T011 | Reconcile the tests that pinned the old premise | WP02 | |
| T012 | Red test: a commit injected during the run | WP03 | |
| T013 | Re-run the lane check at the gate | WP03 | |
| T014 | Prove the rollback path | WP03 | |
| T015 | Pin the merge-commit residual | WP03 | [P] |
| T016 | `approved_attestation.py` | WP04 | |
| T017 | CLI flag, recording, refusal sentence | WP04 | |
| T018 | End-to-end attestation test | WP04 | |
| T019 | Attestation unit tests | WP04 | [P] |
| T020 | CLI reference and flag inventory | WP04 | [P] |
| T021 | Red test for the orchestrator code-lane path | WP05 | |
| T022 | Evaluate the check before the first lane merge | WP05 | |
| T023 | Resume | WP05 | [P] |
| T024 | ADR | WP06 | [P] |
| T025 | Changelog | WP06 | [P] |
| T026 | CLAUDE.md | WP06 | [P] |
| T027 | Run the issue's reproducer | WP07 | |
| T028 | Attestation across the gate | WP07 | |
| T029 | Owning suites on the integrated base | WP07 | |
| T030 | Orchestrator contract version and review follow-ups | WP07 | |
| T031 | Resume after an interruption between the lane merge and the gate | WP07 | |
| T032 | Pin the case the gate re-check closes; review tidy-ups | WP07 | |

---

## Work Package WP01: Tidy-first: stamp readers and truthful approval fixtures (Priority: P0)

**Goal**: one public reader of the lane-head stamp; shared test fixtures that approve after the lane work exists, with real stamps. No product behaviour change.
**Independent Test**: `tests/consolidation` and `tests/terminus` pass with the same counts before and after, minus one deleted self-comparison test.
**Prompt**: `/tasks/WP01-tidy-first-stamp-readers-and-truthful-fixtures.md`
**Requirement Refs**: FR-014, C-007
**Estimated prompt size**: ~177 lines

### Included Subtasks

T001 Make the stamp readers public (WP01)
T002 Fold the inline stamp read in `canceled_attestation.py` (WP01)
T003 Restamp the terminus fixtures (WP01)
T004 Restamp the consolidation unit-test builders (WP01)
T005 Remove the self-comparison test; prove the suite unchanged (WP01)

### Implementation Notes

- Two renames and one fold under `src/`; two central fixture edits under `tests/`.

### Parallel Opportunities

- T003 and T004 touch different files.

### Dependencies

- None (starting package).

### Risks & Mitigations

- A builder reorder changes what a test asserts: keep signatures, compare counts before and after.

---

## Work Package WP02: Approved bound: red-first reproduction and claim-time refusal (Priority: P0)

**Goal**: `consolidate` refuses a lane with content beyond its approval stamps, an unstamped approval and a rewritten lane, before any branch moves.
**Independent Test**: `tests/terminus/test_post_approval_commit_refused.py` is red at its own commit and green at the end of the work package, in four cells with a positive control each.
**Prompt**: `/tasks/WP02-approved-bound-reproduction-and-claim-time-refusal.md`
**Requirement Refs**: FR-001, FR-002, FR-005, FR-008, FR-009, FR-010, FR-013, NFR-001, NFR-004, C-002, C-003, C-005
**Estimated prompt size**: ~241 lines

### Included Subtasks

T006 Red-first reproduction through the CLI (WP02)
T007 `approved_bound.py`: approval-stamp reader (WP02)
T008 `approved_bound.py`: lane check (WP02)
T009 Wire the check into the claim builder (WP02)
T010 Unit tests for the bound (WP02)
T011 Reconcile the tests that pinned the old premise (WP02)

### Implementation Notes

- New module `consolidation/approved_bound.py`; two public functions in `reconciliation.py`; two run-state fields.

### Parallel Opportunities

- None; the subtasks build on each other.

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- False refusal on tool-made lane movement: each movement has a unit test with a refusing control.
- Mixed lanes: a canceled work package's latest stamp is a covered point; existing verdicts must not change.

---

## Work Package WP03: Gate re-check and honest verified banner (Priority: P1)

**Goal**: the gate re-runs the lane check before it prints "verified"; a commit added during the run is refused and rolled back through the existing authority.
**Independent Test**: `tests/terminus/test_post_approval_gate_recheck.py` is red without the gate change and green with it.
**Prompt**: `/tasks/WP03-gate-recheck-and-honest-verified-banner.md`
**Requirement Refs**: FR-003, FR-004, C-001
**Estimated prompt size**: ~168 lines

### Included Subtasks

T012 Red test: a commit injected during the run (WP03)
T013 Re-run the lane check at the gate (WP03)
T014 Prove the rollback path (WP03)
T015 Pin the merge-commit residual (WP03)

### Implementation Notes

- One call in `phase_gate.py` in front of `verify()`, anchored on SHAs captured before mutation; one non-PASS branch.

### Parallel Opportunities

- Runs in parallel with WP04 and WP05. T015 is independent of T012 to T014.

### Dependencies

- Depends on WP02.

### Risks & Mitigations

- No new restore path: the rollback caller pin must pass unchanged.

---

## Work Package WP04: Attestation for an unstamped approval (Priority: P1)

**Goal**: `--attest-approved-reviewed` records an operator attestation that lifts only the missing-stamp refusal.
**Independent Test**: `tests/terminus/test_unstamped_approval_attestation.py` walks refuse, attest, consolidate, and refuse-after-attestation.
**Prompt**: `/tasks/WP04-attestation-for-an-unstamped-approval.md`
**Requirement Refs**: FR-006, FR-007
**Estimated prompt size**: ~187 lines

### Included Subtasks

T016 `approved_attestation.py` (WP04)
T017 CLI flag, recording, refusal sentence (WP04)
T018 End-to-end attestation test (WP04)
T019 Attestation unit tests (WP04)
T020 CLI reference and flag inventory (WP04)

### Implementation Notes

- Mirrors `canceled_attestation.py`; the record is a forced operator self-transition read by `approval_stamp`.

### Parallel Opportunities

- Runs in parallel with WP03 and WP05. T019 and T020 are independent of T018.

### Dependencies

- Depends on WP02.

### Risks & Mitigations

- The events contract requires evidence for `approved` and `done` transitions.

---

## Work Package WP05: Orchestrator and resume entry points (Priority: P1)

**Goal**: `orchestrator-api consolidate-mission` refuses before its first lane merge; `--resume` is proven in both directions.
**Independent Test**: `tests/orchestrator_api/test_consolidate_mission_post_approval.py` is red without the change and green with it.
**Prompt**: `/tasks/WP05-orchestrator-and-resume-entry-points.md`
**Requirement Refs**: FR-011
**Estimated prompt size**: ~148 lines

### Included Subtasks

T021 Red test for the orchestrator code-lane path (WP05)
T022 Evaluate the check before the first lane merge (WP05)
T023 Resume (WP05)

### Implementation Notes

- One call into `reconciliation` before the lane loop; the envelope contract stays stable.

### Parallel Opportunities

- Runs in parallel with WP03 and WP04.

### Dependencies

- Depends on WP02.

### Risks & Mitigations

- External orchestrators parse the envelope: add a code, change no existing key.

---

## Work Package WP06: Decision record and operator documentation (Priority: P2)

**Goal**: ADR, changelog with upgrade note, `CLAUDE.md`.
**Independent Test**: docs freshness check reports 0 errors.
**Prompt**: `/tasks/WP06-decision-record-and-operator-documentation.md`
**Requirement Refs**: FR-015
**Estimated prompt size**: ~148 lines

### Included Subtasks

T024 ADR (WP06)
T025 Changelog (WP06)
T026 CLAUDE.md (WP06)

### Implementation Notes

- New ADR `docs/adr/4.x/2026-10-04-3-approval-stamp-bounds-the-approved-claim.md`; forward pointer in the 3.x ADR.

### Parallel Opportunities

- T024 to T026 touch different files.

### Dependencies

- Depends on WP03, WP04, WP05.

### Risks & Mitigations

- Docs index regeneration after adding an ADR.

---

## Work Package WP07: Integrated verification (Priority: P1)

**Goal**: the parallel packages work together: an attestation survives the gate re-check, the owning suites pass on the integrated base, the issue's reproducer exits 0 in four combinations.
**Independent Test**: the commands of T029 recorded with counts; four reproducer runs recorded.
**Prompt**: `/tasks/WP07-integrated-verification.md`
**Requirement Refs**: FR-012, NFR-002, NFR-003
**Estimated prompt size**: ~144 lines

### Included Subtasks

T027 Run the issue's reproducer (WP07)
T028 Attestation across the gate (WP07)
T029 Owning suites on the integrated base (WP07)
T030 Orchestrator contract version and review follow-ups (WP07)
T031 Resume after an interruption between the lane merge and the gate (WP07)
T032 Pin the case the gate re-check closes; review tidy-ups (WP07)

### Implementation Notes

- At most one new test file; everything else is running and classifying.

### Parallel Opportunities

- Runs in parallel with WP06.

### Dependencies

- Depends on WP03, WP04, WP05.

### Risks & Mitigations

- Baseline reds are classified, not chased.
