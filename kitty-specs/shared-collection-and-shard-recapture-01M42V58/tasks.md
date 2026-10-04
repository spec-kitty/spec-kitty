# Work Packages: Shared battery collection and complete shard-timing provenance

**Inputs**: Design documents from `kitty-specs/shared-collection-and-shard-recapture-01M42V58/`
**Prerequisites**: plan.md, spec.md, research.md (decisions D-01..D-15, brownfield findings B-01..B-09), data-model.md, contracts/, quickstart.md

**Tests**: required. Every work package opens with a failing test through the real entry point (charter ATDD-first).

**Organization**: fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Write scopes are disjoint, so each code package gets its own lane. Two chains run in parallel: WP01 → WP02 → WP03 (collection store and its workflows) and WP04 (scheduled recapture). Then WP06 (rename and documentation), then WP05 (measured capture, last so nothing changes test counts after it), then WP07 (evidence).

**After the pull request is open** (not a work package, because the data does not exist earlier): the orchestrator fills `evidence/ci-measurements.md` from three per-PR runs (FR-022, SC-001, SC-002).

**Prompt Files**: each work package references a prompt file in `tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can proceed in parallel with its neighbours.
- Subtasks are reference rows. Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Campsite: split `collect_universe()` into fresh-collection helpers, behaviour unchanged | WP01 | |
| T002 | Red-first tests for key, record validation and store I/O in `test_universe_store.py` | WP01 | |
| T003 | Implement `_universe_store.py`: key inputs, digest, record read/validate/write/evict | WP01 | |
| T004 | Wire the store into `collect_universe()`: bypass rules, lock, atomic write | WP01 | |
| T005 | Emit the reuse report line for every call | WP01 | |
| T006 | Non-vacuity pins: paired controls, half-by-half reverts, planted violation on both paths | WP01 | |
| T007 | Red-first tests for the pre-step script commands | WP02 | |
| T008 | Implement `key` and `collect` | WP02 | |
| T009 | Implement `check` with job-summary output and the fallback failure | WP02 | |
| T010 | Implement `compare` (fresh versus stored) | WP02 | |
| T011 | Red-first workflow-shape tests for the pre-test step | WP03 | |
| T012 | Heavy battery legs: split the run block, add restore, pre-step, check, save | WP03 | |
| T013 | Module shard: move the shard list out of the checkout, add the conditional pre-step | WP03 | |
| T014 | Nightly equivalence job with fork guard and summary wiring | WP03 | [P] |
| T015 | Re-run and adjust the workflow-shape gates named in B-06 | WP03 | |
| T016 | Rename the recapture script and its test; campsite: lift single-module constants | WP04 | |
| T017 | Red-first tests: count-only drift pass, isolation, budget, open-proposal refresh, rejected push | WP04 | |
| T018 | Implement the count-only drift pass and the shared valid-capture predicate | WP04 | |
| T019 | Implement per-module subprocess capture with failure isolation | WP04 | |
| T020 | Implement the time budget and deferred reporting | WP04 | |
| T021 | Publish phase: follow-up commit on an open proposal, loud rejected push | WP04 | |
| T022 | Update the workflow content for all modules (file name unchanged) | WP04 | |
| T023 | Red-first provenance-completeness test with self-mutation proof | WP05 | |
| T024 | Measured capture of every unmeasured or drifted module (orchestrator) | WP05 | |
| T025 | Raise any shard count that fails the skew check on recaptured durations (never reduce) | WP05 | |
| T026 | Delete the mismatch allowlist, its baseline and its shape tests | WP05 | |
| T027 | Strict-mode agreement run at the capture commit; record results | WP05 | |
| T028 | Rename the recapture workflow file and update every reference | WP06 | |
| T029 | Regenerate the pinning inventory; run the gates that pin the workflow set | WP06 | |
| T030 | Update the CI gate mechanics and parallel-testing references | WP06 | [P] |
| T031 | Update the PR-landing how-to and add the changelog entry | WP06 | [P] |
| T032 | Docs gates: freshness, terminology, spelling, retrieval index | WP06 | |
| T033 | Record local reuse and capture measurements in `evidence/` | WP07 | |
| T034 | Record the #5536 publish-failure classification | WP07 | [P] |
| T035 | Assess the three tracer files and seed the CI-measurement template | WP07 | |

---

## Work Package WP01: Collection key and store (Priority: P1) 🎯 MVP

**Goal**: `collect_universe()` reuses a stored universe when, and only when, it was produced from the same committed tree and environment; every call reports what it did.
**Independent Test**: `pytest tests/architectural/test_universe_store.py -q` passes; on a clean checkout two consecutive real calls report `collected` then `reused` and return equal lists.
**Prompt**: `tasks/WP01-collection-key-and-store.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-010, FR-012, NFR-004, C-002, C-003, SC-003, SC-007

