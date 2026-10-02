---
description: "Work package task list for Mission coord-artifact-single-home-01M3V4BE"
---

# Work Packages: Coordination artifacts get one durable home

**Inputs**: Design documents from `/kitty-specs/coord-artifact-single-home-01M3V4BE/`
**Prerequisites**: plan.md (IC-01..IC-18, shared-file map), spec.md (rev 5: US1-US6, FR-001..FR-017), research.md (D1-D23, red-first R1-R24 + R1d, NFR-001 baseline), data-model.md, contracts/ (write-location-accessor, seed, commit-outcome, doctor-decisions-fork-report), quickstart.md

**Tests**: Required. The charter's ATDD-First Discipline (C-011) and spec C-005 / FR-016 apply: every code work package opens with a red-first reproduction through the pre-existing entry point, committed before the fix. The reviewer verifies RED on the work package's base and GREEN on its final commit. Test runs are targeted (C-006, `NO_FULL_HEAVY_SUITES_IN_MISSION`). Never run the bare `tests/architectural/`, an e2e or integration directory, or `make test-full`.

**Red evidence per WP (analyze C2)**:

| WP | Red evidence the reviewer checks |
|----|----------------------------------|
| WP01 | Exempt: tidy-first, behaviour-preserving. Same tests and same results before and after, with lower C901 (the moved tidy-first commits T002/T003/T004 in WP13/WP14/WP15 follow the same rule) |
| WP02 | Exempt: test harness; its self-tests are green by design |
| WP03–WP19 | The red-first test(s) named in the prompt are RED on the WP's lane base (its `planning_base_branch` plus stacked dependency lanes) and GREEN on its final commit. Forward guards (e.g. R20, R1d, WP12's recency guard) are labelled as such and shown red on the intermediate commit the prompt names |
| WP19 | First reproduce the receipt defect through the CLI. If the coordination-Mission premise does not reproduce, the red comes from the lanes/single_branch `sha=None` receipt and the finding is reported (never a faked red) |
| WP20 | RED at `ecb5dd914a` on the real offenders (`decisions/emit.py::_mission_dir`, `decisions/service.py::_mission_dir`) plus the planted mutation; GREEN on the final tree |
| WP21 | REQUIRED: the SC-001 history probe and the single-log assertion RED on the planning base (pre-Mission product code), GREEN on the final tree |
| WP22 | Exempt: documentation; FR-017 is anchored on the cited ADR sections |

**Brownfield scout notes (binding per-WP corrections)**: `research/brownfield-scout-wp01-11.md` and `research/brownfield-scout-wp12-22.md`. Each prompt points to its `## WPxx` section and folds the corrections into a "Binding corrections — analyze + brownfield scout (round 3)" section.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work package is independently deliverable and testable.

**Prompt Files**: Each work package references a matching prompt file in `/tasks/`. Treat this file as the high-level checklist; the deep implementation detail lives in the prompt files.

