# Work Packages: Nightly suites green on main

**Inputs**: Design documents from `/kitty-specs/nightly-suites-green-01M44FEP/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, research/code-grounding.md, quickstart.md

**Tests**: Required. Every implementation work package is red-first (charter C-011, spec C-005); the named test and gate files are listed in each prompt.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work package is independently deliverable and testable. Tracks A (WP01 to WP04), B (WP05, WP06) and C (WP07) share no source or test file; WP08 writes the closing records.

**Prompt Files**: Each work package references a matching prompt file in `/tasks/`. This file is the high-level list; implementation detail lives in the prompts.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`. The reduced event-log snapshot is the sole subtask-completion authority.

## Path Conventions

- **Single project**: `src/`, `tests/`, `docs/`

## Rules that bind every work package

- Paths owned by running missions are not edited (research/code-grounding.md section 6). The one exception is the body of `_is_bookkeeping` in `consolidation/reconciliation.py`, in WP03 only. An edit in a listed path is a stop-and-report.
- An edit outside a work package's `owned_files` needs a one-line rationale in the hand-back.
- Named test files and named `tests/architectural/*.py` gate files only; no whole directory, no `make test-fast`, no `make test-full`; at most `-n 4` pytest workers.
- Implementers do not edit `kitty-specs/`; tracer notes go in the hand-back.
- Implementer: `python-pedro` (WP01 to WP07), `architect-alphonso` (WP08). Reviewer for every work package: `reviewer-renata` on the strongest available model.

---

## Work Package WP01: Track A enablers: teardown identity read and structured seed refusal (Priority: P1)

**Goal**: Two behaviour-preserving enablers: the coordination teardown reads identity from the primary metadata, and the seed report carries a structured refusal field.
**Independent Test**: The focused teardown test and the extended seed-refusal tests pass; the named gates stay green; the #5651 reproduction is still red.
**Prompt**: `/tasks/WP01-track-a-enablers.md`
**Requirement Refs**: FR-001, FR-006, C-005

### Included Subtasks

T001 Record the baseline for the owned tests, gates and the reproduction (WP01)
T002 [P] Teardown reads Mission identity from `run.target_feature_dir` (`phase_teardown.py:393`); focused test committed red first (WP01)
T003 [P] Add defaulted `SeedReport.commit_refused` and `uncommitted_paths`, set in `coord_seed._commit_and_restore` (WP01)
T004 Run named gates, lint, type check; hand back (WP01)

### Implementation Notes

- Tidy-first: each enabler lands before any Track A fix; the teardown test is committed red before its one-line change.
- `SeedReport` is on the `mission_runtime` surface: the field is defaulted and no root export is added.

### Parallel Opportunities

- T002 and T003 touch different files and can proceed in parallel.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Surface gate on `mission_runtime` -> defaulted field, no new export.
- Warning text drift -> build the reason once, keep the sentence byte-identical.

---

## Work Package WP02: Track A: directory alias authority and partition classification (Priority: P1)

**Goal**: One directory alias authority from recorded identity, consumed by the commit-router partition grouping, so the seed commit for a bare-slug coordination Mission lands on the coordination branch.
**Independent Test**: The red `commit_for_mission` test turns green; six negative controls and the canonical characterization pass; the reproduction now fails at the reconciliation gate instead of the dirty-worktree refusal.
**Prompt**: `/tasks/WP02-track-a-alias-authority-and-partition.md`
**Requirement Refs**: FR-002, FR-003, FR-004, FR-005

### Included Subtasks

T005 Red test through `commit_for_mission`: bare-slug composed-directory status files group to PRIMARY (WP02)
T006 [P] Add `mission_dir_aliases` (literal primary directory, declared identity, no new raise) with unit tests (WP02)
T007 [P] `coherence.is_coord_residue_churn` / `is_status_state_path` accept a collection of directory names (WP02)
T008 Resolve aliases once in `_group_files_by_partition`, thread them through the router, one `mid8` derivation in the module (WP02)
T009 [P] Negative controls (FR-004), canonical-unchanged pins (FR-005), base characterization for corrupt / absent / ambiguous metadata and a bare handle (WP02)
T010 Run named gates, lint, type check; record the reproduction's new failure point; hand back (WP02)