### Included Subtasks

T001 Campsite: split `collect_universe()` into fresh-collection helpers, behaviour unchanged
T002 Red-first tests for key, record validation and store I/O in `test_universe_store.py`
T003 Implement `_universe_store.py`: key inputs, digest, record read/validate/write/evict
T004 Wire the store into `collect_universe()`: bypass rules, lock, atomic write
T005 Emit the reuse report line for every call
T006 Non-vacuity pins: paired controls, half-by-half reverts, planted violation on both paths

### Implementation Notes

- Pure logic lives in `_universe_store.py`; `_gate_coverage.py` keeps orchestration only.
- Tests inject a fake collector; no test in this package performs a real 20–95 s collection.

### Parallel Opportunities

- None inside the package; lane B (WP04) runs in parallel.

### Dependencies

- None.

### Risks & Mitigations

- Per-process variables in the key would prevent any match → exclusion list with a test.
- `_gate_coverage.py` is on the ruff-format exclude ratchet → never format it by explicit path.

**Estimated prompt size**: ~330 lines

---

## Work Package WP02: Pre-step script and reuse check (Priority: P1)

**Goal**: one command-line entry point that computes the key, collects before tests, fails a job that silently fell back, and compares a fresh collection with the stored one.
**Independent Test**: `pytest tests/ci/test_collect_universe_prestep.py -q` passes; `python -m scripts.ci.collect_universe_prestep check` exits 1 on a report file that shows a fallback after a successful pre-step.
**Prompt**: `tasks/WP02-pre-step-script-and-reuse-check.md`
**Requirement Refs**: FR-010, FR-011, NFR-005

### Included Subtasks

T007 Red-first tests for the pre-step script commands
T008 Implement `key` and `collect`
T009 Implement `check` with job-summary output and the fallback failure
T010 Implement `compare` (fresh versus stored)

### Implementation Notes

- The script delegates every key and store decision to `_universe_store.py`; it holds no second copy.

### Parallel Opportunities

- T009 and T010 are independent once T008 exists.

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- `scripts/**` is under ruff's security rules → subprocess use must be argument-list form with fixed executables.

**Estimated prompt size**: ~260 lines

---

## Work Package WP03: Pre-test step in the consuming workflows (Priority: P1)

**Goal**: the two heavy battery legs and the consuming module shard collect before pytest, restore on re-runs, and fail on a silent fallback; the nightly run proves reuse equals a fresh collection.
**Independent Test**: `pytest tests/ci/test_ci_workflow_prestep_shape.py -q` passes and the gates named in research B-06 stay green.
**Prompt**: `tasks/WP03-pre-test-step-in-workflows.md`
**Requirement Refs**: FR-008, FR-009, NFR-001, NFR-002, NFR-003, C-010

### Included Subtasks

T011 Red-first workflow-shape tests for the pre-test step
T012 Heavy battery legs: split the run block, add restore, pre-step, check, save
T013 Module shard: move the shard list out of the checkout, add the conditional pre-step
T014 [P] Nightly equivalence job with fork guard and summary wiring
T015 Re-run and adjust the workflow-shape gates named in B-06

### Implementation Notes

- The pytest command line of each job stays byte-identical.
- Reuse the existing `actions/cache` pin (research B-07).

### Parallel Opportunities

- T014 touches only the nightly workflow.

### Dependencies

- Depends on WP02.

### Risks & Mitigations

- Step-shape gates may pin step order → run the named gate files after each workflow edit.

**Estimated prompt size**: ~320 lines

---

## Work Package WP04: Generalised scheduled recapture (Priority: P2)

**Goal**: the scheduled recapture finds drift in any registry module with a count-only pass, captures only those modules in isolation and within a time budget, refreshes an open proposal, and reports a rejected push clearly.
**Independent Test**: `pytest tests/ci/test_recapture_shard_timings.py -q` passes, including a fixture where one non-charter module has drifted and only that module is captured.
**Prompt**: `tasks/WP04-generalised-scheduled-recapture.md`
**Requirement Refs**: FR-017, FR-018, FR-019, FR-020, FR-021, NFR-007, C-008, SC-006

### Included Subtasks