**Base revision for line references**: `ecb5dd914a`. The Mission branch was rebased onto `bc826fcbcb`; none of the Mission's source files changed in between.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Include precise file paths or modules.
- Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`. The reduced event-log snapshot is the sole subtask-completion authority — there is no `- [ ]` box to tick.

## Path Conventions

- **Single project**: `src/` (layered `kernel ← charter ← {glossary, runtime, mission_runtime} ← specify_cli`), `tests/` mirroring the source tree.
- Every path below is repository-root-relative.

## Lane notes (lanes.json ids; analyze I14)

`owned_files` overlap only between **dependency-ordered** work packages, where the plan's shared-file map asks for one lane. The ownership validator exempts those pairs, and lane computation places them in one lane. The lanes and lane dependencies below are exactly as computed in `lanes.json`.

| Lane | WPs (in order) | Depends on lanes | Shared file(s) / note |
|------|----------------|------------------|-----------------------|
| lane-b | WP02 | — | root |
| lane-i | WP11 | — | root |
| lane-c | WP03 | lane-b | |
| lane-a | WP01 → WP04 → WP05 | lane-c | `surface_resolver.py`, `commit_router.py`. **lane-a starts after lane-c (WP03)**, so WP01, although it has no WP dependency of its own, does not start concurrently with the roots |
| lane-d | WP06 | lane-a | |
| lane-j | WP12 | lane-a, lane-i | |
| lane-k / lane-l / lane-m | WP13 / WP14 / WP15 | lane-a | own lanes after the P-m7 move of T002/T003/T004 |
| lane-o | WP07 → WP09 → WP17 → WP18 | lane-a, lane-j | `test_coord_read_seam_callers.py` (WP07 L259, WP09 L198), `cli/commands/decision.py` (WP09, then WP17), `consolidation/executor.py` (IC-12 before IC-18) |
| lane-f | WP19 → WP08 | lane-b, lane-o | `cli/commands/agent/workflow.py` (WP08 may fix the reject→fix-mode readers) |
| lane-h | WP10 | lane-a, lane-o | |
| lane-n | WP16 | lane-a, lane-h, lane-j | |
| lane-p | WP20 | lane-d, lane-f, lane-h, lane-k, lane-l, lane-m, lane-n, lane-o | |
| lane-q | WP21 | lane-d, lane-f, lane-n, lane-o, lane-p | |
| lane-planning | WP22 | lane-q | docs only (`planning_artifact`) |

- **Single owners**:
  - `tests/architectural/test_no_read_side_bypass.py` is WP07's; WP10 depends on WP07 and removes its own entry as a declared out-of-map edit.
  - `coordination/write_seam.py` is WP10's; WP16 depends on WP10 and updates its docstring L55 as a declared out-of-map edit.
  - `mission_runtime/write_target_degrade.py`, `mission_runtime/__init__.py` and `test_mission_runtime_surface.py` are WP03's (single write authority; package-root re-exports).
- **P-m7**: the T002/T003/T004 extractions are each WP's tidy-first first commit in WP13/WP14/WP15. Subtask ids keep their global numbers.
- **Declared out-of-map edit**: WP07 updates two tests in `tests/coordination/test_commit_router.py` (≈L953, ≈L1012) that import `status_transition._coord_feature_dir`, which WP07 deletes. That file belongs to lane-a, which completes before lane-o starts.
- Every other pair of work packages has disjoint ownership.

---

## Work Package WP01: Campsite-clean the functions this Mission changes (Priority: P0)

**Goal**: Record the C901 baseline for every function the Mission touches, and make behaviour-preserving extractions in the router and the anchor resolver so that no touched function crosses C901 15 (IC-01, Standing Order 2). The other extractions are the first commits of WP13/WP14/WP15 (P-m7).
**Independent Test**: The same tests pass before and after with no assertion edits, and the C901 numbers for the two target functions go down.
**Prompt**: `/tasks/WP01-campsite-clean-touched-god-surfaces.md`
**Requirement Refs**: NFR-003, NFR-004, NFR-005
**Estimated prompt size**: ~350 lines

### Included Subtasks

T001 Baseline C901 table and green test counts before any edit, covering all functions in the plan's IC-01 table plus `_commit_planning_pin_refresh_locked` (WP01)
T005 Extract the per-path classify/translate step from `_stage_artifacts_in_coord_worktree` (`commit_router.py:991`) (WP01)
T006 Extract the coordination-state branch from `resolve_status_surface_with_anchor` (`surface_resolver.py:1192`), keeping it pure (WP01)
T007 Behaviour-preservation proof: same tests, C901 after-table, ruff/format/mypy --strict (WP01)

### Implementation Notes

- One commit per extraction. Each extraction stays inside its own file (locality), and each extracted helper gets a focused test.
- ~~Leave `record_analysis` (C901 13) alone~~ (struck, round 4: WP14 extracts its suppress-and-commit block first; plan IC-01 corrected).

### Parallel Opportunities

- T005 and T006 touch different files and can be done in any order.

### Dependencies

- None at WP level. Per lanes.json, its lane-a depends on lane-c, so it starts after WP03 (analyze I14).

### Risks & Mitigations

- Hidden behaviour change during extraction → no assertion edits are allowed; the full owning-module test files must give identical results.

---

## Work Package WP02: Shared coordination-routed Mission fixture harness (Priority: P0)

**Goal**: Provide one importable factory for coordination-routed Missions created through the production create path, plus builders for the pre-fix shape and the NFR-002 fork fixtures (IC-02).
**Independent Test**: The self-tests in `tests/coordination/test_coord_mission_factory.py` prove each builder yields its documented shape.
**Prompt**: `/tasks/WP02-coord-mission-fixture-harness.md`
**Requirement Refs**: FR-016, C-005, NFR-002
**Estimated prompt size**: ~300 lines

### Included Subtasks

T008 [P] Importable factory `tests/_factories/coord_mission.py`, parametrized over `coord` / `lanes_with_coord` and the CLI `--pr-bound --start-branch` path (WP02)
T009 Pre-fix shape builder (root log, coordination branch without the Mission dir; UNMATERIALIZED / EMPTY / remote-only / DELETED variants) (WP02)
T010 NFR-002 fork-fixture builders (four shapes) plus event-id, lamport and history probes (WP02)
T011 `tests/coordination/conftest.py` fixtures and the factory self-tests (WP02)

### Implementation Notes

- The pre-fix builder constructs its shape explicitly, so it stays valid after WP06 changes create.

### Parallel Opportunities

- Runs in parallel with WP11 from the start (lane-b and lane-i are the only roots in lanes.json). WP19 follows this WP, and WP01's lane-a waits for lane-c (WP03).

### Dependencies

- None (starting package).

### Risks & Mitigations

- Slow git fixtures → reuse the repository's git template support and keep builders cheap.

---

## Work Package WP03: Coordination write-location core — establish, seed, refuse (Priority: P1)

**Goal**: Implement `establish_coord_write_location` and `seed_coord_surface`, the one place that materializes, seeds (prefix rule, atomic, exactly once, durable) or refuses (IC-03 part 1).
**Independent Test**: `tests/coordination/test_coord_seed.py` covers the state × outcome matrix, the prefix/fork rule, idempotence, atomic visibility, root restoration, lock reentrancy and the NFR-002 fixtures.
**Prompt**: `/tasks/WP03-coord-seed-and-establish-core.md`
**Requirement Refs**: FR-003a, FR-004, FR-004a, FR-004b, C-001, C-003, C-004, NFR-002
**Estimated prompt size**: ~450 lines

### Included Subtasks

T012 Red-first state-matrix tests; `WriteLocation`, `Establishment`, `SeedReport`, `CoordSeedForkRefused`; `STATUS_LOCK_HELD` error code (WP03)
T013 Prefix rule as pure functions per log stream (WP03)
T014 `seed_coord_surface`: lock, re-probe, stale-temp cleanup, collect, coordination side, temp dir plus one `os.rename` (WP03)
T015 Seed commit on the coordination branch and root-checkout restoration (WP03)
T016 `establish_coord_write_location` state machine (materialize / refuse remote-only / refuse deleted / seed / restore-from-branch) (WP03)
T017 Complete the test matrix with the WP02 builders (WP03)

### Implementation Notes

- `SeedReport` lives in `mission_runtime/write_location.py`, because `WriteLocation` references it.
- Lock order follows I-SEED-2: materialize, release the workspace lock, then take the reentrant status lock.

### Parallel Opportunities

- T013 (pure functions) can proceed alongside T012.

### Dependencies

- Depends on WP02.

### Risks & Mitigations

- Lock-order inversion → covered by the reentrancy and nesting tests.
- A partial seed being visible → the temp-dir build plus a single rename.

---

## Work Package WP04: PlacementSeam.write_dir and the loud post-fix EMPTY surface (Priority: P1)

**Goal**: Add the single sanctioned seam extension, `PlacementSeam.write_dir(kind) -> WriteLocation`, make the read-side EMPTY warning loud for post-fix Missions, and fix the stale seam docstrings (IC-03 part 2).
**Independent Test**: Property tests show `write_dir`/`write_target` agreement over every kind and topology; `read_dir`, `write_target` and `resolve_placement_only` stay side-effect-free; the post-fix EMPTY warning fires in both coordination topologies.
**Prompt**: `/tasks/WP04-placement-seam-write-dir.md`
**Requirement Refs**: FR-003, FR-003a, C-001, C-002, C-008, FR-017
**Estimated prompt size**: ~380 lines

### Included Subtasks

T018 Red-first and `PlacementSeam.write_dir` (PRIMARY short-circuit; lazy delegate for COORD kinds) (WP04)
T019 Owned-checkout arm (WP04)
T020 Property tests: write_dir/write_target agreement, C-008 byte-identical answers, purity of the existing seams (WP04)
T021 Loud EMPTY warning for post-fix Missions in both coordination topologies; read fallback kept (WP04)
T022 Stale seam docstrings and the `CoordState.EMPTY` contract text (WP04)

### Implementation Notes

- The `mission_runtime` outbound ledger must not grow; the existing `coordination` edge is reused.

### Parallel Opportunities

- T021 and T022 are independent of T018–T020.

### Dependencies

- Depends on WP01, WP03.

### Risks & Mitigations

- Accidental side effects in read paths → the purity assertions in T020.

---

## Work Package WP05: Commit router — retire the target fast-forward, per-surface outcomes, owning-surface commits (Priority: P1)

**Goal**: "Unchanged" means unchanged. A COORD record passed by its repository-root path is judged and committed on its coordination copy, or refused for a named reason. Every surface's outcome is carried in the shared result contract. The router's target fast-forward is retired. Subtask order IC-10 → IC-07 core → IC-06 is a **stated deviation** from plan.md's 10 → 06 → 07 (analyze I5): R2's tightened refusal assertion needs `surfaces` first; IC-07's consumer migration still follows IC-06 in later WPs.
**Independent Test**: R12, the adopted R2/R2b (tightened), and the per-reason refusal tests.
**Prompt**: `/tasks/WP05-commit-router-owning-surface-outcomes.md`
**Requirement Refs**: FR-006, FR-007, FR-008, FR-016, SC-003
**Estimated prompt size**: ~480 lines

### Included Subtasks

T023 IC-10: red-first R12, then delete `_try_advance_ref` and the post-commit advance (WP05)
T024 `coordination/commit_outcome.py`: `PathFate`, `SurfaceOutcome`, reason codes, renderer, payload, exit-code helper (WP05)
T025 `CommitRouterResult.surfaces`, populated by `_merge_group_results` (WP05)
T026 Adopt R2/R2b (`git cherry-pick -x 251bea520f`) and tighten the refusal branch (WP05)
T027 IC-06: translate root-path STATUS_STATE / DECISION_LOG inputs to the owning surface via `write_dir` (WP05)
T028 Owning-surface dirt classification; `COORD_RECORD_IN_ROOT_CHECKOUT` skip fate (WP05)
T029 Named refusals (`STATUS_LOCK_HELD`, `PROTECTED_BRANCH_REFUSED`, `COORDINATION_BRANCH_DELETED`, `PATH_UNROUTABLE`, `WRONG_SURFACE`); the split path forwards `owned` (WP05)

### Implementation Notes

- The `surfaces` field is additive; the legacy top-level fields keep today's caller-surface selection.
- Never copy a root log over the coordination log.

### Parallel Opportunities

- T024 (new module) can be written alongside T023.

### Dependencies

- Depends on WP01, WP04.

### Risks & Mitigations

- `commit_router.py` is shared with WP01 (lane A) → sequential by dependency.

---

## Work Package WP06: Create materializes and seeds the coordination surface; expected-divergence model (Priority: P1) 🎯 MVP

**Goal**: The coordination branch carries the creation records from birth and the target branch never does. Protected-target create still seeds, and rollback undoes the seed. `doctor coordination` and `ensure_coordination_branch` expect the by-design divergence (IC-05).
**Independent Test**: The adopted R1/R1b, the R1c re-pin, R6 with its legacy control, R20 with its legacy control, and the protected-target and rollback tests; NFR-001 medians are recorded.
**Prompt**: `/tasks/WP06-create-seeds-coordination-surface.md`
**Requirement Refs**: FR-001, FR-002, FR-002a, FR-002b, FR-016, NFR-001, C-008
**Estimated prompt size**: ~480 lines

### Included Subtasks

T030 Adopt R1/R1b (`git cherry-pick -x 31ea4681f7`), parametrized over both coordination topologies and the pr-bound path (WP06)
T031 Create flow: `write_dir(STATUS_STATE)`, emit the creation events there, commit on the coordination branch, drop the status log from the target scaffold (WP06)
T032 Protected-target seed outside the bootstrap suppression; rollback removes the coordination worktree and the seed (WP06)
T033 R1c re-pin (~~S9 topology check~~ struck: create defaults to COORD) plus an explicit `lanes` control; R6 no-warning-after-create plus the legacy control (WP06)
T034 `is_expected_coordination_divergence` predicate; `ensure_coordination_branch` accepts it (WP06)
T035 `doctor coordination` finding uses the predicate; R20 plus the genuinely-diverged control (WP06)
T036 NFR-001 re-measure against the research baseline (manual; recorded for the PR) (WP06)

### Implementation Notes

- `meta.json` and `tasks/*` stay on the target branch (positive control).
- The NFR-001 budget is the base median + 1.0 s for each of the four configurations.

### Parallel Opportunities

- T034/T035 (divergence model) are independent of T031/T032 once T030 lands.

### Dependencies

- Depends on WP05.

### Risks & Mitigations

- Create latency → one extra `git worktree add` plus one commit, measured against the budget.
- Rollback across two refs → injected-failure tests.

---

## Work Package WP07: Transactional status writers and the tasks-port write location (Priority: P1)

**Goal**: The transactional status path, `move-task`'s port and lanes recovery take their write location from `write_dir`, so no status write lands in the repository root checkout of a coordination-routed Mission in any coordination-surface state (IC-04).
**Independent Test**: CLI `move-task` across the UNMATERIALIZED-local, pre-fix EMPTY, remote-only, DELETED and forked-MATERIALIZED states.
**Prompt**: `/tasks/WP07-transactional-status-writers.md`
**Requirement Refs**: FR-003, FR-003a, FR-007, C-008
**Estimated prompt size**: ~400 lines

### Included Subtasks

T037 Red-first state-matrix tests through CLI `move-task` (WP07)
T038 `status_transition.py`: retire `_coord_feature_dir` and the fallback composition in favour of `write_dir` (WP07)
T039 `transaction.py` `_acquire_locked` uses `write_dir` under the held status lock (WP07)
T040 `agent_tasks_ports.py`: `feature_write_dir` becomes kind-aware via `write_dir`; `CommitArtifactResult.surfaces` passthrough (WP07)
T041 `lanes/recovery.py` `reconcile_status` uses `write_dir` (WP07)
T042 C-008 controls, lock-reentrancy and no-root-residue tests (WP07)

### Implementation Notes

- No second composer of the coordination Mission dir may remain.

### Parallel Opportunities

- T041 is independent of T038–T040.

### Dependencies

- Depends on WP05.

### Risks & Mitigations

- Deadlock between the status lock and the workspace lock → I-SEED-2 ordering plus the reentrancy test.

---

## Work Package WP08: Review-cycle, mark-status and map-requirements — write location and outcomes (Priority: P2)

**Goal**: Review-cycle records and mark-status events are written in place on the coordination surface with no root residue, and the tasks-port consumers render every surface's outcome (IC-04 and IC-07).
**Independent Test**: Review-cycle and mark-status write-location tests, plus a one-surface-skipped rendering test per consumer.
**Prompt**: `/tasks/WP08-review-cycle-and-tasks-port-writers.md`
**Requirement Refs**: FR-003, FR-007, SC-003
**Estimated prompt size**: ~350 lines

### Included Subtasks

T043 Red-first: review-cycle written in place with no root residue; mark-status lands on the coordination surface; a skipped surface is rendered (WP08)
T044 `review/cycle.py` writers use `write_dir(REVIEW_CYCLE)`; the stage-in-root copy is removed (WP08)
T045 `tasks_mark_status.py` read/write split (WP08)
T046 Render outcomes at `review/cycle.py:712` and `tasks_map_requirements.py:668`; mark-status renders nothing (its live write path commits nothing; the L279 shim is dead) (WP08)
T047 Consumer, residue and C-008 tests (WP08)

### Implementation Notes

- Uses `CommitArtifactResult.surfaces` from WP07 and the shared renderer from WP05.

### Parallel Opportunities

- T045 and T044 touch different files.

### Dependencies

- Depends on WP07, WP19 (WP19 first: both own `workflow.py`; the shared file puts them in one lane).

### Risks & Mitigations

- The review-cycle fallback path has no production caller → test through the real CLI entry point.

---

## Work Package WP09: Decision event writers move to the accessor (Priority: P1)

**Goal**: Decision events in the status log and the `decisions.events.jsonl` stream are written at `write_dir`, so decision → tracer → decision keeps one log with a continuing logical clock (#5519) (IC-04).
**Independent Test**: R4 plus the decision-writer state matrix.
**Prompt**: `/tasks/WP09-decision-event-writers.md`
**Requirement Refs**: FR-003, FR-003a, FR-016, SC-002
**Estimated prompt size**: ~380 lines

### Included Subtasks

T048 Red-first R4: decision → tracer → decision keeps one log and a monotonic clock (WP09)
T049 `decisions/emit.py` `_mission_dir` uses `write_dir` (WP09)
T050 `decisions/service.py` `_mission_dir` uses `write_dir`; the direct materialize calls are dropped; the ledger dir is untouched (WP09)
T051 `runtime_bridge._wrap_with_decision_git_log` and `events/decision_log.py` use `write_dir(DECISION_LOG)`; slug/mid8 agreement (WP09)
T052 State matrix for both decision streams, the ledger-PRIMARY control and C-008 controls (WP09)

### Implementation Notes

- The `runtime` outbound ledger is shrink-only; reach the seam through an allowed edge.

### Parallel Opportunities

- T049/T050 and T051 touch different files.

### Dependencies

- Depends on WP04, WP07 (WP07 re-pins `tests/mission_runtime/test_coord_read_seam_callers.py` first; P-M1).

### Risks & Mitigations

- The `<slug>` vs `<slug>-<mid8>` dir-name mismatch → an explicit agreement test.

---

## Work Package WP10: Write-seam writers — tracer, issue matrix, acceptance matrix (Priority: P2)

**Goal**: Tracer files and both matrices are written in place at `write_dir(kind)` with no root residue, and the write-seam result carries every surface's outcome (IC-04 and IC-07).
**Independent Test**: Write-location and no-residue tests per writer; one-surface-skipped rendering per consumer.
**Prompt**: `/tasks/WP10-write-seam-writers-tracer-matrices.md`
**Requirement Refs**: FR-003, FR-007, SC-003
**Estimated prompt size**: ~420 lines

### Included Subtasks

T053 Red-first: in-place writes with no root residue for tracer, issue matrix and acceptance matrix; a skipped surface is rendered (WP10)
T054 `WriteSeamResult.surfaces` passthrough (WP10)
T055 Tracer writer uses `write_dir(TRACER_FILE)`; render at L298 (WP10)
T056 Issue matrix uses `write_dir(ISSUE_MATRIX)`; render at L404 (WP10)
T057 Acceptance verdict and matrix use `write_dir(ACCEPTANCE_MATRIX)`; render at L524 (WP10)
T058 Transient-staging, rendering and C-008 tests (WP10)

### Implementation Notes

- Reads keep the read resolvers; only write locations move.

### Parallel Opportunities

- T055, T056 and T057 touch different files.

### Dependencies

- Depends on WP05, WP07 (WP07 owns `tests/architectural/test_no_read_side_bypass.py`; this WP removes its own stale entry after it).

### Risks & Mitigations

- Root residue left by stage-and-copy → asserted after every command returns.

---

## Work Package WP11: Decision index merge driver (Priority: P2)

**Goal**: Add a `spec-kitty-decision-index` merge driver (keyed union by `decision_id`, fold precedence, deterministic order), registered in every driver surface, seeded by `init`, shipped by an upgrade migration (IC-11, FR-009b lane merge).
**Independent Test**: R21: two lanes adding decisions merge with no lost entry; the migration tests.
**Prompt**: `/tasks/WP11-decision-index-merge-driver.md`
**Requirement Refs**: FR-009b
**Estimated prompt size**: ~380 lines

### Included Subtasks

T059 Red-first R21 through a real `git merge` with the driver configured (WP11)
T060 Union function using the `index_fold` precedence; deterministic output; malformed input fails (WP11)
T061 Register the driver: `_MERGE_DRIVERS`, `MERGE_DRIVER_BODIES`, the `merge-driver-decision-index` CLI (WP11)
T062 Init seed and `.gitattributes` line (WP11)
T063 Upgrade migration `m_4_0_0rc5_decision_index_merge_driver.py` and its tests (WP11)

### Implementation Notes

- Merge drivers shell out to `spec-kitty`: reinstall (`uv sync` / `pip install -e .`) before trusting a red.

### Parallel Opportunities

- Runs in parallel with WP01–WP04 from the start.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Migration `target_version` above the installed package version → follow the m_3_2_7 rationale.

---

## Work Package WP12: Decision ledger reclassified to the PRIMARY partition (Priority: P2)

**Goal**: The decision ledger is a PRIMARY-partition record in the taxonomy. Every reader that flips is pinned by a focused test, the ledger write/read ratchet holds, and the two architectural guards are amended (IC-11, FR-009/009a).
**Independent Test**: R13, the commit-router grouping of the ledger, the reader-flip tests, and the FR-009a ratchet.
**Prompt**: `/tasks/WP12-decision-ledger-primary-partition.md`
**Requirement Refs**: FR-009, FR-009a, FR-009b, FR-017, C-008
**Estimated prompt size**: ~400 lines

### Included Subtasks

T064 Red-first R13, the ledger commit-grouping test and the spec-commit ledger-on-target test (WP12)
T065 Move `DECISION_LEDGER` to `_PRIMARY_ARTIFACT_KINDS`; rewrite the stale #3928 comments (WP12)
T066 Reader-flip focused tests (research D12); re-pin stale tests that pinned the old classification (WP12)
T067 FR-009a ratchet: ledger writes and reads stay PRIMARY (WP12)
T068 Amend `test_write_surface_placement_guard.py` and `test_merge_reconciliation_class_guard.py` (WP12)

### Implementation Notes

- Behaviour change: the accept and consolidation dirty gates now treat uncommitted ledger files as real work. WP16 and WP17 complete those legs.

### Parallel Opportunities

- T066 and T067 are independent test files.

### Dependencies

- Depends on WP05, WP11.

### Risks & Mitigations

- The broadest behaviour flip (~20 readers) → each reader pinned; stale pins re-pinned in this WP, never left red.

---

## Work Package WP13: spec-commit names every argument's fate (Priority: P1)

**Goal**: `spec-commit` text and JSON name each argument's fate. Planning files are committed on the target branch, and ledger files on the surface the taxonomy assigns them (the target branch once WP12 lands; WP12 owns that assertion); traces and the status log are committed on the coordination branch or refused with a named reason (#5501). The `--target-branch` help no longer claims a fast-forward (IC-07, IC-10).
**Independent Test**: R5 plus the mixed-refusal, clean-control and C-008 tests.
**Prompt**: `/tasks/WP13-spec-commit-argument-fates.md`
**Requirement Refs**: FR-007, FR-007a, FR-016, SC-003
**Estimated prompt size**: ~320 lines

### Included Subtasks

T002 Tidy-first: extract helpers from `spec_commit_command` (`spec_commit_cmd.py:155`, C901 15); moved from WP01 (WP13)
T069 Red-first R5 through the `spec-commit` CLI, on a `materialized=True` fixture with its preconditions asserted (WP13)
T070 `_payload`: additive `surfaces` and `arguments[]`; `success=false` on any refusal (WP13)
T071 Text output through the shared renderer; exit-code rule (WP13)
T072 `--target-branch` help text (WP13)
T073 Mixed-refusal, clean-control and C-008 tests (WP13)

### Implementation Notes

- The render step lives in the helper WP01 extracted; replace it there.

### Parallel Opportunities

- None inside the WP (single file).

### Dependencies

- Depends on WP05. It deliberately does not depend on WP12; WP12 owns the "spec-commit commits the ledger on the target" assertion (a WP13 → WP12 edge created a lane dependency cycle before the P-m7 move, and is unnecessary now).

### Risks & Mitigations

- `success` may newly be `false` → only when a surface was refused, which is the defect being fixed.

---

## Work Package WP14: Planning-command and retrospect consumers render per-surface outcomes (Priority: P2)

**Goal**: setup-plan, record-analysis, the report transaction, the orchestrator API and retrospect report every surface's outcome through the shared renderer. Retrospect appends use `write_dir` (IC-07, IC-04).
**Independent Test**: R11 (retrospect half), plus one-surface-skipped tests per consumer.
**Prompt**: `/tasks/WP14-planning-command-outcome-consumers.md`
**Requirement Refs**: FR-003, FR-007, FR-016, SC-003
**Estimated prompt size**: ~380 lines

### Included Subtasks

T003 Tidy-first: extract helpers from `record_report_transaction` (`git/report_transaction.py:130`, C901 15); moved from WP01 (WP14)
T074 Red-first R11 (retrospect), the setup-plan masking test and the retrospect write location, with fixture preconditions asserted (WP14)
T075 setup-plan renders at L237; warnings at the discarded sites L892/L951 (WP14)
T076 record-analysis (L374), orchestrator API (L3018) and the report transaction (L199) render through the shared pair (WP14)
T077 Retrospect read/append split via `write_dir`; render at L315 (WP14)
T078 Consumer tests; JSON stays additive; C-008 controls (WP14)

### Implementation Notes

- ~~Do not touch the body of `record_analysis`~~ (struck, round 4): first extract its suppress-and-commit block (L355-391, C901 13) into a private helper, then render there.

### Parallel Opportunities

- T075, T076 and T077 touch different files.

### Dependencies

- Depends on WP05.

### Risks & Mitigations

- Discarded-result sites may get noisy → warn only when a surface is not committed/unchanged.

---

## Work Package WP15: finalize-tasks — write location, coordination dirt, per-surface output, planning-commit refresh (Priority: P1)

**Goal**: Finalize lifecycle events land in the coordination log. Finalize sees coordination-only dirt and reports every surface, and it refreshes `planning_commit_sha` by default, warning and continuing when the automatic refresh is refused (IC-04/07/09/13).
**Independent Test**: R10, R11 (finalize half), R17 plus its control, the US5.3 refused-refresh test and US2.2.
**Prompt**: `/tasks/WP15-finalize-tasks-single-home.md`
**Requirement Refs**: FR-003, FR-007, FR-007b, FR-012, FR-016, SC-003
**Estimated prompt size**: ~450 lines

### Included Subtasks

T004 Tidy-first: extract helpers from `finalize_tasks` (`mission_finalize.py:4758`, C901 14), `_commit_planning_pin_refresh_locked` (`mission_finalize.py:2807`, C901 15) and `_ft_apply_writes` (`tasks_finalize.py:250`, C901 14); moved from WP01 (WP15)
T079 Red-first R10, R11, R17 (plus control), US5.3 and US2.2 through the finalize-tasks CLI, with fixture preconditions asserted (WP15)
T080 `_emit_local_canonical_events` and `_ft_apply_writes` use `write_dir(STATUS_STATE)` (WP15)
T081 Coordination-worktree porcelain in `_resolve_finalize_commit_candidates` (WP15)
T082 Per-surface output (`commit_surfaces`), including the pin-refresh consumer (WP15)
T083 Default refresh when the planning artefacts changed (reusing the existing refresh flow) (WP15)
T084 A refused automatic refresh warns and continues; an explicit flag refusal still fails; `planning_commit_refresh` JSON (WP15)

### Implementation Notes

- Keep `finalize_tasks` at C901 ≤ 15; the refresh decision goes in a new helper.

### Parallel Opportunities

- T083/T084 are independent of T080–T082 inside the same file (sequence the commits).

### Dependencies

- Depends on WP05.

### Risks & Mitigations

- The warn-and-continue arm swallowing an explicit-flag refusal → a dedicated test.

---

## Work Package WP16: accept — both residual legs through the commit router (Priority: P1)

**Goal**: Remove accept's raw commit. Both residual legs go through one `commit_for_mission` call; the dirty gate and the committer share one classifier; the birth cutover uses `write_dir` (IC-08).
**Independent Test**: R7, R8 and R9 (each leg proven separately) plus the committed-ledger control.
**Prompt**: `/tasks/WP16-accept-residual-legs-via-router.md`
**Requirement Refs**: FR-003, FR-005, FR-007, FR-009, SC-003, FR-009b
**Estimated prompt size**: ~400 lines

### Included Subtasks

T085 Red-first R7, R8 and R9 through the `accept` CLI (WP16)
T086 Remove `_commit_primary_residuals`; one router call over both legs; fix the L425 join; forward `owned` (WP16)
T087 `COORD_RECORD_IN_ROOT_CHECKOUT` reporting; the ledger is committed on the target; `residual_commit` JSON (WP16)
T088 One shared classifier for `_filter_coordination_residue` and the committer; render at L1791/L1822 (WP16)
T089 Birth cutover via `write_dir`; C-008 controls (WP16)

### Implementation Notes

- Accept fixtures need lanes plus a passing acceptance matrix (the #4891 pattern).
- The dirty gate calls WP05's public per-path partition predicate; no new classifier (P-M5). Red reasons are re-derived on this WP's real lane base (R-M6).
- C901 watch: `accept.py::_print_acceptance_result` (13).

### Parallel Opportunities

- T089 is independent of T086–T088.

### Dependencies

- Depends on WP05, WP12, WP10 (declared out-of-map docstring edit to `write_seam.py:55`).

### Risks & Mitigations

- Operator-visible change (accept now commits an uncommitted ledger) → intended (FR-009) and called out in the PR.

---

## Work Package WP17: doctor decisions fork detection, honest verify, non-destructive repair, teardown and preflight refusal (Priority: P1)

**Goal**: One read-only fork detector serves `doctor decisions`, `decision verify`, teardown and the consolidation preflight. Repair never drops a decision and heals coordination-only ledgers additively (IC-12).
**Independent Test**: R3, R14, R15 and R16 over the four NFR-002 fixtures; the unforked-orphan positive control.
**Prompt**: `/tasks/WP17-decisions-doctor-fork-detection.md`
**Requirement Refs**: FR-009c, FR-010, FR-010a, FR-011, FR-016, SC-004, NFR-002, C-003
**Estimated prompt size**: ~480 lines

### Included Subtasks

T090 Red-first R3, R14, R15 and R16 (WP17)
T091 `decisions/fork.py` `detect_decision_forks` (refs plus worktrees, both streams, read-only) (WP17)
T092 `coordination_only_ledger` (WP17)
T093 `_diagnose`: union orphan rule; additive fork report (WP17)
T094 `_repair`: never drop; forked prints reconcile steps and exits 1; coordination-only ledger copied additively (WP17)
T095 `decision verify` reports `DECISION_LOG_FORKED` (WP17)
T096 Teardown and pre-mutation preflight refuse `COORDINATION_LEDGER_UNREPAIRED`; the ledger-dirt gate message names accept/spec-commit (WP17)

### Implementation Notes

- The detector never materializes or writes, so it works in a fresh clone.

### Parallel Opportunities

- T091/T092 (new module) can be built before the consumers T093–T096.

### Dependencies

- Depends on WP12, WP09 (the decision-stream dir-name ruling; P-M4).

### Risks & Mitigations

- `executor.py` is shared with WP18 (lane B) → only the preflight and message edits land here.

---

## Work Package WP18: Consolidation executor and materialize writers move to the accessor (Priority: P2)

**Goal**: The consolidation executor's status writes and `materialize`'s `status.json` stop deriving their write location from read resolvers. `--resume`, dry-run and the rollback machinery stay intact (IC-18, ruling Q4).
**Independent Test**: The R1d characterization, R22, the R23 re-pin, R24 plus its control, and the named consolidation guard files.
**Prompt**: `/tasks/WP18-consolidation-materialize-writers.md`
**Requirement Refs**: FR-003, FR-014, FR-016, NFR-002, C-008
**Estimated prompt size**: ~450 lines

### Included Subtasks

T097 R1d characterization pin first (green at base and after) (WP18)
T098 Red-first R22, the R23 split re-pin and R24 plus its control (WP18)
T099 `executor.py:4183` uses `write_dir` in the unlocked pre-phase; abort arms kept; fork arm added (WP18)
T100 `executor.py:825`: one canonical-events authority per run, except the completed-Mission resume (WP18)
T101 `materialize`: the `--mission` path and the all-Missions loop use `write_dir` for coordination-routed Missions; `errors[]` per Mission (WP18)
T102 Guard sweep over the named consolidation files; `--resume` integrity (WP18)

### Implementation Notes

- Deliberate behaviour change: an UNMATERIALIZED surface with a local branch now materializes and proceeds (R23).

### Parallel Opportunities

- T101 (`materialize.py`) is independent of T099/T100.

### Dependencies

- Depends on WP17.

### Risks & Mitigations

- Terminus-integrity machinery (#5001) → the seed happens before the merge lock and the pre-mutation captures; the guard files are run by name.

---

## Work Package WP19: implement receipts name the branch that holds each commit (Priority: P3)

**Goal**: Every `implement` receipt carries a commit id contained in the branch it names (IC-14).
**Independent Test**: R18 plus the target-branch positive control.
**Prompt**: `/tasks/WP19-implement-receipts-real-branch.md`
**Requirement Refs**: FR-013
**Estimated prompt size**: ~250 lines

### Included Subtasks

T103 Red-first R18 plus the target-branch positive control (WP19)
T104 The "already present" receipt names `write_target(STATUS_STATE).ref` and the last commit touching the status log (WP19)
T105 The summary prints short ids; JSON `commits[]` carries `sha` on every entry (WP19)

### Implementation Notes

- The JSON change is additive.

### Parallel Opportunities

- Not a root (analyze I4): it depends on WP02 and sits in lane-f before WP08. Per lanes.json, lane-f depends on lane-b and lane-o.

### Dependencies

- Depends on WP02 (shared fixture factory; P-m6).

### Risks & Mitigations

- "Always print the coordination branch" would pass a naive test → the positive control rejects it.

---

## Work Package WP20: Extend the write-side rederivation gate; pin the commit-outcome consumer list (Priority: P1)

**Goal**: Close the defect class by construction. A third grammar in the existing gate forbids read resolvers as COORD write locations (floor ≥ 22, empty shrink-only allowlist, mutation bite, stale-entry twin), and an AST pin keeps every commit-outcome consumer on the shared renderer (IC-15, IC-07).
**Independent Test**: The gate is red at `ecb5dd914a` on the real offenders and green on the final tree; the planted mutation is red.
**Prompt**: `/tasks/WP20-write-side-gate-extension.md`
**Requirement Refs**: FR-014, FR-007, SC-005
**Estimated prompt size**: ~400 lines

### Included Subtasks

T106 Third grammar over the census writer functions (WP20)
T107 Floor and live-qualname assertion; red-at-base proof recorded (WP20)
T108 Empty shrink-only allowlist, `_baselines.yaml` cap 0, stale-entry twin (WP20)
T109 Planted-mutation bite test (WP20)
T110 Consumer-list pin test (WP20)

### Implementation Notes

- Re-derive the qualnames from the merged code; earlier work packages may have extracted helpers.

### Parallel Opportunities

- T110 is independent of T106–T109.

### Dependencies

- Depends on WP06, WP07, WP08, WP09, WP10, WP13, WP14, WP15, WP16, WP18.

### Risks & Mitigations

- A gate-unmask cannot self-validate → the red-at-base output is pasted in the PR.

---

## Work Package WP21: End-to-end single-home invariant over the coordination workflow (Priority: P1)

**Goal**: Prove the single-home invariant across create → decision → tracer → spec-commit → setup-plan → finalize → implement → move-task → accept → consolidate, for both coordination topologies, with linear and moved-merge-base variants (IC-16).
**Independent Test**: `tests/integration/test_coord_single_home_workflow.py`, run alone.
**Prompt**: `/tasks/WP21-coord-single-home-e2e.md`
**Requirement Refs**: FR-015, FR-009b, SC-001, SC-002, NFR-002
**Estimated prompt size**: ~330 lines

### Included Subtasks

T111 Scaffold the end-to-end test: integration marker, production CLI create, parametrized topologies (WP21)
T112 Linear flow and its assertions (no COORD path on the target before consolidation, one log, every decision, monotonic clock) (WP21)
T113 Moved-merge-base variant: consolidation succeeds with no target content conflict (WP21)
T114 Local single-file run recorded; SC-001 probe non-vacuity check; defects reported to their owning work package (WP21)
T119 Fresh-clone decision durability and the ledger commit point via spec-commit and accept only (US4.8, FR-009b; operator decision G1) (WP21)

### Implementation Notes

- `consolidate` here is local lane consolidation into the local target branch, never a publish to origin.

### Parallel Opportunities

- None (last code package).

### Dependencies

- Depends on WP06, WP16, WP17, WP18, WP19, WP20.

### Risks & Mitigations

- Slow and brittle → one file, CI nightly owns it; reuse the WP02 factory.

---

## Work Package WP22: Decision records and seam documentation (Priority: P2)

**Goal**: The ADRs and the artifact-placement seam documentation state shipped behaviour: the single-home rule, `write_dir`, no write-side substitution, the kept read fallback, the ledger reclassification (IC-17).
**Independent Test**: The terminology guard passes; the amended ADR sections are cited as FR-017's checkable anchor.
**Prompt**: `/tasks/WP22-adr-and-seam-docs.md`
**Requirement Refs**: FR-017
**Estimated prompt size**: ~280 lines

### Included Subtasks

T115 ADR 2026-06-19-1 amendment: single home, `write_dir`, no write-side substitution, kept read fallback, loud post-fix EMPTY (WP22)
T116 Ledger reversal of the #3928 intent; ADR 2026-09-24-2 write-side note (WP22)
T117 `artifact-placement-seam.md`: `write_dir` section, corrected line citations, partition table (WP22)
T118 Docs hygiene: freshness dates, terminology guard, named docs checks; FR-017 anchors (WP22)

### Implementation Notes

- A `planning_artifact` package: every owned path is under `docs/`.

### Parallel Opportunities

- T115–T117 touch different files.

### Dependencies

- Depends on WP21.

### Risks & Mitigations

- Stale line citations → re-derive them against the final code.

---

## Dependency & Execution Summary

- **Sequence**: the lane roots in lanes.json are lane-b (WP02) and lane-i (WP11). WP01 has no WP dependency, but its lane-a starts after lane-c (WP03). WP19 is not a root (I4). WP-level order: WP02 → WP03 → WP01 → WP04 → WP05 → {WP06, WP07, WP12, WP13, WP14, WP15} → {WP08 (after WP07 and WP19), WP09, WP10} → {WP16, WP17} → WP18 → WP20 → WP21 → WP22.
- **Parallelization**: lane-b (WP02) and lane-i (WP11) start concurrently; lane-c (WP03), then lane-a (WP01 → WP04 → WP05). After WP05, writer migrations (WP07, WP09, WP10), create (WP06) and the ledger reclassification (WP12) proceed in separate lanes. After the post-tasks squad P-m7 move, WP13/WP14/WP15 each run in their own lane after WP05. lane-o serializes WP07 → WP09 → WP17 → WP18 and starts after lane-a and lane-j (WP12); lane-f (WP19 → WP08) starts after lane-b and lane-o. 16 lanes in total (lanes.json).
- **MVP Scope**: WP01–WP06 make creation single-home and the router honest. That is the P0 #5440/#5513 core, but #5519 needs WP07–WP10 as well.

## Closeout items (in-mission, after lane consolidation; not WPs)

1. **Retire the commit router's legacy root-staging copy**: the `shutil.copy2` of non-log COORD records from the repository root checkout into the coordination worktree (`commit_router.py`, legacy branch ≈L1069-1088), once the WP08/WP10 writers write in place.
   - This is an **in-mission closeout fold, not deferred work** (analyze U2). It runs after lane consolidation and before the PR is marked ready.
   - It cannot be a WP: a WP that depends on WP08/WP10 and edits `commit_router.py` (lane A) would create a lane dependency cycle.
   - WP20's gate module carries a pointer comment (post-tasks squad P-M2).
   - If the operator ends up deferring it after all, a GitHub issue is filed and cited here.
2. **CHANGELOG `[Unreleased]` entries (analyze C3)** for every operator-visible change:
   - create materializes and seeds the coordination worktree;
   - spec-commit reports per-argument fates and `success=false` with a non-zero exit on a refused surface;
   - accept commits an uncommitted decision ledger on the target branch, and a protected-target residual is refused by the router;
   - the consolidation dirty gate treats ledger dirt as real work;
   - consolidate materializes an UNMATERIALIZED coordination surface (R23);
   - `spec-kitty materialize` may create and seed coordination worktrees;
   - finalize refreshes `planning_commit_sha` by default, with a new `planning_commit_refresh` JSON field;
   - the decision-index merge-driver migration;
   - doctor decisions fork detection, non-destructive repair, and verify exiting 1 on a fork;
   - teardown refuses a coordination-only ledger.
   The CLI help text is updated inside each owning WP; the shared `docs/api/*` reference pages are updated in WP22.
3. **Issue-matrix verdicts (analyze G3)**: fill `issue-matrix.json` rows for #5440, #5513, #5519, #5501, #2533 and #5023, including the split verdict for #2533: claim leg fixed by `3599c05990`/`e4644c2342`; create/empty-surface leg covered by this Mission (research "Verification: #2533's implement-claim leg").

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP06 |
| FR-002 | WP06 |
| FR-002a | WP06 |
| FR-002b | WP06 |
| FR-003 | WP04, WP07, WP08, WP09, WP10, WP14, WP15, WP16, WP18 |
| FR-003a | WP03, WP04, WP07, WP09 |
| FR-004 | WP03 |
| FR-004a | WP03 |
| FR-004b | WP03 |
| FR-005 | WP16 |
| FR-006 | WP05 |
| FR-007 | WP05, WP07, WP08, WP10, WP13, WP14, WP15, WP16, WP20 |
| FR-007a | WP13 |
| FR-007b | WP15 |
| FR-008 | WP05 |
| FR-009 | WP12, WP16 |
| FR-009a | WP12 |
| FR-009b | WP11, WP12, WP16, WP21 |
| FR-009c | WP17 |
| FR-010 | WP17 |
| FR-010a | WP17 |
| FR-011 | WP17 |
| FR-012 | WP15 |
| FR-013 | WP19 |
| FR-014 | WP18, WP20 |
| FR-015 | WP21 |
| FR-016 | WP02, WP05, WP06, WP09, WP13, WP14, WP15, WP17, WP18 |
| FR-017 | WP04, WP12, WP22 |
| NFR-001 | WP06 |
| NFR-002 | WP02, WP03, WP17, WP18, WP21 |
| NFR-003 | WP01 (every WP applies it) |
| NFR-004 | WP01 (every WP applies it) |
| NFR-005 | WP01 (every WP applies it) |
| C-001 | WP03, WP04 |
| C-002 | WP04 |
| C-003 | WP03, WP17 |
| C-004 | WP03 |
| C-005 | WP02 (every code WP opens red-first) |
| C-008 | WP04, WP06, WP07, WP12, WP18 |
| SC-001 | WP21 |
| SC-002 | WP09, WP21 |
| SC-003 | WP05, WP08, WP10, WP13, WP14, WP15, WP16 |
| SC-004 | WP17 |
| SC-005 | WP20 |

C-006 (no heavy suites) and C-007 (terminology) are process constraints that bind every work package's prompt; they are not delivered by one package.

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Baseline C901 and test counts | WP01 | P0 | No |
| T002 | Extract `spec_commit_command` helpers (moved) | WP13 | P1 | No |
| T003 | Extract `record_report_transaction` helpers (moved) | WP14 | P2 | No |
| T004 | Extract `finalize_tasks` / `_commit_planning_pin_refresh_locked` / `_ft_apply_writes` helpers (moved) | WP15 | P1 | No |
| T005 | Extract router per-path staging step | WP01 | P0 | Yes |
| T006 | Extract anchor-resolver coord-state branch | WP01 | P0 | Yes |
| T007 | Behaviour-preservation proof | WP01 | P0 | No |
| T008 | Coord Mission factory | WP02 | P0 | Yes |
| T009 | Pre-fix shape builder | WP02 | P0 | No |
| T010 | Fork-fixture builders and probes | WP02 | P0 | No |
| T011 | Conftest fixtures and self-tests | WP02 | P0 | No |
| T012 | Red-first and value objects | WP03 | P1 | No |
| T013 | Prefix rule pure functions | WP03 | P1 | Yes |
| T014 | Seed build and atomic rename | WP03 | P1 | No |
| T015 | Seed commit and root restoration | WP03 | P1 | No |
| T016 | Establish state machine | WP03 | P1 | No |
| T017 | Seed test matrix | WP03 | P1 | No |
| T018 | `PlacementSeam.write_dir` | WP04 | P1 | No |
| T019 | Owned-checkout arm | WP04 | P1 | No |
| T020 | Agreement and purity property tests | WP04 | P1 | No |
| T021 | Loud post-fix EMPTY warning | WP04 | P1 | Yes |
| T022 | Stale seam docstrings | WP04 | P1 | Yes |
| T023 | Retire `_try_advance_ref` (R12) | WP05 | P1 | No |
| T024 | `commit_outcome.py` contract | WP05 | P1 | Yes |
| T025 | `CommitRouterResult.surfaces` | WP05 | P1 | No |
| T026 | Adopt R2/R2b | WP05 | P1 | No |
| T027 | Owning-surface translation | WP05 | P1 | No |
| T028 | Owning-surface dirt classification | WP05 | P1 | No |
| T029 | Named refusals | WP05 | P1 | No |
| T030 | Adopt R1/R1b | WP06 | P1 | No |
| T031 | Create flow seeds the coordination surface | WP06 | P1 | No |
| T032 | Protected target and rollback | WP06 | P1 | No |
| T033 | R1c re-pin and R6 | WP06 | P1 | No |
| T034 | Expected-divergence predicate | WP06 | P1 | Yes |
| T035 | Doctor coordination finding (R20) | WP06 | P1 | No |
| T036 | NFR-001 re-measure | WP06 | P1 | No |
| T037 | Red-first move-task state matrix | WP07 | P1 | No |
| T038 | `status_transition.py` via write_dir | WP07 | P1 | No |
| T039 | `transaction.py` via write_dir | WP07 | P1 | No |
| T040 | Tasks port write location and surfaces | WP07 | P1 | No |
| T041 | Lanes recovery via write_dir | WP07 | P1 | Yes |
| T042 | C-008, lock and residue tests | WP07 | P1 | No |
| T043 | Red-first review-cycle / mark-status | WP08 | P2 | No |
| T044 | Review-cycle writers via write_dir | WP08 | P2 | No |
| T045 | Mark-status read/write split | WP08 | P2 | Yes |
| T046 | Tasks-port consumer rendering | WP08 | P2 | No |
| T047 | Consumer and residue tests | WP08 | P2 | No |
| T048 | Red-first R4 | WP09 | P1 | No |
| T049 | `decisions/emit.py` via write_dir | WP09 | P1 | No |
| T050 | `decisions/service.py` via write_dir | WP09 | P1 | No |
| T051 | DecisionGitLog via write_dir | WP09 | P1 | Yes |
| T052 | Decision writer state matrix | WP09 | P1 | No |
| T053 | Red-first in-place writes | WP10 | P2 | No |
| T054 | `WriteSeamResult.surfaces` | WP10 | P2 | No |
| T055 | Tracer writer via write_dir | WP10 | P2 | Yes |
| T056 | Issue matrix via write_dir | WP10 | P2 | Yes |
| T057 | Acceptance matrix via write_dir | WP10 | P2 | Yes |
| T058 | Staging, rendering and C-008 tests | WP10 | P2 | No |
| T059 | Red-first R21 | WP11 | P2 | No |
| T060 | Index union function | WP11 | P2 | No |
| T061 | Driver registration | WP11 | P2 | No |
| T062 | Init seed and `.gitattributes` | WP11 | P2 | No |
| T063 | Upgrade migration | WP11 | P2 | No |
| T064 | Red-first R13 and grouping | WP12 | P2 | No |
| T065 | Move `DECISION_LEDGER` to PRIMARY | WP12 | P2 | No |
| T066 | Reader-flip tests | WP12 | P2 | Yes |
| T067 | FR-009a ratchet | WP12 | P2 | Yes |
| T068 | Guard amendments | WP12 | P2 | No |
| T069 | Red-first R5 | WP13 | P1 | No |
| T070 | spec-commit payload | WP13 | P1 | No |
| T071 | spec-commit text and exit code | WP13 | P1 | No |
| T072 | `--target-branch` help | WP13 | P1 | No |
| T073 | spec-commit tests | WP13 | P1 | No |
| T074 | Red-first R11 (retrospect) | WP14 | P2 | No |
| T075 | setup-plan rendering | WP14 | P2 | Yes |
| T076 | record-analysis / orchestrator / report transaction | WP14 | P2 | Yes |
| T077 | Retrospect read/append split | WP14 | P2 | Yes |
| T078 | Consumer tests | WP14 | P2 | No |
| T079 | Red-first finalize scenarios | WP15 | P1 | No |
| T080 | Finalize write location | WP15 | P1 | No |
| T081 | Finalize coordination porcelain | WP15 | P1 | No |
| T082 | Finalize per-surface output | WP15 | P1 | No |
| T083 | Default planning-commit refresh | WP15 | P1 | No |
| T084 | Refused refresh warns and continues | WP15 | P1 | No |
| T085 | Red-first R7/R8/R9 | WP16 | P1 | No |
| T086 | Accept single router call | WP16 | P1 | No |
| T087 | Accept outcomes and ledger commit | WP16 | P1 | No |
| T088 | Shared accept classifier | WP16 | P1 | No |
| T089 | Accept birth cutover | WP16 | P1 | Yes |
| T090 | Red-first R3/R14/R15/R16 | WP17 | P1 | No |
| T091 | Fork detector | WP17 | P1 | No |
| T092 | Coordination-only ledger finding | WP17 | P1 | No |
| T093 | Doctor diagnose and report | WP17 | P1 | No |
| T094 | Non-destructive repair | WP17 | P1 | No |
| T095 | Verify reports forks | WP17 | P1 | No |
| T096 | Teardown and preflight refusal | WP17 | P1 | No |
| T097 | R1d characterization | WP18 | P2 | No |
| T098 | Red-first R22/R23/R24 | WP18 | P2 | No |
| T099 | Executor pre-phase via write_dir | WP18 | P2 | No |
| T100 | Executor canonical-events authority | WP18 | P2 | No |
| T101 | materialize via write_dir | WP18 | P2 | Yes |
| T102 | Consolidation guard sweep | WP18 | P2 | No |
| T103 | Red-first R18 | WP19 | P3 | No |
| T104 | Receipt names the real branch | WP19 | P3 | No |
| T105 | Short ids and JSON sha | WP19 | P3 | No |
| T106 | Gate third grammar | WP20 | P1 | No |
| T107 | Floor and red-at-base proof | WP20 | P1 | No |
| T108 | Empty allowlist and baseline cap | WP20 | P1 | No |
| T109 | Mutation bite test | WP20 | P1 | No |
| T110 | Consumer-list pin | WP20 | P1 | Yes |
| T111 | E2E scaffold | WP21 | P1 | No |
| T112 | E2E linear flow | WP21 | P1 | No |
| T113 | E2E moved merge base | WP21 | P1 | No |
| T114 | E2E local run record | WP21 | P1 | No |
| T115 | ADR 2026-06-19-1 amendment | WP22 | P2 | Yes |
| T116 | Ledger reversal and ADR 2026-09-24-2 | WP22 | P2 | Yes |
| T117 | Seam documentation | WP22 | P2 | Yes |
| T118 | Docs hygiene | WP22 | P2 | No |
| T119 | Fresh-clone decision durability and ledger commit point | WP21 | P1 | No |
