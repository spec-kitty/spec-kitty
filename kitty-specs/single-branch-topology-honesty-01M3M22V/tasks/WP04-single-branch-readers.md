---
work_package_id: WP04
title: single_branch readers ready for a repo-root lane
dependencies:
- WP03
requirement_refs:
- FR-004
- FR-005
- FR-009
- FR-010
- FR-012
- NFR-002
- NFR-004
planning_base_branch: issue-5100-single-branch-topology
merge_target_branch: issue-5100-single-branch-topology
branch_strategy: Planning artifacts for this mission were generated on issue-5100-single-branch-topology. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5100-single-branch-topology unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-single-branch-topology-honesty-01M3M22V
base_commit: b1d397061491858776902e2ea97355cb3d50457d
created_at: '2026-09-28T19:31:00.785189+00:00'
subtasks:
- T016
- T017
- T018
- T019
- T020
phase: Phase 3 - single_branch readers
history:
- at: '2026-09-28T14:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- src/specify_cli/lanes/checkout_occupancy.py
- tests/lanes/test_checkout_occupancy.py
- tests/specify_cli/workspace/test_single_branch_resolution.py
- tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py
- tests/specify_cli/status/test_execution_mode_stamp_paths.py
- tests/specify_cli/cli/commands/test_single_branch_review_path.py
- tests/specify_cli/consolidation/test_single_branch_bookkeeping_only.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/implement.py
- src/specify_cli/cli/commands/agent/workflow.py
- src/specify_cli/cli/commands/agent/workflow_executor.py
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- src/specify_cli/cli/commands/agent/tasks_status_view.py
- src/specify_cli/orchestrator_api/commands.py
- src/specify_cli/acceptance/gates_core.py
- src/specify_cli/lanes/auto_rebase.py
- src/specify_cli/lanes/lifecycle_sync.py
- src/specify_cli/lanes/checkout_occupancy.py
- tests/lanes/test_checkout_occupancy.py
- tests/specify_cli/workspace/test_single_branch_resolution.py
- tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py
- tests/specify_cli/status/test_execution_mode_stamp_paths.py
- tests/specify_cli/cli/commands/test_single_branch_review_path.py
- tests/specify_cli/consolidation/test_single_branch_bookkeeping_only.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – single_branch readers ready for a repo-root lane

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (`python-pedro`, role `implementer`, agent `claude`), and behave according to its guidance before parsing the rest of this prompt.

---

## ⚠️ IMPORTANT: Review Feedback

Check the event log for `review_ref`. Address every item before finishing.

---

## Objectives & Success Criteria

Prepare **every reader** for a single_branch mission whose `lanes.json` holds exactly one repo-root lane (`lane-planning`) containing **code** WPs. That manifest shape is only *produced* in WP05. This WP tests readers against hand-written manifests of that shape. Covers FR-004, FR-005, FR-009, FR-010, US2.9, and FR-012 (unprotected case).

1. **FR-005 execution-mode stamp.** Add a `ResolvedWorkspace.status_execution_mode` property: `"direct_repo"` when `resolution_kind == "repo_root"`, else `"worktree"`. Every status emit path uses it:
   - `implement.py:~1480`
   - `agent/workflow.py:~1450`
   - `agent/workflow_executor.py:~1573`
   - `orchestrator_api/commands.py:1604,1697,1870`
   - `tasks_move_task.py:~2809`, which today passes no mode and so defaults to `"worktree"`
   - `_mt_owned_workspace` at `tasks_move_task.py:781`, which must use `resolution_kind="repo_root"`
   - `lanes/recovery.py:817` (a genuine lane path, so leave it as `"worktree"` but route it through the property where it resolves a workspace)
