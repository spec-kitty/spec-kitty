---
work_package_id: WP05
title: Activate the single_branch repo-root manifest (#5100 red→green)
dependencies:
- WP06
requirement_refs:
- FR-003
- FR-006
- FR-011
planning_base_branch: issue-5100-single-branch-topology
merge_target_branch: issue-5100-single-branch-topology
branch_strategy: Planning artifacts for this mission were generated on issue-5100-single-branch-topology. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5100-single-branch-topology unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-single-branch-topology-honesty-01M3M22V
base_commit: b1d397061491858776902e2ea97355cb3d50457d
created_at: '2026-09-29T00:24:44.831179+00:00'
subtasks:
- T021
- T022
- T023
- T024
phase: Phase 4 - Activation
history:
- at: '2026-09-28T14:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- tests/integration/test_issue_5100_single_branch_topology.py
- tests/lanes/test_compute_lanes_single_branch.py
- tests/lanes/test_single_branch_code_lanes_fail_closed.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/lanes/compute.py
- src/specify_cli/cli/commands/agent/mission_finalize.py
- tests/integration/test_issue_5100_single_branch_topology.py
- tests/lanes/test_compute_lanes_single_branch.py
- tests/lanes/test_single_branch_code_lanes_fail_closed.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Activate the single_branch repo-root manifest (#5100 red→green)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (`python-pedro`, role `implementer`, agent `claude`), and behave according to its guidance before parsing the rest of this prompt.

---

## ⚠️ IMPORTANT: Review Feedback

Check the event log for `review_ref`. Address every item before finishing.

---

## Objectives & Success Criteria

Switch single_branch on. `compute_lanes` / `compute_and_write_lanes` with `topology=single_branch` produce a manifest with exactly one lane, `lane-planning`, that holds **every** WP. Its `mission_branch` is `meta.mission_branch` when set (WP08) and otherwise `target_branch`. Every reader was made ready in WP02 and WP04. This WP turns the #5100 red-first acceptance test green for the **unprotected** cases (FR-003, FR-006, FR-011, SC-001).

**Done when**:
- `tests/integration/test_issue_5100_single_branch_topology.py` was committed RED first.
- Its unprotected cases now pass.
- Its protected and override cases are `xfail(strict=True, reason="WP08")`.
- The blast-radius tests pass.

## Context & Constraints

- Read first:
  - `spec.md` US2 (all scenarios and controls);
  - `plan.md` IC-03, the folds (B3 and the "Feasibility / fixtures" bullets), and the WP order note;
  - `contracts/single-branch-execution.md` "Finalize".
- `planning_artifact_wps` in the finalize JSON (`compute.py:563/770`, `mission_finalize.py:1919/2860`) **stays derived from WP kind**, not lane membership.
- `compute_and_persist._preserved_mission_branch` (`:68-81,170`) must not re-inject a stale `kitty/mission-…` value for single_branch (fold B3). That is an out-of-map edit to WP03's file; record the rationale.
- **Integration test location.** `tests/integration/**` is sibling-owned (C-005). Only this one new file is added, as the brief directs. Note it in the PR overlap list.

## Branch Strategy

- **Planning base / merge target**: `issue-5100-single-branch-topology`. Run `spec-kitty implement WP05 --mission single-branch-topology-honesty-01M3M22V`.

## Subtasks & Detailed Guidance

### Subtask T021 – Red-first #5100 acceptance test (commit FIRST, alone)

- **File**: `tests/integration/test_issue_5100_single_branch_topology.py`. Module markers: `pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]`.
- **Fixture approach** (plan folds, "Feasibility"):
  - Start from `tests/e2e/conftest.py::e2e_project`, which runs on the unprotected branch `e2e-status-commit`. Re-export it with `from tests.e2e.conftest import e2e_project  # noqa: F401`, following the precedent in `tests/git/protected_target_fixtures.py`. Or build a minimal equivalent.
  - Drive the real CLI through `typer.testing.CliRunner` on the root app, or `run_cli` if a subprocess is needed.
  - Create the mission with `--topology single_branch` explicitly. The default changes in WP06; do not depend on it.
  - Write two code_change WPs (WP02 depends on WP01) with `owned_files` in `src/`, then run `finalize-tasks` and `implement WP01`.
  - Use a module-scoped template copied per test where practical.
- **Tests**, one function each:
  1. `test_finalize_writes_single_repo_root_lane`: `lanes.json` has exactly one lane, `lane-planning`, containing WP01 and WP02.
  2. `test_implement_runs_in_repo_root_without_lane_artifacts`:
     - `implement WP01` exits 0 and WP01 is `in_progress`;
     - no `.worktrees/*-lane-*` exists;
     - `git for-each-ref refs/heads/kitty/mission-*` is empty;
     - the resolved workspace (from `--json` output, or `resolve_workspace_for_wp`) equals the repository root;
     - the claimed/in_progress events have `execution_mode == "direct_repo"`.
  3. `test_lanes_control_creates_lane_worktree`: the same fixture with `--topology lanes` creates exactly one lane worktree and stamps `worktree`. This is the non-vacuity control.
  4. `test_for_review_without_force`: commit an owned file in the repository root, then `move-task WP01 --to for_review` without `--force` succeeds and the event is stamped `direct_repo`. Control: with no commit, it is refused.
  5. `test_second_implement_refused_names_in_progress_wp`: `implement WP02` while WP01 is `in_progress` exits non-zero, the output contains `WP01`, and nothing is created.
  6. `test_dirty_checkout_refused_but_resume_allowed`: an untracked file outside spec-kitty paths makes `implement` of a new WP fail; `implement WP01` again (resume) succeeds.
  7. `test_protected_target_mints_mission_branch`, marked `@pytest.mark.xfail(strict=True, reason="WP08")`: create on `main` (protected by default) with `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS` unset. Assert `kitty/mission-<slug>-<mid8>` exists and is checked out in the repository root, and that there is no worktree.
  8. `test_commit_to_target_overrides`, marked `@pytest.mark.xfail(strict=True, reason="WP08")`: its own function, because `--commit-to-target` is a usage error today.
- **The red must be for the right reason.** On the planning base, test 1 fails on the lane count and test 2 on the `lane-a` worktree assertion, not on fixture crashes. Pre-assert the setup commands' exit codes with distinct messages.
- Commit this test alone: `test(integration): red-first #5100 single_branch topology acceptance`.

### Subtask T022 – `compute_lanes(topology=single_branch)`

- In `lanes/compute.py:477`, add `topology: MissionTopology` as a keyword to `compute_lanes`. The call site `compute_and_persist.py:146` is threaded by WP03.
- For `SINGLE_BRANCH`:
  - return a `LanesManifest` with one `ExecutionLane(lane_id=PLANNING_LANE_ID, wp_ids=<all WPs in dependency order>, ...)`;
  - set `mission_branch = meta.mission_branch or target_branch`. Pass `mission_branch` in as a parameter rather than reading meta inside `compute_lanes`; it is documented as meta-free;
  - leave `planning_artifact_wps` kind-derived.
- For every other topology, behaviour is byte-identical to today.
- **Fail-closed call sites (moved here from WP03, post-tasks fold B-2):** in the same commit, call `assert_topology_matches_manifest(...)` in `compute_and_write_lanes` (after compute, before write) and at the top of `allocate_lane_worktree` (before any git mutation; out-of-map edit to WP07's file). Add `tests/lanes/test_single_branch_code_lanes_fail_closed.py` (US5.3, **two asserts**): an unmigrated single_branch mission with a hand-written code-lane manifest (a) fails `finalize-tasks` and (b) fails `implement` / `allocate_lane_worktree`, each with `SINGLE_BRANCH_CODE_LANES_UNMIGRATED` and no `.worktrees/` created.
- **Tests**: `tests/lanes/test_compute_lanes_single_branch.py`:
  - a single_branch manifest shape;
  - a lanes control with an identical manifest before and after (golden compare against `compute_lanes` without the new path);
  - `mission_branch` falls back to `target_branch`.

### Subtask T023 – Finalize wiring and JSON

- In `mission_finalize.py` (`_compute_and_write_lanes` at `:2439`/`:2992`, and the call at `:2503`), pass the topology from `read_topology(meta)` and the mission branch from meta.
- The finalize JSON must still report `planning_artifact_wps` by kind. Add a lane-count field only if one exists already.
- Run `finalize-tasks --validate-only` on a single_branch fixture and confirm that no lane validation (ownership overlap across lanes, etc.) wrongly fires for the single lane.

### Subtask T024 – Green end-to-end; blast radius

- Make tests 1–6 of T021 pass.
- Blast-radius tests (post-tasks fold B-2; WP06 already made the implicit default `lanes`, so default-created missions are unaffected). These explicit-single_branch fixtures change and must be updated here (minimal edits, rationale each):
  - `tests/specify_cli/cli/commands/agent/test_issue_2684_subtask_completion_event_sourced.py` (hand-written SINGLE_BRANCH + `lane-a`, asserts `.worktrees/*-lane-a` at ~:279) → give the fixture explicit `topology: lanes`.
  - `tests/integration/test_explicit_checkout_commands.py` and `tests/integration/test_owned_checkout_mark_status.py` (owned single_branch checkout) → expect the repo-root lane / write checkout.
  - Re-run `tests/e2e/test_cli_smoke.py` (`test_full_workflow_sequence`) and `tests/e2e/test_charter_epic_golden_path.py` — they must stay green.
  - The finalize tests (grep `compute_lanes\|finalize-tasks`).
- **NFR-002 evidence:** time one `implement WP01` on the single_branch fixture and record the sample in the Activity Log (must be < 2 s excluding hook/interpreter startup noted separately).

## Test Strategy

```bash
.venv/bin/python -m pytest tests/integration/test_issue_5100_single_branch_topology.py tests/lanes/test_compute_lanes_single_branch.py -q
grep -rl "compute_lanes\|finalize_tasks\|finalize-tasks\|lane-a" tests/lanes tests/specify_cli/cli/commands/agent tests/e2e --include=*.py   # run each listed file
make test-fast
.venv/bin/mypy --strict src/specify_cli/lanes/compute.py src/specify_cli/cli/commands/agent/mission_finalize.py ; .venv/bin/ruff check . ; .venv/bin/ruff format --check .
```

## Risks & Mitigations

- **An e2e fixture's runtime (5–15 s).** Use `CliRunner` plus a module-scoped template. Mark a test `slow` only if it exceeds 30 s.
- **A WP04 reader gap surfaces only now.** Fix it in the owning module as an out-of-map edit with a rationale, and add a unit test there.

## Review Guidance

- Verify red→green: the T021 commit fails on the planning base for the right reason.
- Verify the lanes control.
- Verify the xfails are strict.
- Verify `planning_artifact_wps` is unchanged.

## Activity Log

- 2026-09-28T14:00:00Z – system – Prompt created.
