---
work_package_id: WP02
title: executor resume tolerance (#5021 r1) + squash projection-proof precision (#5038)
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-007
- FR-008
planning_base_branch: fix/terminus-reconciliation-attribution-integrity
merge_target_branch: fix/terminus-reconciliation-attribution-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-reconciliation-attribution-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-reconciliation-attribution-integrity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-terminus-reconciliation-attribution-integrity-01M3D4RW
base_commit: c14f1bc773d30631223726cbe875078c9b9f46f0
created_at: '2026-09-25T22:10:45.771491+00:00'
subtasks:
- T007
- T008
- T009
- T010
- T011
phase: Phase 2 - executor resume + projection proof
history:
- at: '2026-09-25T21:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/
create_intent:
- tests/terminus/test_repro_5021.py
- tests/terminus/test_repro_5038.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/merge/executor.py
- src/specify_cli/merge/bookkeeping_projection.py
- tests/terminus/test_repro_5021.py
- tests/terminus/test_repro_5038.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5021'
- '#5038'
---

# Work Package Prompt: WP02 — executor resume tolerance (#5021 r1) + squash projection-proof precision (#5038)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter before parsing the
rest of this prompt, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

State which initialization/boundaries/directives you applied, then continue.

---

## Markdown Formatting
Wrap HTML/XML tags in backticks. Use language identifiers in fenced code blocks.

## Objective & Success Criteria

Fix two fail-closed availability regressions on the `spec-kitty merge` recovery / squash-proof paths:

1. **#5021 residual 1**: a `merge --resume` that crashed mid-teardown with a partial `authored_blobs` set false-FAILs a legitimately-completed squash merge (re-runs the content axis against a post-teardown-partial claim).
2. **#5038**: a clean single-approved-lane DEFAULT-squash merge is false-REFUSEd on the coord-bookkeeping projection proof ("projected coordination bookkeeping content did not land on the target"), and `merge --resume` dead-ends on `TARGET_BRANCH_CONTENT_CONFLICT`.

**Success**: `test_repro_5021.py` and `test_repro_5038.py` are RED before the fixes and GREEN after (real `spec-kitty merge` / `--resume`, no mocking). Both guards hold: a genuinely-incomplete merge still runs the full gate; a genuine failed projection still REFUSEs. `ruff`, `ruff format --check`, `mypy --strict` clean; complexity ≤ 15.

## Context (grounded — file:line at HEAD 1409dc827f)

- Resume path: `_run_lane_based_merge_locked` (`executor.py:2883`) runs `_capture_reconciliation_claim` (L1999) then `_phase_reconcile_before_teardown` (L2102). `merge --resume` reuses the same flow.
- `_enforce_resume_anchor_integrity` (L1944-1996): guards absent `pre_mutation_coord_sha` + lane-tip divergence; does NOT tolerate completed-but-mid-teardown.
- `_lane_first_parent_spine` (L882-895) tolerates an unresolvable range (returns [] on `GitProbeError`) — so once a lane branch is torn down, the rebuilt `authored_blobs` is partial/empty and `_verify_squash_content` REFUSEs on an empty authored set with resolved approved WPs.
- `_phase_reconcile_before_teardown` (L2102-2140): re-runs `MergeOutcomeVerifier.verify`; on FAIL CAS-reverts the target (L2138-2139). No "already-verified / squash content already landed → skip" branch.
- `MergeState` (`merge/state.py`): `completed_wps`, `current_wp`, `strategy`, `pre_mutation_coord_sha`; look for an existing "target advanced + reconciliation passed" signal (`reconciliation_result`, `_MergeRunState` L433-451) to key the completed-state short-circuit on.
- `_assert_squash_projected_content_landed` (`executor.py:2208-2258`): computes `projected_paths` via `_post_checkpoint_mission_paths` and requires `projected_content_matches_target`; on mismatch prints "projected coordination bookkeeping content did not land" and exits 1 WITHOUT rollback.
- `projected_content_matches_target` (`bookkeeping_projection.py:569-594`): returns False when `coord_bytes is None` OR `target_bytes != coord_bytes` for ANY projected path.
- `_post_checkpoint_mission_paths` (`bookkeeping_projection.py:414-480`): yields non-status coord-partition paths (verdict/notes/trace/matrix) under `kitty-specs/<slug>/`, minus status byte-sets and PRIMARY kinds.

Read `../research.md` Decisions 3 & 4 and `../contracts/reconciliation-gate-contract.md` (R1, R2, P1, P2) before coding.

## Subtasks

### T007 — Red-first repro for #5021 r1 (mid-teardown resume false-FAIL)

**Purpose**: Prove a completed squash merge interrupted mid-teardown false-FAILs on `--resume`.

**Steps**:
1. Create `tests/terminus/test_repro_5021.py`, `@pytest.mark.regression` + `#5021`. Study `test_repro_4997.py` / `test_repro_4982.py` for the interrupt-and-persist-`MergeState` pattern (persist-before-mutate anchors so the resume is not fail-closed by the baseless-consolidation guard).
2. Build a coord mission, drive a default-squash `spec-kitty merge` to the point where the target has advanced and reconciliation PASSed, then simulate a crash DURING coord teardown (e.g. a lane branch already deleted) with a persisted `MergeState` reflecting the completed-but-mid-teardown state.
3. Drive `spec-kitty merge --resume`. Assert DESIRED: exit 0 / teardown completes / target unchanged. Today RED (content axis re-run against a partial claim → REFUSE/revert) → `xfail(strict=True)` referencing #5021 until T008.

**Validation**: RED before T008. Commit first.

### T008 — Resume tolerance for completed-but-mid-teardown squash

**Purpose**: Do not re-verify already-verified, already-landed content on resume.

**Steps**:
1. On resume, detect a completed-but-mid-teardown state (target already at the post-merge tip AND `MergeState` records the reconciliation PASS / the mission already integrated — reuse `_mission_integrated_into_target` L1363/1392 and the persisted `reconciliation_result`/completed markers). When detected, SKIP re-running the content axis and proceed to finish teardown.
2. **Guard**: a genuinely-incomplete merge (target NOT advanced, or reconciliation not recorded as passed) still runs the full `_phase_reconcile_before_teardown` gate — no tolerance leak. Add a focused assertion in the repro for the incomplete case (R2).
3. Remove T007's `xfail` → GREEN.

**Validation**: T007 GREEN; R2 guard case still runs the full gate; existing resume tests (`test_repro_4997`, `test_repro_4982`) still GREEN.

### T009 — Red-first repro for #5038 (clean single-lane squash projection false-REFUSE)

**Purpose**: Prove a clean single-approved-lane squash is false-REFUSEd on the bookkeeping projection.

**Steps**:
1. Create `tests/terminus/test_repro_5038.py`, `@pytest.mark.regression` + `#5038`.
2. Build a clean single-approved-lane coord mission with a coord checkpoint and a post-checkpoint coord-partition bookkeeping path (a verdict/notes/trace file) that the target legitimately does not carry. Drive default-squash `spec-kitty merge`.
3. Assert DESIRED: exit 0 / PASS; then drive `--resume` and assert it does NOT dead-end on `TARGET_BRANCH_CONTENT_CONFLICT`. Today RED → `xfail(strict=True)` referencing #5038 until T010.

**Validation**: RED before T010. Commit first.

### T010 — Projection-proof precision

**Purpose**: Distinguish a legitimately-non-landing coord-partition path from a genuine failed projection (C-001: precision, not weakening).

**Steps**:
1. In `_assert_squash_projected_content_landed` / `projected_content_matches_target`, classify a path the target legitimately does not carry (the exact class — e.g. a `coord_bytes`-present path the projection did not/should not carry to target under a legitimate ownership contract) and do NOT REFUSE on it alone. Nail the precise root cause with the T009 repro; prefer narrowing `_post_checkpoint_mission_paths` (what is genuinely expected to land) over loosening the byte-equality check.
2. **Guard**: an approved-content path that genuinely failed to land still makes the proof REFUSE (P2). Add that adversarial case to the repro.
3. Ensure `--resume` no longer dead-ends: the resume path re-projects and completes for the completed clean merge.
4. Remove T009's `xfail` → GREEN.

**Validation**: T009 GREEN; P2 guard REFUSEs; existing squash-projection tests (`test_squash_target_newer_*`, `test_issue_2709_*`) still GREEN.

### T011 — Full run + honest-red check

**Steps**:
1. `PWHEADLESS=1 .venv/bin/python -m pytest tests/terminus/ tests/merge/ -q`.
2. Confirm all four mission repros GREEN, the 3-way `xfail(strict)` still xfailing, and no regressions.
3. Record counts for the PR *Tests run* section.

## Branch Strategy

Planning branch: `fix/terminus-reconciliation-attribution-integrity`. Final merge target: same (mission later PRs to `main`). Enter the lane workspace resolved from `lanes.json`; do not reconstruct it. Depends on WP01 — implement after WP01 is approved.

## Test Strategy (ATDD / red-first — mandatory)

Both defects land issue-pinned `@pytest.mark.regression` real-CLI repros RED through `spec-kitty merge`/`--resume` (committed first), GREEN after the fix. Targeted surface: `tests/terminus/`, plus the squash-projection tests in `tests/merge/`.

## Definition of Done

- FR-006, FR-007 satisfied; scenarios R1, R2, P1, P2 (contract) pass.
- `test_repro_5021.py`, `test_repro_5038.py` GREEN (RED first); both guards hold.
- FR-008 respected: 3-way `xfail(strict)` untouched.
- `ruff check`, `ruff format --check`, `mypy --strict` clean, no new suppressions; complexity ≤ 15.

## Reviewer Guidance

- Verify red→green on both repros against the base commit.
- Confirm the resume tolerance does NOT skip verification of a genuinely-incomplete merge (R2) — this is the fail-closed safety.
- Confirm the projection precision still REFUSEs a genuine failed projection of approved content (P2).
- Adversarial availability lens: the fixes unblock legitimate merges only, never weaken a data-loss guard.

## Risks

- **R1 (C-001)**: resume tolerance skips a gate on genuinely-unfinished work. Mitigation: key the short-circuit on target-advanced + recorded-PASS; R2 guard test.
- **R2 (C-001)**: projection precision blinds the proof to a real failed projection. Mitigation: narrow expected-paths, keep byte-equality for genuinely-projected content; P2 guard test.
- **R3**: #5038's exact root cause is subtler than the summary. Mitigation: the T009 red-first repro nails the precise trigger before T010 codes the fix; if it proves mission-sized, split it out to the #5038 issue and land #5021 r1 alone (flag in the PR).
