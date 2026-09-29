# Tasks: Single-branch topology honesty and destroyed-lane tip guard

**Mission**: `single-branch-topology-honesty-01M3M22V`

**Branches**: planning base `issue-5100-single-branch-topology`; merge target `issue-5100-single-branch-topology`.

**Inputs**: [spec.md](spec.md), [plan.md](plan.md) (the "Post-plan squad folds" section is binding), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/)

The WPs run strictly in sequence: WP01 → WP02 → WP03 → WP04 → **WP06 → WP05** → WP07 → WP08 → WP09. Post-tasks fold B-2 moved the create-default flip to `lanes` ahead of single_branch activation. They share hot files (`worktree_allocator.py`, `implement_support.py`, `workspace/context.py`), so each WP depends on the one before it. See the ownership notes in each prompt.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Extract destroyed-lane guard helpers from `worktree_allocator.py` (behaviour-preserving) | WP01 | |
| T002 | Split `_resolve_workspace_for_wp_impl` into per-arm helpers (behaviour-preserving) | WP01 | |
| T003 | Focused unit tests for the extracted helpers | WP01 | |
| T004 | Red-first: planning-lane for_review and dependency-merge regression test | WP02 | |
| T005 | Naming API split: `code_lane_branch_name` / `lane_branch_name(..., *, target_branch)` | WP02 | |
| T006 | Update every `lane_branch_name` caller; add the architectural gate | WP02 | |
| T007 | Claim-base ref `refs/spec-kitty/wp-base/<mission>/<WP>` recorded at claim | WP02 | |
| T008 | for_review gate evaluates repo-root-lane WPs through the claim base | WP02 | |
| T009 | Repo-root-lane arms in implement, orchestrator and recovery; the allocator and predictor refuse a repo-root lane | WP02 | |
| T010 | Red-first: migration registered, re-stamp, and fail-closed test | WP03 | |
| T011 | Predicates `is_repo_root_lane`, `has_code_lanes`, `has_code_wps`; `_has_lanes` counts code lanes | WP03 | |
| T012 | `assert_topology_matches_manifest` at the manifest writer and the allocator; topology parameter threaded through the three `compute_and_write_lanes` callers | WP03 | |
| T013 | `restamp_single_branch_with_code_lanes()`, migration `m_4_0_0rc5_single_branch_code_lanes_restamp`, and operator CLI flag | WP03 | |
| T014 | Doctor topology finding `SINGLE_BRANCH_CODE_LANES_UNMIGRATED` | WP03 | |
| T015 | Dry-run the re-stamp against this repo and record the count. The data commit itself is the orchestrator's wrap-up step, because code_change WPs may not own `kitty-specs/`. | WP03 | |
| T016 | `ResolvedWorkspace.status_execution_mode`; every emit path uses it | WP04 | |
| T017 | Resolver precedence (`is_repo_root_lane` before the context lookup) plus the `effective_root` arm (PR #5009, co-author) | WP04 | |
| T018 | Implement refusals: wrong branch, other in-progress WP in the write checkout, dirty checkout (resume exempt) | WP04 | |
| T019 | Skip dependency merge for a repo-root lane; `tasks_status_view` repo-root handling | WP04 | |
| T020 | Consolidate and orchestrator-merge arms for a single_branch mission (bookkeeping only when unprotected) | WP04 | |
| T021 | Red-first: `tests/integration/test_issue_5100_single_branch_topology.py` (protected cases `xfail(strict=True)`) | WP05 | |
| T022 | `compute_lanes(topology=single_branch)` writes one repo-root lane; `mission_branch` set to the target | WP05 | |
| T023 | Finalize wiring and JSON: `planning_artifact_wps` stays kind-derived | WP05 | |
| T024 | Green the #5100 unprotected cases end to end; update blast-radius tests | WP05 | |
| T025 | Create default: both implicit single_branch arms become `lanes` | WP06 | |
| T026 | Update the pinned mission-create tests; add a default-matrix test | WP06 | |
| T027 | Update help text and docstrings for `--topology` | WP06 | |
| T028 | Red-first: `tests/lanes/test_issue_5115_destroyed_lane_non_coord.py` | WP07 | |
| T029 | `lanes/lane_tip.py`: ref naming, record/read/clear, `is_absorbed` via merge-tree | WP07 | |
| T030 | `install_lane_tip_recorder` (post-commit and post-rewrite, `sh`) plus upgrade migration | WP07 | |
| T031 | Guard order and tip-based decision; `LaneWorkTipUnknownError`; remedy text | WP07 | |
| T032 | Record the tip at spec-kitty lane advances; clear it at terminal states or teardown; backfill on touch | WP07 | |
| T033 | Orchestrator lane allocation persists context through the allocator (FR-022) | WP07 | |
| T034 | `ProtectionPolicy.is_protected_target`; `commit_to_target` read and write | WP08 | |
| T035 | `--commit-to-target` flag; create-time mission-branch mint and checkout; refuse an existing branch | WP08 | |
| T036 | Write-target and authoritative-ref arm for `meta.mission_branch`; `expected_write_branch` in `owned_mission` | WP08 | |
| T037 | Consolidate mission→target phase and blob source for protected single_branch; switch the checkout back before teardown | WP08 | |
| T038 | Flip the #5100 protected-case xfails to passing | WP08 | |
| T039 | Correct the CLAUDE.md Execution Workspace Strategy and `docs/architecture/execution-lanes.md` | WP09 | |
| T040 | Topology glossary entry under `docs/context/` | WP09 | |
| T041 | CHANGELOG `[Unreleased]` entry; docs index, freshness and terminology gates | WP09 | |

## WP01 — Campsite: extract guard and resolver helpers (behaviour-preserving)

- **Goal**: make the two god-surfaces this mission changes, `worktree_allocator.py` and `_resolve_workspace_for_wp_impl`, small and testable. Behaviour must not change.
- **Priority**: P1 (enabler; charter standing order 2).
- **Independent test**: the existing `tests/lanes/` guard tests and workspace-resolution tests pass unchanged. The new helper tests pass.
- **Subtasks**:
  - T001 Extract destroyed-lane guard helpers from `worktree_allocator.py` (WP01)
  - T002 Split `_resolve_workspace_for_wp_impl` into per-arm helpers (WP01)
  - T003 Focused unit tests for the extracted helpers (WP01)
- **Dependencies**: none.
- **Prompt**: [tasks/WP01-campsite-guard-and-resolver-helpers.md](tasks/WP01-campsite-guard-and-resolver-helpers.md). Estimated at about 200 lines.

## WP02 — Planning lane never needs a lane-planning ref (#5100 guard facet)

- **Goal**: FR-001 and FR-002. No caller can resolve the planning lane to `main`. The for_review gate evaluates repo-root-lane WPs through a claim-time base. Implement, the orchestrator and recovery route repo-root lanes to the write checkout.
- **Priority**: P1.
- **Independent test**: a regression test on a planning-plus-code mission targeting a non-`main` branch.
- **Subtasks**:
  - T004 Red-first regression test (WP02)
  - T005 Naming API split (WP02)
  - T006 Callers updated; architectural gate added (WP02)
  - T007 Claim-base ref (WP02)
  - T008 for_review gate through the claim base (WP02)
  - T009 Repo-root arms; allocator and predictor refusal (WP02)
- **Dependencies**: WP01.
- **Prompt**: [tasks/WP02-planning-lane-target-and-claim-base.md](tasks/WP02-planning-lane-target-and-claim-base.md). Estimated at about 330 lines.

## WP03 — Topology reader counts code lanes; fail closed; re-stamp migration; doctor

- **Goal**: FR-014, FR-015, FR-016 and FR-017.
- **Priority**: P1.
- **Independent test**: `tests/specify_cli/upgrade/migrations/test_single_branch_code_lanes_restamp.py`.
- **Subtasks**:
  - T010 Red-first migration test (WP03)
  - T011 Predicates (WP03)
  - T012 Fail-closed assertion and topology parameter (WP03)
  - T013 Re-stamp function, migration and CLI (WP03)
  - T014 Doctor finding (WP03)
  - T015 Data commit for in-repo missions (WP03)
- **Dependencies**: WP02.
- **Prompt**: [tasks/WP03-restamp-migration-and-fail-closed.md](tasks/WP03-restamp-migration-and-fail-closed.md). Estimated at about 330 lines.

## WP04 — single_branch readers ready for a repo-root lane

- **Goal**: FR-004, FR-005, FR-009 and FR-010, the dependency-merge skip (US2.9), and FR-012 for the unprotected case. Every reader is ready before activation.
- **Priority**: P1.
- **Independent test**: unit tests with a hand-written repo-root manifest.
- **Subtasks**:
  - T016 Stamp property on every emit path (WP04)
  - T017 Resolver precedence and the `effective_root` arm (WP04)
  - T018 Implement refusals (WP04)
  - T019 Dependency-merge skip and status view (WP04)
  - T020 Consolidate and orchestrator-merge arms (WP04)
- **Dependencies**: WP03.
- **Prompt**: [tasks/WP04-single-branch-readers.md](tasks/WP04-single-branch-readers.md). Estimated at about 380 lines.

## WP05 — Activate the single_branch repo-root manifest (#5100 red→green)

- **Goal**: FR-003, FR-006 and FR-011. The #5100 test goes green for the unprotected cases.
- **Priority**: P1.
- **Independent test**: `tests/integration/test_issue_5100_single_branch_topology.py`.
- **Subtasks**:
  - T021 Red-first #5100 test (WP05)
  - T022 `compute_lanes(topology=single_branch)` (WP05)
  - T023 Finalize wiring and JSON (WP05)
  - T024 End-to-end green; blast-radius tests (WP05)
- **Dependencies**: WP06.
- **Prompt**: [tasks/WP05-activate-single-branch-manifest.md](tasks/WP05-activate-single-branch-manifest.md). Estimated at about 300 lines.

## WP06 — Create default becomes `lanes` (#2602)

- **Goal**: FR-013.
- **Priority**: P2.
- **Independent test**: the mission-create default-matrix test.
- **Subtasks**:
  - T025 Default derivation (WP06)
  - T026 Pinned tests and default matrix (WP06)
  - T027 Help text (WP06)
- **Dependencies**: WP04 (runs before WP05).
- **Prompt**: [tasks/WP06-create-default-lanes.md](tasks/WP06-create-default-lanes.md). Estimated at about 180 lines.

## WP07 — Lane work tip and destroyed-lane guard (#5115 red→green)

- **Goal**: FR-018 through FR-022 and FR-024, plus NFR-001.
- **Priority**: P1.
- **Independent test**: `tests/lanes/test_issue_5115_destroyed_lane_non_coord.py`.
- **Subtasks**:
  - T028 Red-first #5115 test (WP07)
  - T029 `lane_tip.py` (WP07)
  - T030 Recorder installer and migration (WP07)
  - T031 Guard order and decision (WP07)
  - T032 Recording, clearing and backfill (WP07)
  - T033 Orchestrator context through the allocator (WP07)
- **Dependencies**: WP05.
- **Prompt**: [tasks/WP07-lane-work-tip-guard.md](tasks/WP07-lane-work-tip-guard.md). Estimated at about 420 lines.

## WP08 — Protected-target mission branch

- **Goal**: FR-007, FR-008 and FR-012 for the protected case.
- **Priority**: P1.
- **Independent test**: the protected cases in the #5100 test file flip from xfail to passing.
- **Subtasks**:
  - T034 Protection query and meta field (WP08)
  - T035 Flag, mint and refuse (WP08)
  - T036 Write-target and authoritative-ref arm (WP08)
  - T037 Consolidate mission→target (WP08)
  - T038 Flip the xfails (WP08)
- **Dependencies**: WP07.
- **Prompt**: [tasks/WP08-protected-target-mission-branch.md](tasks/WP08-protected-target-mission-branch.md). Estimated at about 400 lines.

## WP09 — Truthful docs, glossary and changelog

- **Goal**: FR-023.
- **Priority**: P2.
- **Independent test**: the docs gates and the terminology gate.
- **Subtasks**:
  - T039 CLAUDE.md and `execution-lanes.md` (WP09)
  - T040 Topology glossary entry (WP09)
  - T041 CHANGELOG entry and docs gates (WP09)
- **Dependencies**: WP08.
- **Prompt**: [tasks/WP09-docs-glossary-changelog.md](tasks/WP09-docs-glossary-changelog.md). Estimated at about 160 lines.

## Orchestrator wrap-up (not a WP)

- Run the re-stamp migration on this repository: `spec-kitty migrate backfill-topology --restamp-single-branch`.
- Verify that `git diff -U0 kitty-specs/*/meta.json` changes only `topology` lines (NFR-003).
- Run `spec-kitty doctor topology` and confirm it reports 0 `SINGLE_BRANCH_CODE_LANES_UNMIGRATED` findings (SC-003).
- Commit the result as a separate data commit.

## Parallelization

None. The WPs deliberately form a strict chain because they share the allocator, resolver and implement-support files.

The MVP is WP01–WP05, which closes the #5100 P0 for unprotected targets. WP07 closes the #5115 P0.