### Implementation Notes

- Red first through `commit_for_mission`, then the authority, the pure classifiers, the router threading.
- `src/mission_runtime/artifacts.py` is not edited; the classifiers stay pure and receive names.
- One `mid8` derivation in `commit_router.py` (reconcile with `_resolve_mid8`); no new raise on corrupt, absent or ambiguous metadata; a bare handle on a composed-directory Mission keeps its partition.

### Parallel Opportunities

- T006 and T007 are independent; T009 can be written once T008 is in.

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- Prefix-matched alias -> negative controls.
- Dead-symbol gate -> the router caller lands in the same work package.
- Import cycle -> mirror `surface_resolver.py`.

---

## Work Package WP03: Track A: consolidation consumers and one directory on the target (Priority: P1)

**Goal**: The consolidation consumers accept the alias, and a consolidated bare-slug coordination Mission leaves exactly one Mission directory on the target with the complete event log.
**Independent Test**: `test_bare_slug_coord_mission_consolidates_onto_a_protected_target`, running the real bookkeeping door with its fixture data unchanged, asserts exit 0, teardown, one directory, the event set including `done` and a clean checkout; a `--strategy merge` variant passes.
**Prompt**: `/tasks/WP03-track-a-consolidation-consumers-one-directory.md`
**Requirement Refs**: FR-001, FR-003, FR-004, FR-005, FR-018, FR-019

### Included Subtasks

T011 Switch the #5651 reproduction to the real bookkeeping door and strengthen its end-state assertions (red until T014) (WP03)
T012 After T014: `--strategy merge` variant; add the narrow `_is_bookkeeping` nested-alias leg only if that variant is red without it (WP03)
T013 No run-state field: `run_state.py` / `executor.py` stay unedited unless a consumer with a red proof needs them (WP03)
T014 Fold in the existing bookkeeping commit: remove the composed status pair after an event-preservation assert (`_phase_commit_and_assert`) (WP03)
T015 `phase_bookkeeping.py:567`: convert only with a red proof, else record as follow-up (WP03)
T016 Rewrite the reproduction's docstring, keep `regression`; consumer-to-test revert table (WP03)
T017 Run named gates, lint, type check; report `reconciliation.py` hunk headers; hand back (WP03)

### Implementation Notes

- Execution order T011, T013, T014, T012. `reconciliation.py` is edited only if the `--strategy merge` variant is red without the leg; then only the body of `_is_bookkeeping`, function-local import. Zero diff there is preferred.
- Operator ruling: replacing a mock of in-repository product code with the real path is allowed; the shared helper `_real_merge_external_mocks` is not edited.
- FR-019 mechanism: the composed directory's two status files are unlinked and committed as a deletion in the existing bookkeeping commit, after an event-preservation assert; no new git argv, no run-state field.
- A consumer is converted only with a red proof. STOP: a fold that needs a new destructive git operation, or an edit outside owned files / in a do-not-touch path.

### Parallel Opportunities

- None; the subtasks are sequential on one failure chain.

### Dependencies

- Depends on WP02.

### Risks & Mitigations

- Adjacency to #5668 -> minimal hunk, report hunk headers.
- Whole-directory exemption -> record-kind restriction plus negative controls.
- Destructive fold -> stop and report.

---

## Work Package WP04: Track A: refused seed commit stops consolidate with its real cause (Priority: P2)