2. **FR-004 resolver.** `is_repo_root_lane` precedence runs *before* the persisted WorkspaceContext lookup (plan fold M8). Add the `effective_root: Path | None` parameter to `resolve_workspace_for_wp` / `_resolve_workspace_for_wp_impl`, absorbing PR #5009's arm (see T017). A single_branch repo-root-lane WP resolves to `effective_root` or, if that is absent, the repository root checkout, with `branch_name` = the manifest's `mission_branch`.
3. **FR-009 / FR-010 / wrong-branch refusals.** These apply in implement for a WP in a repo-root lane **of a single_branch mission**. The contract's refusal order is:
   - unmigrated (already done in WP03)
   - wrong branch
   - another WP in progress in the same write checkout
   - dirty checkout

   Resuming the WP that is already in progress is exempt from the last two.
4. **US2.9** No dependency merge for a repo-root lane (`_merge_dependency_lane_tips` skipped). Dependency readiness is unchanged. `tasks_status_view.py:140` must not report repo-root code WPs as `stale_detection_unavailable`.
5. **Unprotected single_branch consolidate and orchestrator merge.**
   - `consolidation/executor.py:680` keys the skip on `is_repo_root_lane`.
   - `acceptance/gates_core.py:277,770` and `executor.py:1671` use `has_code_wps` for their "no code" claims.
   - `orchestrator_api/commands.py:997` keeps single_branch off the lane-merge path.
   - Unprotected consolidate is bookkeeping only (no branch merge or deletion).
   - `--skip-lanes` (`_synthesize_no_lane_manifest`, `executor.py:3326-3383`) must not regress.

**Done when**: every new test passes; all existing tests in the touched modules pass; ruff, mypy and complexity are clean.

## Context & Constraints

- Read first:
  - `plan.md` IC-03 plus folds B1, B3, M1, M6, M8
  - `contracts/single-branch-execution.md` (refusal order, resolve table, consolidate table)
  - `research.md` R-9, R-10, R-12
- **Out-of-map edits** (one-line rationale each in the Activity Log):
  - `src/specify_cli/workspace/context.py` (resolver arm; WP01 owns it)
  - `src/specify_cli/lanes/implement_support.py`
  - `src/specify_cli/lanes/worktree_allocator.py` (dependency-merge skip)
  - `src/specify_cli/lanes/recovery.py`
  - `src/specify_cli/consolidation/executor.py` (**sibling-owned, C-005**: minimal arms only, and list each hunk in the Activity Log for the PR overlap note)
  - `src/specify_cli/core/owned_mission.py`
- **Review path (M1).** `agent/workflow.py:1809-1821` creates a lane worktree for review with `-b`. For a repo-root lane, review runs in the write checkout and must not create a worktree. `lanes/auto_rebase.py:~928` / `lifecycle_sync.py:137-139` must skip repo-root lanes.
- Do NOT change `compute_lanes` yet (WP05). Do not touch mission-create defaults (WP06) or protected-target minting (WP08).

## Branch Strategy

- **Planning base / merge target**: `issue-5100-single-branch-topology`. Run `spec-kitty implement WP04 --mission single-branch-topology-honesty-01M3M22V`.

## Subtasks & Detailed Guidance

### Red-first (charter C-011; analysis finding C1)

Before any implementation commit in this WP, commit the new behaviour tests **alone**, and show that they are RED against the WP's planning base.

- The failure must be an assertion failure. An ImportError, or a crash in a fixture, does not count as red.
- Record the red run (command plus the failing test names) in the Activity Log.
- The reviewer verifies red→green.

The red set for this WP is the tests listed in T016, T017, T018, T019, T020b and T020.


### Subtask T016 – Execution-mode stamp property on every path

- Add the property to `ResolvedWorkspace` in `workspace/context.py`.
- Replace the three copied derivations and the hardcoded `"worktree"` sites listed above.
- In move-task, pass `execution_mode=resolved.status_execution_mode` into the `TransitionRequest`.
- **Tests**: `tests/specify_cli/status/test_execution_mode_stamp_paths.py`. For each path (implement, workflow, move-task, orchestrator start/transition), use a repo-root-lane fixture and assert the emitted event's `execution_mode == "direct_repo"`. Pair each with a code-lane fixture asserting `"worktree"`. This is the non-vacuity control.

