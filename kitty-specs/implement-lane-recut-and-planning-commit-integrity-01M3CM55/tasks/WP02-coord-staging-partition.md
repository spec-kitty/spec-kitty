---
work_package_id: WP02
title: Coord-staging partition — keep WP files off coord (#4905)
dependencies: []
requirement_refs:
- C-004
- FR-005
- FR-006
- FR-007
planning_base_branch: fix/implement-lane-recut-and-planning-commit-integrity
merge_target_branch: fix/implement-lane-recut-and-planning-commit-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/implement-lane-recut-and-planning-commit-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/implement-lane-recut-and-planning-commit-integrity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-implement-lane-recut-and-planning-commit-integrity-01M3CM55
base_commit: e021d4ad82c513423fc67235970950696094bf00
created_at: '2026-09-25T16:28:58.253448+00:00'
subtasks:
- T010
- T011
- T012
- T013
- T014
- T015
phase: Phase 1 - Fix
history:
- at: '2026-09-25T16:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_issue_4905_coord_staging.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/cli/commands/agent/workflow.py
- src/specify_cli/cli/commands/agent/workflow_executor.py
- tests/specify_cli/cli/commands/agent/test_issue_4905_coord_staging.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Coord-staging partition (#4905)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Fix GitHub issue **#4905** (P1): on `coord` / `lanes_with_coord` topologies, the agent-verb lifecycle commit stages the PRIMARY-partition file `kitty-specs/<slug>/tasks/WP*.md` onto the **coordination branch**. Every later lane is cut from the coord tip and must absorb the recorded planning commit via FR-009; that merge then hits an add/add conflict on the WP file → `PlanningCommitMergeConflictError`, exit 1, so `implement WP02` cannot start.

**Done when:**
- On a coord mission, the coordination branch tree contains **zero** `kitty-specs/<slug>/tasks/WP*.md` blobs — verified after the claim commit AND after a review-claim.
- `agent action implement WP02` allocates its lane and completes the FR-009 planning merge without a `PlanningCommitMergeConflictError` (exit 0).
- The `lanes` topology (no coord branch) is unchanged.

## Context & Source Map

- **Shared sink (fix here)**: `src/specify_cli/cli/commands/agent/workflow.py::_commit_via_coordination_transaction` (L404). It maps each staged path into the coord worktree via `_transaction_path_for` (L328, called at L437) and commits it. Partition the `paths` here by artifact kind.
- **Three staging sites that funnel through the sink** (all pass `wp.path` in `paths`, so all are fixed by construction at the sink):
  - `workflow_executor.py:881` — claim (`planned → claimed`).
  - `workflow_executor.py:1066` — resume-refresh (`_implement_emit_resume_refresh`).
  - `workflow_executor.py:1741` — review-claim (`for_review → in_review`).
- **Partition authority to reuse** (precise):
  - path → kind: `mission_runtime.kind_for_mission_file(path)` (`artifacts.py:415`; maps `tasks/WP*.md` → `WORK_PACKAGE_TASK`), then `mission_runtime.is_primary_artifact_kind(kind)` (`artifacts.py:402`). `is_primary_artifact_kind` takes a `MissionArtifactKind`, NOT a `Path`, so the classifier step is required first.
  - destination: `commit_to_primary_target` is **not a function/path** — it is an opt-in **bool flag on `BookkeepingTransaction.acquire`** (`coordination/transaction.py:248`, threaded L310, applied L447; its docstring at L258 currently names only `implement.py::_run_planning_artifact_commit` as a caller). WP02 becomes the second caller: the sink currently does `acquire(destination_ref=coord_branch)`; for the primary-bound group run a **second** `acquire(destination_ref=<primary target ref>, commit_to_primary_target=True)`. A PRIMARY-partition path (`WORK_PACKAGE_TASK`, spec/plan/tasks) routes there; `STATUS_STATE` (`status.events.jsonl`, `status.json`) stays on coord via the existing acquire.
  - (Note: `commands.py:685` is the READ-side `placement_seam(...).read_dir(WORK_PACKAGE_TASK)`, not an `is_primary_artifact_kind` call site — do not model the fix on it.)
- **Do NOT** "fix" this by teaching FR-009 `_merge_recorded_planning_commit` to auto-resolve the add/add — that papers over a partition leak. The WP file simply must not be on coord.
- **Contract**: [../contracts/coord-commit-partition.md](../contracts/coord-commit-partition.md). Decision D4: [../research.md](../research.md#decisions).

## Subtasks

### T010 — Red-first repro (coord pollution)
Add `tests/specify_cli/cli/commands/agent/test_issue_4905_coord_staging.py::test_claim_does_not_stage_wp_file_on_coord` (`@pytest.mark.regression`, #4905). Build a coord mission, run the `agent action implement WP01` claim, and **assert the DESIRED post-fix state**: the coordination branch tree contains **zero** `tasks/WP*.md` blobs. Written this way the test is **RED on current main** (which stages the WP file onto coord) and flips GREEN after T012–T014 — do not assert the current bug (that is green-on-main, the inverse of red-first).

### T011 — Red-first repro (WP02 conflict) [P]
Add `test_wp02_starts_without_planning_merge_conflict` (`@pytest.mark.regression`, #4905): after WP01 claim, `agent action implement WP02` currently raises `PlanningCommitMergeConflictError` (RED) → succeeds after the fix.

### T012 — Partition at the sink
In `_commit_via_coordination_transaction`, before writing/staging each path into the coord worktree, classify it by artifact kind. Extract a small helper (keep the sink's complexity ≤ 15) that splits `paths` into coord-bound (STATUS_STATE) and primary-bound (PRIMARY-partition) groups.

### T013 — Route primary-kind to primary target
Commit the primary-bound group via a second `BookkeepingTransaction.acquire(destination_ref=<primary target ref>, commit_to_primary_target=True)` (mirroring `implement.py::_run_planning_artifact_commit`) so `tasks/WP*.md` lands on the primary partition, never coord. Preserve the existing status-artifact `acquire(destination_ref=coord_branch)` exactly as today. If the primary-bound group is empty, skip the second acquire (no empty commit).

### T014 — Cover all three sites
Confirm (by reading the call graph) that claim (881), resume-refresh (1066), and review-claim (1741) all reach the sink, so the single fix covers them. Add no per-site branching; the sink is the single authority.

### T015 — Regression assertions
Assert coord tree has zero `tasks/WP*.md` after claim, after a resume-refresh, AND after a review-claim (`for_review → in_review`) — one assertion per funnel site so a future per-site regression cannot slip through; assert WP02 starts clean; add a `lanes`-topology control asserting unchanged behavior.

## Branch Strategy

Planning artifacts were generated on `fix/implement-lane-recut-and-planning-commit-integrity`; completed changes merge back into it (then `main` via PR to upstream) unless redirected. Execution worktrees are per-lane from `lanes.json`.

## Test Strategy

Red-first per ADR 2026-07-17-1. Run narrowly/foreground: `.venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/test_issue_4905_coord_staging.py -q`. No whole-dir sweeps in the WP.

## Definition of Done

- FR-005, FR-006 satisfied; SC-003 review-claim assertion present.
- Complexity ≤ 15 on changed functions; no new `# noqa`/`# type: ignore`; `ruff check` + `ruff format --check` clean on touched files.
- Repros flipped RED→GREEN.

## Reviewer Guidance

Verify the fix is at the shared sink (not per-site), that it reuses `is_primary_artifact_kind` / `commit_to_primary_target` (no new authority, no merge driver), and that the review-claim path is provably covered (SC-003).