**Goal**: A refused coordination seed commit stops consolidate before any branch moves, with `COORD_SEED_COMMIT_REFUSED`, naming the kept files and the retry.
**Independent Test**: A CLI-level test with a commit hook that rejects the seed commit gets exit 1 and the error code; the no-hook control exits 0; the retry after removing the hook commits the seeded files.
**Prompt**: `/tasks/WP04-track-a-refused-seed-backstop.md`
**Requirement Refs**: FR-006

### Included Subtasks

T018 Red CLI test: a commit hook rejects the seed commit, consolidate gives the misleading refusal (WP04)
T019 `COORD_SEED_COMMIT_REFUSED` constant and refusal in `entry_preflight._resolve_run_status_dir` (WP04)
T020 [P] Branch coverage for the refusal, the retry / no-delete proof (I-SEED-10) and the twice-refused case (WP04)
T021 Run named gates, lint, type check; hand back (WP04)

### Implementation Notes

- Reads `SeedReport.commit_refused` and `uncommitted_paths` from WP01; never parses warning text, never names files from `carried`.
- STOP: if the no-hook control cannot exit 0 on a WP01-only base with a composed-primary fixture, report; the fallback is a dependency on WP03.
- Nothing is deleted (I-SEED-10); `executor.py` is not edited.

### Parallel Opportunities

- T020 can proceed alongside T019 once the constant exists. The whole work package runs in parallel with WP02 and WP03.

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- Control cannot go green on a WP01-only base -> stop and report.
- Fixture never seeds -> prove a seed runs first.

---

## Work Package WP05: Track B: runner-relative performance tests (Priority: P1)

**Goal**: The owned-checkout and start-up performance tests assert runner-relative measures with calibrated limits held in one authority module, proven by planted-work tests and recorded in a decision record.
**Independent Test**: 30 of 30 green at a throttle level where the old absolute assertion is red; planted work red 10 of 10 idle and throttled; the owned file takes at most 90 s idle.
**Prompt**: `/tasks/WP05-track-b-runner-relative-performance-tests.md`
**Requirement Refs**: FR-007, FR-008, FR-009, FR-010, FR-012, FR-017, NFR-001, NFR-002, NFR-003

### Included Subtasks

T022 Calibration spike: floor command, throttle method, clean and planted ratio ranges, limits (WP05)
T023 Limit authority and `measure_interleaved` in `tests/_perf_helpers.py`; helper unit tests and the six-nightly-row control in `tests/architectural/test_perf_limit_authority.py` (WP05)
T024 [P] Rewrite the three owned-checkout tests to the ratio assertion (WP05)
T025 Planted-work test through a test-side `sitecustomize` (CPU-bound loop), plant cost asserted between 0.3 and 0.7 of the floor (WP05)
T026 [P] Start-up tests against a fixed interpreter workload; fold the 5.0 s leaf constant into the authority (WP05)
T027 Check that no other test file defines a start-up limit (FR-012), hosted in `tests/architectural/test_perf_limit_authority.py` (WP05)
T028 [P] Track B decision record and `testing-flakiness.md` update (WP05)
T029 30/30 throttled, 10/10 planted, cost at most 90 s; gates, lint; hand back (WP05)

### Implementation Notes

- Starts with a calibration spike; STOP if clean and planted ranges overlap.
- `assert_timing_budget` has 53 importers and stays unchanged.
- Functional tests (helper units, single-authority check, six-nightly-row control) live in `tests/architectural/test_perf_limit_authority.py`: no job runs an unmarked test in `tests/performance`.

### Parallel Opportunities

- T024, T026 and T028 can proceed in parallel after T023 (T028 after T022).

### Dependencies

- None (starting package).

### Risks & Mitigations

- Ranges overlap -> stop and report.
- Marker guard -> assert through the helper.
- Widened limit -> planted tests share the limit constant.

---

## Work Package WP06: Track B: git-subprocess count pin for owned-checkout commands (Priority: P2)

