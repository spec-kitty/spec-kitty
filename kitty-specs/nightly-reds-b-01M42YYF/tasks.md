# Work Packages: Nightly reds B (2026-10-04)

**Inputs**: [`spec.md`](spec.md), [`plan.md`](plan.md), [`research/nightly-red-memo.md`](research/nightly-red-memo.md)
**Prerequisites**: plan.md, spec.md, research memo
**Tests**: every WP is a test repair or a red-first product fix; each names the exact node ids it greens.
**Organization**: one WP per independent failure group (not per GitHub issue), disjoint `owned_files`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Stress fixture is a well-formed coordination Mission (Priority: P1)

**Goal**: `tests/stress/test_concurrent_emits.py` passes 2/2 against a fixture shaped like a real coordination Mission.
**Independent Test**: `PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -q -n0 -m "" tests/stress/test_concurrent_emits.py`
**Prompt**: `/tasks/WP01-stress-fixture-coordination-mission.md`
**Requirement Refs**: FR-001, NFR-001, NFR-002, SC-001

### Included Subtasks

T001 Write the Mission `meta.json` (declared `coordination_branch`) in `_init_coord_repo`
T002 Make `MID8` the first 8 characters of `MISSION_ID`
T003 Show red on base and green on the lane; run the timing-coverage pin

### Dependencies

- None.

### Risks & Mitigations

- `tests/architectural/test_timing_coverage_invariant.py` pins the correctness test body verbatim: change only the fixture and constants.

---

## Work Package WP02: Coordination single-home integration oracles (Priority: P1)

**Goal**: the three integration node ids that lag commit `5b5699e50` pin the intended contract and pass.
**Independent Test**: the three node ids listed in the prompt.
**Prompt**: `/tasks/WP02-coord-single-home-oracles.md`
**Requirement Refs**: FR-002, FR-003, FR-004, NFR-001, NFR-002, SC-002

### Included Subtasks

T004 [P] Golden path: assert the create-time coordination seed instead of committing an empty log
T005 [P] Coordination-read residuals: spy on `write_dir(STATUS_STATE)`; assert `read_dir(STATUS_STATE)` is not used
T006 [P] Owned finalize: re-pin the exact post-mint ledger (16 → 18) with the frame-chain rationale

### Dependencies

- None.

### Risks & Mitigations

- Blind ledger bumps: the re-pin names the exact frame chain that added the reads.

---

## Work Package WP03: Vibe pointer recovery in `agent config sync` (Priority: P1)

**Goal**: `agent config sync --create-missing` restores a missing `.vibe/config.toml` for an already-installed vibe agent, without rewriting the pinned manifest.
**Independent Test**: `tests/init/test_init_idempotent.py::test_initialized_clone_vibe_pointer_recovery_and_repeat` plus `tests/specify_cli/cli/commands/test_agent_config.py`.
**Prompt**: `/tasks/WP03-vibe-pointer-recovery.md`
**Requirement Refs**: FR-005, NFR-002

### Included Subtasks

T007 Record the pre-existing red test as the red-first evidence (no new test is needed; it already fails on base)
T008 Restore the pointer in the already-installed branch of `_check_or_create_configured_agent_dirs`
T009 Run the agent-config and init test files

### Dependencies

- None.

### Risks & Mitigations

- Regressing `f4a2e63ed` (normal sync must not rewrite pinned manifests): only the gitignored pointer is written.

---

## Work Package WP04: Nightly integration-slice harness (Priority: P2)

**Goal**: the slice's corpus, status-guard and recover-characterization rows pass in the slice's real environment.
**Independent Test**: the node ids listed in the prompt, with `CI=true`, and a `--depth 1` clone check for the corpus row.
**Prompt**: `/tasks/WP04-integration-slice-harness.md`
**Requirement Refs**: FR-006, FR-007, FR-008, NFR-001, NFR-002, SC-003

### Included Subtasks

T010 [P] `ci-nightly.yml` `integration-slice` job: `fetch-depth: 0` with the reason
T011 [P] Status-guard self-test: accept the CI-mode ` - <message>` summary suffix
T012 [P] Recover characterization: run against a materialized coordination worktree

### Dependencies

- None.

### Risks & Mitigations

- `tests/ci/` pins of the nightly workflow: run `tests/ci/test_nightly_integration_slice.py` and `tests/ci/test_nightly_exit_code_honesty.py`.

---

## Dependency & Execution Summary

- **Sequence**: none required; all four WPs are independent.
- **Parallelization**: all four can run in parallel.
- **MVP Scope**: WP01 (closes the stress tracker).

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP02 |
| FR-003 | WP02 |
| FR-004 | WP02 |
| FR-005 | WP03 |
| FR-006 | WP04 |
| FR-007 | WP04 |
| FR-008 | WP04 |
| NFR-001 | WP01, WP02, WP04 |
| NFR-002 | WP01, WP02, WP03, WP04 |

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Stress meta.json | WP01 | P1 | No |
| T002 | Stress mid8 | WP01 | P1 | No |
| T003 | Stress evidence | WP01 | P1 | No |
| T004 | Golden-path seed | WP02 | P1 | Yes |
| T005 | write_dir spy | WP02 | P1 | Yes |
| T006 | Ledger re-pin | WP02 | P1 | Yes |
| T007 | Vibe red evidence | WP03 | P1 | No |
| T008 | Vibe pointer restore | WP03 | P1 | No |
| T009 | Vibe tests | WP03 | P1 | No |
| T010 | Slice full history | WP04 | P2 | Yes |
| T011 | CI-mode parser | WP04 | P2 | Yes |
| T012 | Materialized recover fixture | WP04 | P2 | Yes |