T016 Rename the recapture script and its test; campsite: lift single-module constants
T017 Red-first tests: count-only drift pass, isolation, budget, open-proposal refresh, rejected push
T018 Implement the count-only drift pass and the shared valid-capture predicate
T019 Implement per-module subprocess capture with failure isolation
T020 Implement the time budget and deferred reporting
T021 Publish phase: follow-up commit on an open proposal, loud rejected push
T022 Update the workflow content for all modules (file name unchanged)

### Implementation Notes

- The workflow file keeps its name in this package; WP06 renames it after lane A has landed.
- The secret name is a repository secret and does not change.

### Parallel Opportunities

- Runs in parallel with lane A.

### Dependencies

- None.

### Risks & Mitigations

- The capture producer runs pytest in-process once per process → one subprocess per module.

**Estimated prompt size**: ~380 lines

---

## Work Package WP05: Full recapture, provenance check and allowlist removal (Priority: P2)

**Goal**: every registry module carries measured timings and a valid provenance record, the mismatch allowlist no longer exists, and strict agreement holds at the capture commit.
**Independent Test**: `SPEC_KITTY_STRICT_SHARD_TIMINGS=1 pytest tests/architectural/test_module_length_agreement.py tests/architectural/test_shard_capture_provenance.py tests/architectural/test_module_shard_registry.py -q` passes.
**Prompt**: `tasks/WP05-full-recapture-and-allowlist-removal.md`
**Requirement Refs**: FR-013, FR-014, FR-015, FR-016, NFR-006, C-004, C-006, C-007, SC-004, SC-005

### Included Subtasks

T023 Red-first provenance-completeness test with self-mutation proof
T024 Measured capture of every unmeasured or drifted module (orchestrator)
T025 Raise any shard count that fails the skew check on recaptured durations (never reduce)
T026 Delete the mismatch allowlist, its baseline and its shape tests
T027 Strict-mode agreement run at the capture commit; record results

### Implementation Notes

- T024 is run by the orchestrator, serially, from a fully synced environment; it is not delegated.
- Order inside the package: T023, T026, T024, T025, T027. `ci` is captured last.

### Parallel Opportunities

- None; steps are ordered.

### Dependencies

- Depends on WP01, WP02, WP03, WP04, WP06.

### Risks & Mitigations

- Counts move again after a rebase → re-run the count-only pass and recapture only what moved.

**Estimated prompt size**: ~300 lines

---

## Work Package WP06: Workflow rename, documentation and changelog (Priority: P3)

**Goal**: the recapture workflow's name matches what it does, every reference follows, and the references describe shipped behaviour.
**Independent Test**: the gates that pin the workflow set and the docs gates pass.
**Prompt**: `tasks/WP06-workflow-rename-docs-changelog.md`
**Requirement Refs**: FR-023

### Included Subtasks

T028 Rename the recapture workflow file and update every reference
T029 Regenerate the pinning inventory; run the gates that pin the workflow set
T030 [P] Update the CI gate mechanics and parallel-testing references
T031 [P] Update the PR-landing how-to and add the changelog entry
T032 Docs gates: freshness, terminology, spelling, retrieval index

### Implementation Notes

- One-line edits in files owned by earlier packages are expected here and recorded with a rationale.

### Parallel Opportunities

- T030 and T031 are independent.

### Dependencies

- Depends on WP03, WP04.

### Risks & Mitigations

- Changelog fixtures under `tests/docs/fixtures/` must not be edited.

**Estimated prompt size**: ~240 lines

---

## Work Package WP07: Evidence and tracer assessment (Priority: P3)

**Goal**: the mission's result is stated from measurement, and its tracer files are assessed.
**Independent Test**: `evidence/` holds the local reuse measurement, the capture record and the #5536 classification; the CI-measurement file lists what is filled in after the pull request's first three runs.
**Prompt**: `tasks/WP07-evidence-and-tracer-assessment.md`
**Requirement Refs**: FR-022

### Included Subtasks

T033 Record local reuse and capture measurements in `evidence/`
T034 [P] Record the #5536 publish-failure classification
T035 Assess the three tracer files and seed the CI-measurement template

### Implementation Notes

- Per-PR CI measurements exist only after the pull request is open; they are appended to the same file then.

### Parallel Opportunities

- T034 is independent.

### Dependencies

- Depends on WP05.

### Risks & Mitigations

- Evidence written before the measurement exists would be invented → the template marks every unfilled value as pending.

**Estimated prompt size**: ~160 lines