**Goal**: A clock-free pin on the number of git subprocesses each owned-checkout command spawns, in a directory a pull-request job runs.
**Independent Test**: The three exact counts hold over at least three samples; a planted extra call turns the pin red; the job-selection dry run shows the file is selected.
**Prompt**: `/tasks/WP06-track-b-git-subprocess-count-pin.md`
**Requirement Refs**: FR-011

### Included Subtasks

T030 Choose the pin's home from the job-selection dry run; own fixture, in-process CLI runner and git `Popen` counter (WP06)
T031 Sample at least three times, and with sibling files in both orders, then pin the three counts (WP06)
T032 Planted extra git call proves the pin goes red (WP06)
T033 Final `select_modules` / `select_gates` dry run for the three command source paths, residual gap, marker gates, lint; hand back (WP06)

### Implementation Notes

- One new test file; three candidate homes are listed in `owned_files`, exactly one is created, chosen from the job-selection dry run (a change under `cli/commands/agent/` selects `cli` and `execution_context`, not `core_misc`).
- No `performance` marker; no registry or workflow edit; counts sampled alone and with sibling files in both orders.

### Parallel Opportunities

- Runs in parallel with every other work package.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Unstable or order-dependent counts -> remove the nondeterminism or report; never a range.
- Wrong home -> the dry run decides; residual gap recorded.

---

## Work Package WP07: Track C: recipe-shape classifier and per-pull-request home for the gate (Priority: P2)

**Goal**: The commit-recipe gate classifies by recipe shape, keeps all 11 historical recipes flagged, shrinks its allowlist to live hits, and runs in the architectural battery on every `src/specify_cli` change.
**Independent Test**: The moved gate is green on the current tree; a planted recipe turns it red; `select_gates` selects the architectural jobs for three `src/specify_cli` paths; the file runs in under 15 s.
**Prompt**: `/tasks/WP07-track-c-recipe-classifier-and-move.md`
**Requirement Refs**: FR-013, FR-014, FR-015, FR-016, NFR-004, C-011

### Included Subtasks

T034 Tidy-first: move scanner, allowlist and fixture tests to `tests/architectural/`, still red (WP07)
T035 Fixtures: 11 historical recipes verbatim, one positive per FR-013 shape, negatives (WP07)
T036 Recipe-shape classifier wired into the scanner (WP07)
T037 Shrink `_ALLOWED_GIT_COMMIT_HITS` to live hits (WP07)
T038 Proof: `select_gates` dry run, planted recipe, timing under 15 s, gates; hand back (WP07)

### Implementation Notes

- Tidy-first move as its own commit, still red; then fixtures, classifier, allowlist.
- Test files only: nothing under `src/` is edited.

### Parallel Opportunities

- Runs in parallel with every other work package.

### Dependencies

- None (starting package).

### Risks & Mitigations

- False negatives -> per-shape fixtures and the `git add` rule.
- Battery or naming gate objects -> stop and report, no registry edit.

---

## Work Package WP08: Closing records: alias decision record, ADR index, changelog, docs index (Priority: P3)

**Goal**: The Track A decision record, registration of both records, the changelog entry and the regenerated docs index.
**Independent Test**: The docs freshness check and the terminology guard pass; the ADR index has two new rows; the #5651 known-issue line is gone.
**Prompt**: `/tasks/WP08-closing-records.md`
**Requirement Refs**: FR-017

### Included Subtasks

T039 Track A decision record `2026-10-05-1-bare-slug-coordination-directory-alias.md` (WP08)
T040 Register both decision records (ADR index and page inventory) (WP08)
T041 [P] `[Unreleased]` changelog entries; remove the #5651 known-issue line (WP08)
T042 Regenerate the docs retrieval index; docs freshness and terminology checks; follow-up list; hand back (WP08)

### Implementation Notes

- Documentation only; records what WP01 to WP07 actually built.
- `code_change` with docs-only ownership, in its own lane: a planning-lane claim waives code-lane ancestry, so only a code lane receives the approved dependency tips.

### Parallel Opportunities

- T041 can proceed alongside T039.