### Subtask T017 – Resolver precedence and the `effective_root` arm (PR #5009 absorption)

- In the dispatch from WP01, move the repo-root-lane arm *before* the context arm. The repo-root-lane arm is decided by reading `lanes.json` and checking `is_repo_root_lane(lane)`.
- Add the `effective_root` keyword to both functions and thread it into `placement_seam(..., effective_root=effective_root)` and `get_normalized_wp(...)`, if needed, following PR #5009's shape.
- Key the arm on the stored topology via `read_topology`, not merely on `effective_root` being present:
  - single_branch → write checkout = `effective_root or repo_root`
  - `effective_root` given for a non-single_branch mission → raise `ValueError` (owned mode supports single_branch only, per ADR 2026-09-03-1)
- **Co-author credit**: the commit that introduces the `effective_root` parameter carries the trailer `Co-authored-by: samuelgoff <2007084+samuelgoff@users.noreply.github.com>`. Say in the commit body that the arm was adapted from PR #5009 and re-keyed on topology.
- Update `core/owned_mission.py` only if its validation must accept the resolved write checkout.
- **Tests**: `tests/specify_cli/workspace/test_single_branch_resolution.py`, covering:
  - repo-root lane with no effective_root → repository root checkout
  - with effective_root → that path
  - a stale WorkspaceContext present → still repository root (M8 precedence)
  - `status_execution_mode == "direct_repo"`
  - lanes-topology code lane → `.worktrees` path (control)

### Subtask T018 – Implement refusals

- New module `src/specify_cli/lanes/checkout_occupancy.py`:
  - `in_progress_wps_in_write_checkout(repo_root: Path, write_checkout: Path, *, exclude: tuple[str, str] | None) -> list[tuple[str, str]]` returns `(mission_slug, wp_id)` pairs.
    - It iterates the missions under `kitty-specs/` whose stored topology is single_branch **and** whose resolved write checkout equals `write_checkout`. The owned checkout is read from meta via `owned_mission`; otherwise the repository root is used.
    - For each, it reads WP lanes through the canonical status reader (`materialize` / `get_wp_lane` via the placement seam) and returns WPs in `in_progress`.
    - It must stay cheap: skip missions whose meta says the mission is merged or done, if such a flag exists; otherwise bound the scan to single_branch missions only.
  - `dirty_paths(write_checkout, *, owned_prefixes: Sequence[str]) -> list[str]` uses `git status --porcelain`. It excludes spec-kitty-owned paths: `kitty-specs/<slug>/status.events.jsonl`, `status.json`, `.kittify/runtime/**`, and anything under `.kittify/workspaces/`. Reuse `_validate_worktree_clean` (`worktree_allocator.py:1401`) where possible instead of duplicating its git call.
- In implement's repo-root-lane path, in contract order:
  1. **Wrong branch**: HEAD of the write checkout ≠ `manifest.mission_branch` → refuse, naming both branches.
  2. **Occupancy**: another in-progress WP found (excluding this WP) → refuse, naming mission and WP.
  3. **Dirty**: dirty paths present and this WP is not already `in_progress` → refuse, listing the paths.

  Each refusal has a stable error code (`WRITE_CHECKOUT_WRONG_BRANCH`, `WRITE_CHECKOUT_OCCUPIED`, `WRITE_CHECKOUT_DIRTY`) and a remedy line (NFR-004).
- **Tests**:
  - `tests/lanes/test_checkout_occupancy.py`: pure helpers.
  - `tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py`: through `CliRunner`, with a hand-written repo-root manifest. Cover each refusal, the resume exemption, and the two-missions-sharing-a-checkout case (US2.7).

### Subtask T019 – Dependency-merge skip and status view

