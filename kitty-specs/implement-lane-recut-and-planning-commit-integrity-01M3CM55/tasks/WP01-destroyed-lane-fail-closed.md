---
work_package_id: WP01
title: Fail-closed destroyed-lane detector (#4889)
dependencies: []
requirement_refs:
- C-001
- C-002
- FR-001
- FR-002
- FR-003
- FR-004
- FR-007
- FR-008
- FR-009
- NFR-001
- NFR-002
- NFR-004
planning_base_branch: fix/implement-lane-recut-and-planning-commit-integrity
merge_target_branch: fix/implement-lane-recut-and-planning-commit-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/implement-lane-recut-and-planning-commit-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/implement-lane-recut-and-planning-commit-integrity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-implement-lane-recut-and-planning-commit-integrity-01M3CM55
base_commit: 22e69f4d2c856f5c0b364450a898205bcd2d8987
created_at: '2026-09-25T16:27:34.268433+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Fix
history:
- at: '2026-09-25T16:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- tests/lanes/test_issue_4889_destroyed_lane_guard.py
- tests/orchestrator_api/test_issue_4889_caller_independence.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/specify_cli/lanes/worktree_allocator.py
- tests/lanes/test_issue_4889_destroyed_lane_guard.py
- tests/orchestrator_api/test_issue_4889_caller_independence.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Fail-closed destroyed-lane detector (#4889)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Fix GitHub issue **#4889** (P0): when a WP's lane worktree **and** lane branch are both gone while the WP is still in a non-terminal state, re-running `implement` falls through `allocate_lane_worktree`'s FRESH route, silently cuts a new empty lane from the coordination tip, prints `✓ Lane worktree ready`, exits 0, and overwrites the persisted lane metadata — stranding the committed WP work.

**Done when:**
- With a persisted `WorkspaceContext`, a non-terminal WP lane state, both refs gone, and the persisted tip NOT reachable on the target branch, `allocate_lane_worktree` raises a typed fail-closed error → non-zero exit, diagnostic naming the missing lane branch + a recovery ref (reflog / `git fsck --lost-found`), no `Lane worktree ready`, and `.kittify/workspaces/<slug>-lane-<id>.json` untouched.
- The guard fires for **both** allocator callers — CLI (`create_lane_workspace`) and orchestrator-api (`_resolve_start_workspace`) — because it lives inside `allocate_lane_worktree`.
- All control arms are preserved: REUSE (worktree present), CRASH_RECOVERY (branch present, worktree gone), genuinely-fresh (no context / `planned`), and re-open-after-merge (tip is an ancestor of target → resume, no false refusal).

## Context & Source Map

- **Bug site**: `src/specify_cli/lanes/worktree_allocator.py::allocate_lane_worktree`.
  - REUSE gate `if worktree_path.exists():` (~L554).
  - CRASH_RECOVERY gate `if _branch_exists(repo_root, branch):` (~L603).
  - FRESH routes (~L636–694) — the fall-through that consults no WP lane state. **Insert the pre-flight between the CRASH_RECOVERY gate and the FRESH routes (~L634–636).**
- **Callers** (both must be covered — this is why the guard goes in the allocator, not the wrapper):
  - `src/specify_cli/lanes/implement_support.py::create_lane_workspace` (L169) — CLI.
  - `src/specify_cli/orchestrator_api/commands.py::_resolve_start_workspace` (L1375, reached by `start_implementation` L1492 and `transition --to claimed` L1841) — orchestrator/agent.
- **Lane-state authority**: read canonical status via the reducer over the resolved COORD status surface — never the lane worktree tree (sparse-checkout excludes `status.events.jsonl` there; reading it there silently no-ops — see the module docstring and #2514). Non-terminal set: `{in_progress, blocked, for_review, in_review}`; terminal `{done, canceled}` and pre-allocation `{planned, claimed}` are NOT triggers.
- **Persisted pointer**: `src/specify_cli/workspace/context.py` (`load_context` / `find_context_for_wp`; fields `branch_name`, `base_commit`). Its presence for the lane ⇒ "allocated before".
- **Decision table**: see [../data-model.md](../data-model.md#4889-destroyed-lane-decision-table) and the contract [../contracts/destroyed-lane-guard.md](../contracts/destroyed-lane-guard.md).

## Subtasks

### T001 — Red-first repro (CLI)
Add `tests/lanes/test_issue_4889_destroyed_lane_guard.py::test_destroyed_lane_refuses_via_cli` marked `@pytest.mark.regression` and pinned to #4889. Build a coord mission, `implement WP01`, commit real work in the lane, remove the lane worktree + `git branch -D` the lane branch, re-run the `implement` claim path. **Assert the DESIRED post-fix behavior** — the claim raises / exits non-zero, prints no `Lane worktree ready`, does not re-cut an empty lane, and leaves `.kittify/workspaces/*.json` untouched. Written this way the test is **RED on current main** (which silently re-cuts, exit 0) and flips GREEN after T003–T005 — never invert a "characterize the current bug" assertion (that would be green-on-main, the opposite of red-first / ADR 2026-07-17-1). Drive the real entry point (`allocate_lane_worktree` / `create_lane_workspace`) with a realistic on-disk repo fixture. **The committed lane work must be genuinely unreachable from the target branch (dangling after `git branch -D`, never merged to target)** — otherwise the FR-009 ancestor check correctly suppresses the guard and the test would be red for the wrong reason. Add a sibling case in the same file for a **non-`in_progress` non-terminal** destroyed lane (`blocked` / `for_review` / `in_review`) that must ALSO refuse — this is the trigger arm US1-S6 / contract assertion #3 require, and it is exactly where a predicate keyed on `in_progress` alone would pass every other test yet leave S6 broken.

### T002 — Red-first repro (orchestrator) [P]
Add `tests/orchestrator_api/test_issue_4889_caller_independence.py::test_destroyed_lane_refuses_via_orchestrator` (`@pytest.mark.regression`, #4889): same destroyed-lane state, driven through `_resolve_start_workspace` / `start_implementation`. This is the caller the P0 most exists to protect and would bypass a wrapper-only fix.

### T003 — Fail-closed pre-flight
In `allocate_lane_worktree`, after the CRASH_RECOVERY gate and before the FRESH routes (insertion point ~L636), add a small helper that evaluates the destroyed-lane condition and raises a typed error when it holds. **The error MUST subclass `StructuredError` — `class DestroyedLaneError(StructuredError)` — NOT bare `Exception`.** Rationale (load-bearing for caller-independence + owned-files disjointness): `StructuredError` subclasses `RuntimeError` (`core/errors.py:23`, already imported at `worktree_allocator.py:27`), so the orchestrator's existing `except (LaneNotFoundError, DirtyWorktreeError, DependencyLaneMergeConflictError, UnhonorableBaseError, RuntimeError)` arm at `orchestrator_api/commands.py:1381` catches it and surfaces a structured `LANE_ALLOCATION_FAILED` envelope with ZERO edits outside owned files. Do NOT copy the bare-`Exception` sibling template (`DirtyWorktreeError`/`LaneNotFoundError` at worktree_allocator.py:85/89) two lines up — a bare-`Exception` `DestroyedLaneError` escapes that tuple as a raw traceback on the orchestrator path (breaking its "never a bare exception" contract, NFR-004) and its fix would require editing `commands.py`, which is not in this WP's owned_files. Give the error a machine-readable `error_code` + `to_dict()` like `UnhonorableBaseError`. Keep `allocate_lane_worktree`'s own complexity ≤ 15 by extracting the predicate into a helper.

### T004 — Detection predicate
The helper returns true only when: persisted `WorkspaceContext` exists for the lane AND canonical status is non-terminal post-allocation (`{in_progress, blocked, for_review, in_review}`) AND neither the local lane branch nor the worktree exists AND the persisted lane tip is NOT an ancestor of `lanes_manifest.target_branch`. **Read canonical status from the COORD surface via the already-imported seam** — `placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)` (both symbols already imported at `worktree_allocator.py:20`; this is the exact pattern `core/stale_detection.py:451` uses) then `reduce(read_events(...))` / `materialize`. **Do NOT hand-roll `materialize(repo_root/"kitty-specs"/mission_slug)`** — that reads the PRIMARY partition, which on the create-time-default coord topology is sparse-excluded and silently no-ops (C-001/#2514), so the guard would never fire on coord (the exact whack-a-field class this mission kills). Do not key on ref existence alone (defeats #4969 origin-preference).

### T005 — Diagnostic + no side effects
The raised error carries an actionable message: the missing lane branch name and a recovery ref/command (reflog / `git fsck --lost-found`). Ensure the fail-closed path does NOT call `save_context` / overwrite lane metadata and does NOT print `Lane worktree ready` (verify the caller surfaces the error as non-zero exit without the success line).

### T006 — FR-009 resilience [P]
In `_merge_recorded_planning_commit` (worktree_allocator.py ~L737), add a defensive assertion/branch so that if a WP-file add/add ever recurs it fails with a clear diagnostic rather than a bare git error (belt-and-braces for the #4905 fix). Keep it minimal — the real #4905 fix is WP02; this is a guard, not a duplicate fix.

### T007 — Control-arm regression pins
Add focused tests proving REUSE (worktree intact → no-op resume), CRASH_RECOVERY (branch intact, worktree gone → re-attach), genuinely-fresh (no context → fresh create), and re-open-after-merge (tip ancestor of target → resume, no refusal). These pin NFR-001 (zero false positives).

## Branch Strategy

Planning artifacts were generated on `fix/implement-lane-recut-and-planning-commit-integrity`; completed changes merge back into it (then to `main` via PR to upstream) unless the operator redirects. Execution worktrees are allocated per computed lane from `lanes.json` — do not hand-construct the worktree path.

## Test Strategy

Red-first per ADR 2026-07-17-1: T001/T002 land RED through the real entry point before T003–T005. Run narrowly and foreground: `PWHEADLESS=1 .venv/bin/python -m pytest tests/lanes/test_issue_4889_destroyed_lane_guard.py -q` and `.venv/bin/python -m pytest tests/orchestrator_api/test_issue_4889_caller_independence.py -q`. Do NOT run whole-dir sweeps or `make test-fast` inside the WP.

## Definition of Done

- FR-001, FR-002, FR-003, FR-004, FR-008, FR-009 satisfied; NFR-001, NFR-002, NFR-004 pinned by tests.
- New/changed functions complexity ≤ 15; no new `# noqa`/`# type: ignore`; `ruff check` + `ruff format --check` clean on touched files.
- Repros flipped RED→GREEN; transitional repros kept only where they still guard behavior.

## Reviewer Guidance

Verify: (1) `DestroyedLaneError` subclasses `StructuredError` (so the orchestrator's `except (…, RuntimeError)` arm catches it — confirm the orchestrator path returns a structured `LANE_ALLOCATION_FAILED`, not a raw traceback); (2) the guard is inside `allocate_lane_worktree` (not `create_lane_workspace`); (3) status is read via `placement_seam(...).read_dir(STATUS_STATE)` (the coord surface), not `repo_root/kitty-specs/<slug>` (the sparse-excluded PRIMARY tree); (4) a `blocked`/`for_review`/`in_review` destroyed lane also refuses (not just `in_progress`); (5) the reachable-tip check prevents a re-open-after-merge false refusal; (6) no lane metadata is overwritten on refusal.