### Dependencies

- Depends on WP03, WP04, WP05, WP06, WP07.

### Risks & Mitigations

- Dependency content missing in the lane worktree -> report before writing.
- Contended files -> minimal edits.

---

## Dependency & Execution Summary

- **Sequence**: WP01 -> WP02 -> WP03 (Track A spine); WP04 after WP01; WP05, WP06 and WP07 have no dependencies; WP08 after WP03, WP04, WP05, WP06 and WP07.
- **WP08 lane**: WP08 is a `code_change` work package with docs-only ownership in its own code lane, not on the planning lane, so that `implement` merges the approved tips of its five dependency lanes into its worktree.
- **Parallelization**: WP01, WP05, WP06 and WP07 can start together. WP04 runs alongside WP02 and WP03 once WP01 is approved.
- **MVP Scope**: WP01 to WP03 turn the integration job green; WP05 the performance job; WP07 the interpreter-shard and out-of-matrix jobs. All four red nightly jobs need WP01, WP02, WP03, WP05 and WP07.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01, WP03 |
| FR-002 | WP02 |
| FR-003 | WP02, WP03 |
| FR-004 | WP02, WP03 |
| FR-005 | WP02, WP03 |
| FR-006 | WP01, WP04 |
| FR-007 | WP05 |
| FR-008 | WP05 |
| FR-009 | WP05 |
| FR-010 | WP05 |
| FR-011 | WP06 |
| FR-012 | WP05 |
| FR-013 | WP07 |
| FR-014 | WP07 |
| FR-015 | WP07 |
| FR-016 | WP07 |
| FR-017 | WP05, WP08 |
| FR-018 | WP03 |
| FR-019 | WP03 |
| NFR-001 | WP05 |
| NFR-002 | WP05 |
| NFR-003 | WP05 |
| NFR-004 | WP07 |
| C-005 | WP01 |
| C-011 | WP07 |

