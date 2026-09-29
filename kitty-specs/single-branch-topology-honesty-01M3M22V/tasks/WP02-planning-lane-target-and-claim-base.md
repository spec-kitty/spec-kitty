---
work_package_id: WP02
title: Planning lane never needs a lane-planning ref (#5100 guard facet)
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-011
planning_base_branch: issue-5100-single-branch-topology
merge_target_branch: issue-5100-single-branch-topology
branch_strategy: Planning artifacts for this mission were generated on issue-5100-single-branch-topology. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5100-single-branch-topology unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-single-branch-topology-honesty-01M3M22V
base_commit: b1d397061491858776902e2ea97355cb3d50457d
created_at: '2026-09-28T14:18:52.414113+00:00'
subtasks:
- T004
- T005
- T006
- T007
- T008
- T009
phase: Phase 1 - Planning-lane guard
history:
- at: '2026-09-28T14:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- src/specify_cli/lanes/claim_base.py
- tests/lanes/test_issue_5100_planning_lane_ref.py
- tests/lanes/test_claim_base.py
- tests/architectural/test_planning_lane_branch_requires_target.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/lanes/branch_naming.py
- src/specify_cli/lanes/for_review_gate.py
- src/specify_cli/lanes/implement_support.py
- src/specify_cli/lanes/recovery.py
- src/specify_cli/lanes/claim_base.py
- tests/lanes/test_issue_5100_planning_lane_ref.py
- tests/lanes/test_claim_base.py
- tests/architectural/test_planning_lane_branch_requires_target.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Planning lane never needs a lane-planning ref (#5100 guard facet)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the event log for `review_ref`. If feedback exists, address every item first.

---

## Objectives & Success Criteria

This WP closes the separable guard facet of #5100 (spec FR-001, FR-002, US1). It also lays the plumbing that single_branch reuses later:

1. **Branch-name resolution.** No code path can resolve the `lane-planning` lane's branch without naming the target branch. Today `lane_branch_name(slug, "lane-planning")` silently returns `"main"` (`lanes/branch_naming.py:~530`).
2. **for_review gate.** The gate evaluates a repo-root-lane WP, which today means any planning_artifact WP, by commits since a **claim-time base**. It no longer predicts a `.worktrees/<slug>-lane-planning` path.
3. **Workspace arms.** Implement, the orchestrator API and recovery route a repo-root lane to the write checkout. `allocate_lane_worktree` and `predict_lane_worktree` refuse a repo-root lane.

**Done when**:
- The red-first test `tests/lanes/test_issue_5100_planning_lane_ref.py` was committed RED first and is now GREEN.
- The new architectural gate passes and has a self-mutation proof.
- All targeted tests pass, and ruff and mypy are clean.

## Context & Constraints

- Read first: `plan.md`, especially the **Post-plan squad folds** (B1, B2, M2); `contracts/single-branch-execution.md`, section "Claim base and for_review"; `research.md`.
- **Out-of-map edits allowed, with a one-line rationale each in the Activity Log.** These are the `lane_branch_name` callers named in plan fold M2:
  - `worktree_allocator.py:491` (`predict_lane_worktree`) and `:~1253` (`_merge_dependency_lane_tips`)
  - `sparse_checkout.py:232`
  - `backfill_ownership.py:148`
  - `mission_type.py:796,1005`
  - `workspace/context.py:846,864`
  - `cli/commands/implement.py:1576` (`_resolve_execution_lane`)
  - `orchestrator_api/commands.py:1343,1427`
- `consolidation/executor.py:1987` has a literal `"lane-planning"`. It is sibling-owned (C-005). Touch it only if the new gate flags it, and note it in the PR.
- **Scope limit.** Do NOT introduce topology reads, single_branch behaviour or `direct_repo` stamping; those land in WP03–WP05. The only WPs that land in a repo-root lane in this WP are planning_artifact WPs, which already resolve to the repository root.

## Branch Strategy

- **Planning base branch**: issue-5100-single-branch-topology
- **Merge target branch**: issue-5100-single-branch-topology
- Workspace: per the computed lane in `lanes.json`. Run `spec-kitty implement WP02 --mission single-branch-topology-honesty-01M3M22V`.

## Subtasks & Detailed Guidance

### Subtask T004 – Red-first regression test (commit FIRST, alone)

- **Purpose**: ATDD/red-first per ADR 2026-07-17-1 and C-008. The reviewer verifies red→green.
- **File**: `tests/lanes/test_issue_5100_planning_lane_ref.py`, marked `@pytest.mark.regression` plus `git_repo`/`integration` markers.
- **Scenarios**, through real entry points: the CLI via `CliRunner`, or the real `evaluate_for_review_gate` / `allocate_lane_worktree` functions.
  1. A mission with target branch `feat/x` and **no `main` branch in the repo**. It has one planning_artifact WP01 with a committed deliverable. `evaluate_for_review_gate`, or `move-task WP01 --to for_review`, passes without `--force`. Assert that no path containing `lane-planning` under `.worktrees/` is ever stat-ed or created.
  2. **Control, same fixture**: a planning_artifact WP with no commit since claim is still refused.
  3. A code WP02 depends on the planning WP01. Allocating WP02's lane merges `feat/x`, not `main`, and emits no "skipping missing branch" warning.
  4. **Status-only commits don't count (B-3):** claim, let only the claimed/in_progress status commits land, then `for_review` → still refused.
  5. `lane_branch_name(slug, "lane-planning")` without a target raises `TypeError`, because the keyword is required. Assert this with `pytest.raises`, not by import.
- **Building the fixture**: reuse `tests/lanes/test_lane_allocation_integrity_e2e.py`:
  - drop the coordination parts of `_build_coord_mission`;
  - use `write_wp`, `_seed_canonical_wp_state` and `write_lanes_json`;
  - use `_ids()` for unique identity.
- **Red must fail on an assertion, not an ImportError.** Do not import symbols that do not exist yet at module top.
- Commit this test alone: `test(lanes): red-first #5100 planning-lane ref regression`.

### Subtask T005 – Naming API split

- **Steps**:
  1. In `branch_naming.py`, add `code_lane_branch_name(mission_slug, lane_id) -> str`. It raises `ValueError` when `lane_id == PLANNING_LANE_ID`, and otherwise behaves exactly like today's code-lane path.
  2. Change `lane_branch_name(mission_slug, lane_id, *, target_branch: str) -> str`. The keyword is now required with no default. The planning arm returns `target_branch`, and the code arm delegates to `code_lane_branch_name`.
  3. Keep `__all__` in sync (charter C-007 `__all__` convention applies to `charter`/`kernel` only, but keep this module consistent).
- **Notes**: mypy now flags every stale caller. Use that, rather than grep, to find them all.

### Subtask T006 – Update every caller and add the architectural gate

- **Steps**:
  1. Fix each caller from fold M2:
     - A caller that knows it has a code lane uses `code_lane_branch_name`.
     - A caller that may see the planning lane passes `target_branch=manifest.target_branch`, or the mission's target from meta via the existing resolver.
  2. In `_merge_dependency_lane_tips` (`worktree_allocator.py:~1253`), pass `target_branch=manifest.target_branch`.
  3. In `_approved_dependency_lane_refs` (`implement_support.py:~478`), do the same.
  4. Create `tests/architectural/test_planning_lane_branch_requires_target.py`:
     - It walks the AST of `src/` and asserts that every call to `lane_branch_name` passes `target_branch=` as a keyword.
     - **Non-vacuity floor**: assert that at least 5 call sites are found.
     - **Self-mutation test**: feed the checker a synthetic source string with a missing keyword and assert that it reports it.
     - No allowlist.

### Subtask T007 – Claim-base ref

- **Steps**:
  1. Create `src/specify_cli/lanes/claim_base.py` with:
     - `claim_base_ref(mission_slug, wp_id) -> str`, which returns `refs/spec-kitty/wp-base/<mission_slug>/<wp_id>`;
     - `record_claim_base(repo_root, write_checkout, mission_slug, wp_id) -> str`, which records `git rev-parse HEAD` of `write_checkout` **only if the ref is absent**, and returns the SHA;
     - `read_claim_base(...) -> str | None`;
     - `clear_claim_base(...)`.
     Use the existing git helpers in `specify_cli.lanes._git` where they fit. Run `git -C <repo_root> update-ref`; refs live in the common dir, so worktrees share them.
  2. Call `record_claim_base` where implement resolves a repo-root-lane WP to the write checkout: the planning arm in `implement_support.create_lane_workspace` (`:136`), and the orchestrator `_resolve_start_workspace` repo-root arm.
  3. Create ONE terminal-transition hook `on_wp_terminal(repo_root, mission_slug, wp_id)` in `claim_base.py` and call it from the single seam where a WP reaches `done`/`canceled` (find it in `status/emit.py` / `coordination/status_transition.py`); it calls `clear_claim_base`. WP07 extends this same hook to clear lane-tip refs — do not create a second terminal hook (post-tasks fold M-3). No lazy-clear fallback.
- **Tests**: `tests/lanes/test_claim_base.py` covers:
  - record-once idempotency (a second record does not move the ref);
  - read and clear;
  - the ref name.

### Subtask T008 – for_review gate through the claim base

- **Steps**:
  1. In `for_review_gate.py:121-160`, when the WP's lane is the planning lane (`is_planning_lane(lane)` for now; WP03 renames it to `is_repo_root_lane`):
     - resolve the workspace through `resolve_workspace_for_wp`;
     - read the claim base;
     - require at least one commit in `<base>..HEAD` (write checkout) that touches a path **outside** `kitty-specs/<slug>/status.*`, `kitty-specs/<slug>/issue-matrix.*` and `.kittify/**` (use `git log --format=%H --name-only <base>..HEAD` and filter; post-tasks fold B-3: claim/in_progress status commits land on the same branch and must not satisfy the gate). Otherwise refuse with the gate's existing refusal shape.
  2. If the claim-base ref is missing (a WP claimed before this change), fall back to the gate's **existing** refusal. Do not pass vacuously.
  3. Fix the docstring at `:86`, which wrongly says planning WPs return None.
- **Notes**: the move-task path skips repo-root workspaces (`tasks_parsing_validation.py:706`). Confirm that the new path keeps that consistent, or route both through the same helper.

### Subtask T009 – Repo-root arms and allocator/predictor refusal

- **Steps**:
  1. In `implement_support.create_lane_workspace` (`:136-150`), `implement._resolve_execution_lane` (`:1576`), `orchestrator_api/commands.py:1343,1427` and `recovery.py:403,701,723`, key the decision on the planning lane (`is_planning_lane`) rather than on the WP kind. Planning-lane WPs go to the repository root with no worktree.
  2. `allocate_lane_worktree` and `predict_lane_worktree` raise a clear `ValueError("repo-root lane has no worktree")` when given the planning lane id. This is a programming error, since callers must route around it.
- **Notes**: behaviour for planning_artifact WPs stays as today. This WP only makes the decision lane-keyed so that WP05's code WPs in the repo-root lane follow the same path.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/lanes/test_issue_5100_planning_lane_ref.py tests/lanes/test_claim_base.py tests/architectural/test_planning_lane_branch_requires_target.py -q
.venv/bin/python -m pytest tests/lanes/test_branch_naming.py tests/lanes/test_branch_naming_planning.py tests/lanes/test_branch_naming_required.py tests/lanes/test_branch_naming_seam.py tests/specify_cli/lanes/test_branch_naming_ssot_entrypoint.py tests/core/test_branch_naming_human_slug.py -q
.venv/bin/python -m pytest tests/specify_cli/lanes/test_for_review_gate_parity.py tests/lanes/test_worktree_allocator.py tests/lanes/test_lane_allocation_integrity_e2e.py tests/lanes/test_issue_4889_destroyed_lane_guard.py tests/specify_cli/lanes/test_worktree_allocator_recovery.py -q
grep -rl "lane_branch_name\|predict_lane_worktree\|for_review_gate" tests/ --include=*.py   # run every file listed
.venv/bin/python -m pytest tests/architectural/test_no_worktree_name_guess.py tests/architectural/test_no_dead_symbols.py -q
.venv/bin/mypy --strict src/specify_cli/lanes/ ; .venv/bin/ruff check src/specify_cli/lanes/ ; .venv/bin/ruff format --check src/specify_cli/lanes/
```

Also run `make test-fast` once. Record the commands and counts in the Activity Log.

## Risks & Mitigations

- **Many callers.** mypy's required-keyword error is the safety net. Run mypy over `src/` before claiming done.
- **The gate becomes vacuous when the claim base is missing.** The fallback is the existing refusal, and a test pins it.
- **Orchestrator flows** (`tests/orchestrator_api/`). Run every orchestrator test file that grep finds for `start_implementation`.

## Review Guidance

- Verify red→green: T004's commit fails on the planning base, and the final commit passes.
- Verify the gate's floor and self-mutation test.
- Verify that no topology or single_branch semantics leaked into this WP.

## Activity Log

- 2026-09-28T14:00:00Z – system – Prompt created.
