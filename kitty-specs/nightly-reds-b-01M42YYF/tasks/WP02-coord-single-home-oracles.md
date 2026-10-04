---
work_package_id: WP02
title: Coordination single-home integration oracles
dependencies: []
requirement_refs:
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- SC-002
planning_base_branch: kitty/nightly-reds-b-2026-10-04
merge_target_branch: kitty/nightly-reds-b-2026-10-04
branch_strategy: Planning artifacts for this mission were generated on kitty/nightly-reds-b-2026-10-04. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/nightly-reds-b-2026-10-04 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-reds-b-01M42YYF
base_commit: bd0e69770c6cfcc4e3e8569c108683cae17bdc48
created_at: '2026-10-04T08:08:27.681476+00:00'
subtasks:
- T004
- T005
- T006
phase: Phase 1 - Nightly red repair
history:
- at: '2026-10-04T08:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/integration/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/integration/test_placement_partition_golden_path.py
- tests/integration/test_coord_read_residuals_proof.py
- tests/integration/test_owned_lifecycle_acceptance_finalize.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Coordination single-home integration oracles

## Objectives & Success Criteria

These three node ids pass at `5b5699e50^` and fail from `5b5699e50` on; each must pass again while still asserting the guarantee it protects:

1. `tests/integration/test_placement_partition_golden_path.py::test_lifecycle_mutation_bookkeeping_lands_on_correct_surface[MissionTopology.COORD]`
2. `tests/integration/test_coord_read_residuals_proof.py::test_executor_status_feature_dir_stays_coord_aware`
3. `tests/integration/test_owned_lifecycle_acceptance_finalize.py::test_armed_get_main_repo_root_pin_owned_finalize`

Requirement refs: FR-002, FR-003, FR-004, NFR-001, NFR-002, SC-002.

## Subtasks & Detailed Guidance

### Subtask T004 – Golden path accepts the create-time seed

- Failure: `CalledProcessError` from the fixture's own `git -C <coord wt> commit -q -m "seed empty coord status log"` ("nothing to commit"). Since `5b5699e50`, create seeds and commits `kitty-specs/<slug>/status.events.jsonl` on the coordination branch (CHANGELOG entry for #5440: "create seeds the status log on the coordination branch (with `MissionCreated` and `SpecifyStarted`)"; `core/mission_creation.py::_commit_coord_create_events`).
- Replace the fixture's touch + add + commit block (around lines 430-445, the "WP07 re-pin" comment) with an assertion that the seeded coordination status log already exists (and is tracked on the coordination branch, e.g. `git -C <coord_root> ls-files --error-unmatch <relpath>`), with a comment citing the create-time seed. Keep every later assertion.

### Subtask T005 – STATUS directory observed through the write accessor

- Failure: `executor STATUS feature_dir must resolve the COORD husk; got None`. The spy only patches `PlacementSeam.read_dir`, but `consolidation/executor.py::_resolve_run_status_dir` now uses `seam.write_dir(MissionArtifactKind.STATUS_STATE).path` ("comes from the WRITE accessor (ruling Q4, FR-003), never from a read resolver"). `None` means "not captured".
- Add a pass-through spy on `PlacementSeam.write_dir` recording `location.path` per kind; assert `MissionArtifactKind.STATUS_STATE not in` the read captures, and assert the write capture for STATUS equals `ctx.coord_feature_dir`. Keep the LANE_STATE / PRIMARY_METADATA read assertions unchanged. Update the test docstring wording from `read_dir(STATUS_STATE)` to `write_dir(STATUS_STATE)`.

### Subtask T006 – Owned-finalize exact ledger

- Failure: `post-mint get_main_repo_root reads differ from the exact ledger`; observed `("mission_has_coordination_branch", "_compose_primary_feature_dir")` = 18, pinned 16; other keys match.
- Cause: `read_primary_meta`'s raw-miss fallback (`src/specify_cli/missions/_read_path_resolver.py`) now routes through the shared `_canonicalize_primary_read_handle` (WP09 review cycle 2, the B1-residual same-family fix), adding the chain `_preflight_policy_verdict > mission_has_coordination_branch > resolve_topology > candidate_feature_dir_for_mission > _stored_topology_best_effort > read_primary_meta > _canonicalize_primary_read_handle > _canonicalize_bare_modern_handle > _compose_primary_feature_dir` once per status transaction (two transactions → +2). Same entry frame, same leaf, a WHERE lookup.
- Change the literal 16 → 18 and extend the ledger comment with a dated line naming that chain. Verify the old comment's stated total against the table and correct it if it is wrong. Confirm by dumping the frames yourself before re-pinning (do not just copy 18).

## Review Guidance

- Each test still fails if the guarantee it protects breaks (golden path: the seed must exist; residuals: STATUS must resolve to the coordination dir; ledger: exact counts).

## Branch Strategy

- **Strategy**: lanes_with_coord
- **Planning base branch**: kitty/nightly-reds-b-2026-10-04
- **Merge target branch**: kitty/nightly-reds-b-2026-10-04

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

## Binding rules for this WP

- Commits: author AND committer are `Stijn Dejongh <stijn.dejongh@sddevelopment.be>`; set `git config user.name "Stijn Dejongh"` and `git config user.email "stijn.dejongh@sddevelopment.be"` in the lane worktree before committing. End every commit message you write with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Run tests foreground by named node id or file only: `PWHEADLESS=1 <repo>/.venv/bin/python -m pytest -p no:cacheprovider -q -n0 -m "" <ids>`. Never a directory, never `make test-full`.
- No retries, skips, xfails, deselections, timeout or budget changes; keep every assertion except the stale literal named below.
- Do not touch any file outside `owned_files`.
- `ruff check` and `uv run --frozen ruff format --check --force-exclude` on every touched Python file.

## Activity Log

- 2026-10-04T08:10:00Z – system – Prompt created.