NFR-005 (code quality) and NFR-006 (no regression in the owning suites) bind every work package through the quality bar and the named validation files in each prompt. C-001 to C-004 and C-006 to C-010 are constraints stated in every prompt; SC-001 and SC-007 are verified at closeout by the orchestrator.

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Record the baseline for the owned tests, gates and the reproduction | WP01 | P1 | No |
| T002 | Teardown reads Mission identity from `run.target_feature_dir` (`phase_teardown.py:393`); focused test committed red first | WP01 | P1 | Yes |
| T003 | Add defaulted `SeedReport.commit_refused` and `uncommitted_paths`, set in `coord_seed._commit_and_restore` | WP01 | P1 | Yes |
| T004 | Run named gates, lint, type check; hand back | WP01 | P1 | No |
| T005 | Red test through `commit_for_mission`: bare-slug composed-directory status files group to PRIMARY | WP02 | P1 | No |
| T006 | Add `mission_dir_aliases` (literal primary directory, declared identity, no new raise) with unit tests | WP02 | P1 | Yes |
| T007 | `coherence.is_coord_residue_churn` / `is_status_state_path` accept a collection of directory names | WP02 | P1 | Yes |
| T008 | Resolve aliases once in `_group_files_by_partition`, thread them through the router, one `mid8` derivation in the module | WP02 | P1 | No |
| T009 | Negative controls (FR-004), canonical-unchanged pins (FR-005), base characterization for corrupt / absent / ambiguous metadata and a bare handle | WP02 | P1 | Yes |
| T010 | Run named gates, lint, type check; record the reproduction's new failure point; hand back | WP02 | P1 | No |
| T011 | Switch the #5651 reproduction to the real bookkeeping door and strengthen its end-state assertions (red until T014) | WP03 | P1 | No |
| T012 | After T014: `--strategy merge` variant; add the narrow `_is_bookkeeping` nested-alias leg only if that variant is red without it | WP03 | P1 | No |
| T013 | No run-state field: `run_state.py` / `executor.py` stay unedited unless a consumer with a red proof needs them | WP03 | P1 | No |
| T014 | Fold in the existing bookkeeping commit: remove the composed status pair after an event-preservation assert (`_phase_commit_and_assert`) | WP03 | P1 | No |
| T015 | `phase_bookkeeping.py:567`: convert only with a red proof, else record as follow-up | WP03 | P1 | No |
| T016 | Rewrite the reproduction's docstring, keep `regression`; consumer-to-test revert table | WP03 | P1 | No |
| T017 | Run named gates, lint, type check; report `reconciliation.py` hunk headers; hand back | WP03 | P1 | No |
| T018 | Red CLI test: a commit hook rejects the seed commit, consolidate gives the misleading refusal | WP04 | P2 | No |
| T019 | `COORD_SEED_COMMIT_REFUSED` constant and refusal in `entry_preflight._resolve_run_status_dir` | WP04 | P2 | No |
| T020 | Branch coverage for the refusal, the retry / no-delete proof (I-SEED-10) and the twice-refused case | WP04 | P2 | Yes |
| T021 | Run named gates, lint, type check; hand back | WP04 | P2 | No |
| T022 | Calibration spike: floor command, throttle method, clean and planted ratio ranges, limits | WP05 | P1 | No |
| T023 | Limit authority and `measure_interleaved` in `tests/_perf_helpers.py`; helper unit tests and the six-nightly-row control in `tests/architectural/test_perf_limit_authority.py` | WP05 | P1 | No |
| T024 | Rewrite the three owned-checkout tests to the ratio assertion | WP05 | P1 | Yes |
| T025 | Planted-work test through a test-side `sitecustomize` (CPU-bound loop), plant cost asserted between 0.3 and 0.7 of the floor | WP05 | P1 | No |
| T026 | Start-up tests against a fixed interpreter workload; fold the 5.0 s leaf constant into the authority | WP05 | P1 | Yes |
| T027 | Check that no other test file defines a start-up limit (FR-012), hosted in `tests/architectural/test_perf_limit_authority.py` | WP05 | P1 | No |
| T028 | Track B decision record and `testing-flakiness.md` update | WP05 | P1 | Yes |
| T029 | 30/30 throttled, 10/10 planted, cost at most 90 s; gates, lint; hand back | WP05 | P1 | No |
| T030 | Choose the pin's home from the job-selection dry run; own fixture, in-process CLI runner and git `Popen` counter | WP06 | P2 | No |
| T031 | Sample at least three times, and with sibling files in both orders, then pin the three counts | WP06 | P2 | No |
| T032 | Planted extra git call proves the pin goes red | WP06 | P2 | No |
| T033 | Final `select_modules` / `select_gates` dry run for the three command source paths, residual gap, marker gates, lint; hand back | WP06 | P2 | No |
| T034 | Tidy-first: move scanner, allowlist and fixture tests to `tests/architectural/`, still red | WP07 | P2 | No |
| T035 | Fixtures: 11 historical recipes verbatim, one positive per FR-013 shape, negatives | WP07 | P2 | No |
| T036 | Recipe-shape classifier wired into the scanner | WP07 | P2 | No |
| T037 | Shrink `_ALLOWED_GIT_COMMIT_HITS` to live hits | WP07 | P2 | No |
| T038 | Proof: `select_gates` dry run, planted recipe, timing under 15 s, gates; hand back | WP07 | P2 | No |
| T039 | Track A decision record `2026-10-05-1-bare-slug-coordination-directory-alias.md` | WP08 | P3 | No |
| T040 | Register both decision records (ADR index and page inventory) | WP08 | P3 | No |
| T041 | `[Unreleased]` changelog entries; remove the #5651 known-issue line | WP08 | P3 | Yes |
| T042 | Regenerate the docs retrieval index; docs freshness and terminology checks; follow-up list; hand back | WP08 | P3 | No |