- In `allocate_lane_worktree` / `_merge_dependency_lane_tips`: a repo-root lane is never merged, so the loop skips it. For a single_branch repo-root lane, allocation is never reached (WP02 made the allocator refuse it). Confirm that the implement path does not call the dependency merge at all, and add a test asserting that no merge commit is created (`git log --merges` is empty).
- `tasks_status_view.py:140`: treat a repo-root lane as detection-available, comparing against the write checkout.
- **Readiness still enforced (US2.9, post-tasks fold M-1):** test: WP01 in `for_review` (not in_progress, so occupancy does not fire), `implement WP02` (depends on WP01) is refused on **dependency readiness**; assert the error is the readiness one, not `WRITE_CHECKOUT_OCCUPIED`.

### Subtask T020 – Consolidate and orchestrator-merge arms (unprotected)

- `executor.py:680`: skip lanes where `is_repo_root_lane(lane)`. This replaces the `planning_artifact_only` gating of that skip; keep `planning_artifact_only` for its other uses.
- `executor.py:1671`, `gates_core.py:277,770`: replace "planning-only means no code" with `not has_code_wps(...)`.
- When `manifest.mission_branch == manifest.target_branch` and the mission is single_branch, the mission→target phase is a no-op and no branch deletion happens.
- `orchestrator_api/commands.py:997`: single_branch → skip the lane-merge path.
### Subtask T020b – Review path and auto-rebase for a repo-root lane (plan fold M1; post-tasks fold M-2)

- `agent/workflow.py:1809-1821` (review `-b` worktree creation): for a repo-root-lane WP, review runs in the write checkout and creates **no** worktree; for an unmigrated single_branch mission with code lanes the path raises `SINGLE_BRANCH_CODE_LANES_UNMIGRATED` (call the pure assertion from WP03).
- `lanes/auto_rebase.py:~928` / `lifecycle_sync.py:137-139`: skip repo-root lanes.
- Tests: `tests/specify_cli/cli/commands/test_single_branch_review_path.py` — review of a repo-root WP creates no `.worktrees/` entry; the unmigrated case raises.

### Subtask T020 tests

- **Tests**: new file `tests/specify_cli/consolidation/test_single_branch_bookkeeping_only.py`:
  - A single_branch repo-root-lane manifest with code WPs consolidates with no branch merged or deleted, the repository root checkout intact, and the acceptance matrix required.
  - A `--skip-lanes` control stays green.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/lanes/test_checkout_occupancy.py tests/specify_cli/workspace/test_single_branch_resolution.py tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py tests/specify_cli/status/test_execution_mode_stamp_paths.py -q
grep -rl "planning_artifact_only\|is_planning_lane\|execution_mode=\|resolve_workspace_for_wp" tests/ --include=*.py | head -60   # run each relevant file (not directories)
.venv/bin/python -m pytest tests/architectural/test_layer_rules.py -q
make test-fast
.venv/bin/mypy --strict <touched src files> ; .venv/bin/ruff check . ; .venv/bin/ruff format --check .
```

Record the commands and counts in the Activity Log.

## Risks & Mitigations

- **The occupancy scan could be slow on repos with many missions.** Restrict it to single_branch missions and read only status tails. NFR-002 allows < 2 s.
- **Sibling consolidation overlap.** Keep the hunks minimal and list them.
- **Behaviour drift for planning_artifact WPs.** They are already in the repo-root lane, so their stamp becomes `direct_repo`, which is correct. Mention this in the Activity Log; CHANGELOG (WP09) will note it.

## Review Guidance

- Check the paired controls on the stamp tests.
- Check the refusal order, and that the resume exemption does not leak to a *different* WP.
- Verify the `Co-authored-by` trailer on the `effective_root` commit.
- Verify the consolidation hunks are minimal.

## Activity Log

- 2026-09-28T14:00:00Z – system – Prompt created.
