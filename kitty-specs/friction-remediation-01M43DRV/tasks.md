# Work Packages: Regression-slice friction remediation

**Inputs**: `spec.md`, `plan.md` and `research/code-grounding.md` in `kitty-specs/friction-remediation-01M43DRV/`

**Tests**:
- Every `[build]` requirement gets a test that is committed RED first, through the pre-existing entry point (charter ATDD-first, SO-4).
- WP04 conversions are proven by planted breaks. Each break is reverted and never committed.

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows. Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Classify quickstart.md and contracts/** as PRIMARY (Priority: P1, #5552)

**Goal**: Squash consolidate stops projecting the plan outputs `quickstart.md` and `contracts/**` as coordination bookkeeping.
**Independent Test**: On a real git fixture, `_post_checkpoint_mission_paths` excludes post-checkpoint `quickstart.md` and `contracts/a.md`, and still projects `traces/approach.md`. The classifier unit tests pin both kinds.
**Prompt**: `tasks/WP01-classify-plan-outputs-primary.md`
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-001, NFR-002, NFR-003

### Included Subtasks

T001 RED: a projection test on a git fixture, plus classifier unit tests for `quickstart.md` and `contracts/**`
T002 Add `quickstart.md → CHECKLIST` and a new `CONTRACT` kind (directory `contracts`) to the `mission_runtime.artifacts` registry, PRIMARY partition
T003 Add `CONTRACT` to `commit_router._PRE_TASKS_ARTIFACT_KINDS` (contracts are plan output)
T004 Re-point the placement guard and the merge-reconciliation class guard (enumerate the new member and entries; no loosening)
T005 Run the `kind_for_mission_file` callers' tests and the named architectural gates

### Dependencies

- None.

### Risks & Mitigations

- `safe-commit` and `workflow.py` commit routing for these paths moves to the primary target. This is intended: they are planning artifacts, like `spec.md`. Covered by the callers' test files.

---

## Work Package WP02: meta.json contracts waiver honoured by strict accept (Priority: P1, #5298)

**Goal**: A software-dev Mission can declare `"contracts": "none"` with a `contracts_rationale` in `meta.json`. Strict `accept` then skips the `contracts/` deliverable convention. Malformed or absent waivers keep it blocking.
**Independent Test**: `collect_feature_summary(..., strict_metadata=True)` on a no-contracts Mission: waived → no `contracts` path violation; unwaived or malformed → blocked. Unit tests on the reader.
**Prompt**: `tasks/WP02-contracts-waiver-accept.md`
**Requirement Refs**: FR-004, FR-005, FR-006, FR-007, C-001, C-002, NFR-001, NFR-002

### Included Subtasks

T006 RED: reader unit tests and strict-accept waiver tests (waived / unwaived / malformed / corrupt meta)
T007 Add `read_contracts_waiver_from_meta` to `core/paths.py` (fail-closed, typed verdict)
T008 Add a `waived_artifact_tokens` keyword to `validate_mission_paths`, and apply the waiver in `evaluate_path_conventions` (surface the rationale as a warning)
T009 Add the `contracts` and `contracts_rationale` fields to `MissionMetaOptional`, plus an ADR under `docs/adr/4.x/`
T010 Run the acceptance and validator suites and the single-caller and load-meta census gates

### Dependencies

- None (independent of WP01).

### Risks & Mitigations

- The dedup behaviour (`test_accept_contracts_dedup.py`) must stay intact.

---

## Work Package WP03: Pure dry-run attestation notice (Priority: P3, #5653) — SEQUENCED

**Goal**: Extract `dry_run_attestation_notice` into `consolidation/canceled_attestation.py`, unit-test it, and replace the 11-stub CLI helper with unit tests plus at most one smoke test.
**Gate**: Start only once PR #5650 has merged to `main` and been merged into this branch. Otherwise cancel this WP, with the rationale "deferred: waits on #5650".
**Prompt**: `tasks/WP03-dry-run-attestation-notice.md`
**Requirement Refs**: FR-008

### Included Subtasks

T011 Sequencing check: is PR #5650 merged?
T012 Extract the pure function; the CLI calls it; output byte-identical
T013 Unit tests (four cases); retire `_invoke_consolidate_dry_run`; update the terminus docstring

### Dependencies

- None in-Mission (external: PR #5650).

---

## Work Package WP04: Root-honest permission tests and isolated TestOrdering (Priority: P3, #5654 + #5186) — SEQUENCED

**Goal**: Fault-inject the three real root defects, verify the three named sites by a planted break, delete `GitignoreManager._atomic_write`, make `TestOrdering` pass alone, and file the follow-up list.
**Gate**: Start only once PR #5656 has merged to `main` and been merged into this branch. Otherwise cancel this WP, with the rationale "deferred: waits on #5656".
**Prompt**: `tasks/WP04-root-honest-tests-and-ordering.md`
**Requirement Refs**: FR-009

### Included Subtasks

T014 Sequencing check: is PR #5656 merged?
T015 Convert the encoding, mission-v1-events and upgrade-ux tests to seam injection (planted breaks)
T016 Planted-break verification of the gitignore and init sites; delete `_atomic_write`; fix its test docstring
T017 Add a class-scoped `auto_discover_migrations` fixture for `TestOrdering`; file the follow-up issue

### Dependencies

- None in-Mission (external: PR #5656).
