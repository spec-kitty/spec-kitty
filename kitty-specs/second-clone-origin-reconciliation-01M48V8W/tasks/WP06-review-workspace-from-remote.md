---
work_package_id: WP06
title: review prepares the lane from the remote (#5758)
dependencies:
- WP03
requirement_refs:
- FR-005
- C-003
- SC-002
- NFR-004
- SC-004
planning_base_branch: claude/happy-keller-r38xig
merge_target_branch: claude/happy-keller-r38xig
branch_strategy: Planning artifacts for this mission were generated on claude/happy-keller-r38xig. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/happy-keller-r38xig unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-second-clone-origin-reconciliation-01M48V8W
base_commit: 823ac378c636a6483fbae6f99a4941508de9b8ba
created_at: '2026-10-06T16:45:25.567935+00:00'
subtasks:
- T028
- T029
- T030
- T031
- T032
phase: Phase 3 - Gates
history:
- at: '2026-10-06T15:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/terminus/test_review_sees_teammate_fix.py
- tests/specify_cli/cli/commands/agent/test_review_lane_from_remote.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/workflow.py
- tests/terminus/test_review_sees_teammate_fix.py
- tests/specify_cli/cli/commands/agent/test_review_lane_from_remote.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – review prepares the lane from the remote (#5758)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log; address every feedback item before handing back.

---

## Objectives & Success Criteria

`spec-kitty agent action review <WP>` reviews what the teammate pushed (FR-005, C-003, SC-002; closes #5758 P0):
- local lane strictly behind the remote, every checkout of it clean, no live foreign review lock → fast-forward the lane to the remote tip (through `git.ref_advance.advance_branch_ref`, which dirty-checks and resyncs every checkout) and `lanes.lane_tip.record_tip`; print `Updated <lane> from <remote>/<lane> (<n> commits)`;
- no local lane but the remote has it → create the review workspace from `refs/remotes/<remote>/<lane>` (`git worktree add <path> -b <lane> <tracking ref>`), not from HEAD;
- local lane exists without a workspace and is behind → fast-forward before `git worktree add`;
- diverged → refuse `ORIGIN_LANE_DIVERGED` (exit 1) before the review lock;
- behind but a checkout is dirty, or a live (non-stale) review lock held by another agent → refuse (exit 1), naming the remedy;
- unreachable remote → warning, continue on the last-known view;
- workspace resolved in the repository root checkout (`workspace.runs_in_checkout_root`: planning lane, `single_branch`) → skipped entirely (that branch is the status evidence branch, C-002).

## Context & Constraints

- Read `spec.md` US2, FR-005; `plan.md` "Where each gate calls the check" (review bullet: NO `is_residue` — `.spec-kitty/` is gitignored + in `info/exclude`, the dirty check ignores untracked/ignored entries; a broad residue predicate would exempt tracked edits that the resync `reset --hard` would discard); `contracts/origin-freshness.md` (`plan_review_lane`).
- Current code: `src/specify_cli/cli/commands/agent/workflow.py::_prepare_review_workspace` (~:1955). Order today: husk check → create (rev-parse + `worktree add [-b]` from HEAD) → lock. New order: husk → freshness plan → (ff / create-from-remote / refuse / warn) → lock.
- `advance_branch_ref(repo_root, branch, new_sha, *, expected_old_sha=<local sha>)` (git/ref_advance.py:665) — call only; C-007 forbids editing it. It raises on a dirty checkout (`CheckoutDirtyError`-style; read the module for the exact exception names) — catch and convert into the refusal.
- Review lock: `review/lock.py` — `ReviewLock.load(worktree)`, `.is_stale()`, `.agent`; a live lock by a DIFFERENT agent blocks the fast-forward; the reviewer's own stale/live lock does not.
- Lane tip: `lanes.lane_tip.record_tip(repo_root, branch, sha)`.
- Campsite first (T029) keeps `_prepare_review_workspace` small (python-pedro brownfield cut: 80 lines today, two raw `subprocess.run` calls with repeated kwargs).

## Branch Strategy

- **Strategy**: lanes; worktree allocated by `spec-kitty implement WP06`.
- **Planning base / merge target**: `claude/happy-keller-r38xig`.

## Subtasks

### T028 — Red-first regression (#5758) — FIRST commit

`tests/terminus/test_review_sees_teammate_fix.py` (`regression`, `integration`, `git_repo`; docstring cites #5758, ADR 2026-07-17-1). Real CLI via `run_terminus`.
- Arm A (re-review): `build_coord_mission` with WP02 on its own lane; push all to a bare remote (`two_clone_support`); A creates the review workspace for WP02 (run `agent action review WP02` once, or materialize the lane worktree); clone B commits "fix v2" on the lane and pushes; A `git fetch`; A runs `agent action review WP02` again → the review workspace file shows v2; the output says `Updated`.
- Arm B (no local lane): A deletes its local lane branch + worktree; A runs review → workspace created from the remote lane (file present with v2 content), not from HEAD.
- Arm C (end-to-end, optional if cheap): after A approves, consolidate lands v2 on the target.
Read the existing reviewer flow requirements (status must be `for_review`, `--agent`) from `tests/terminus` / `tests/review` neighbours. Prove red, commit.

### T029 — Campsite: extract `_create_review_worktree` (separate commit)

Move the creation block (rev-parse + `worktree add` + error rendering) into `_create_review_worktree(workspace, main_repo_root, wp_id, *, start_point: str | None)`; `start_point=None` reproduces today's behaviour. Run `tests/specify_cli/cli/commands/test_workspace_husk_resolution_1833.py` and `tests/specify_cli/cli/commands/agent/test_review_lock_error_output.py` before/after — unchanged.

### T030 — Wire the plan

`_prepare_review_workspace`: after the husk check, `if not workspace.runs_in_checkout_root and workspace.branch_name:` call `origin_freshness.plan_review_lane(main_repo_root, branch)` and act on `kind` (helper `_apply_review_lane_action(...)` to keep C901 ≤ 15). Fast-forward: check live foreign lock (only when the workspace exists), then `advance_branch_ref(..., expected_old_sha=local_sha)`, `record_tip`, print. Create-from: pass the tracking ref as `start_point` to `_create_review_worktree` (when the local branch is missing). Refuse: print the message (rich-escaped, see the #4163 note in the function) and `raise typer.Exit(1)` before any lock. Warn: print and continue.

### T031 — Focused tests

`tests/specify_cli/cli/commands/agent/test_review_lane_from_remote.py` (real git, small): diverged → exit 1 + `ORIGIN_LANE_DIVERGED`, no lock file created; dirty tracked file in the lane worktree + behind → refused, file content intact; live foreign lock + behind → refused; unreachable remote → warning + review proceeds; checkout-root workspace → `plan_review_lane` never called (patch it to raise); up-to-date → no output change.

### T032 — Sweep

```bash
.venv/bin/python -m pytest -q tests/terminus/test_review_sees_teammate_fix.py tests/specify_cli/cli/commands/agent/test_review_lane_from_remote.py
.venv/bin/python -m pytest -q tests/specify_cli/cli/commands/test_workspace_husk_resolution_1833.py tests/specify_cli/cli/commands/agent/ tests/review/
.venv/bin/python -m pytest -q $(ls tests/specify_cli/cli/commands/test_single_branch_review_path.py 2>/dev/null)
make test-fast
```
Plus ruff/format(`--force-exclude`)/mypy on touched files.

## Definition of Done

- [ ] Regression red first, green after; arms A and B both pass.
- [ ] No ref moved except the reviewer's local lane, only forward, only via `advance_branch_ref`.
- [ ] Refusals happen before the review lock is acquired; no husk left behind.

## Risks

- The lane may be checked out in the implementer's lane worktree in the same clone: `advance_branch_ref` resyncs every checkout or refuses if one is dirty — rely on it, do not special-case.
- Review status transitions (`for_review → in_review`) happen after workspace prep — a refusal must not leave a half-transition (check where `_prepare_review_workspace` is called relative to status emission).

## Reviewer Guidance

Re-run arm A with the fix stashed to see v1. Check no `is_residue` is passed. Check the checkout-root skip.

## Post-tasks squad folds (binding — supersede conflicting text above)

- PLACEMENT CHANGE: the lane freshness step runs in the `review` command right after `lane_ctx = _executor.review_resolve_wp_and_lane_gate(...)` and BEFORE `review_enforce_bulk_edit_gate` (~:2108) and `review_claim_transition` (~:2131), so a refusal leaves the WP status untouched and the bulk-edit gate judges the updated lane. Implement it as `_reconcile_review_lane(review_workspace, main_repo_root, wp_id, agent)` (new helper, C901 ≤ 15) called from `review`; `_prepare_review_workspace` only receives the `create_from` start point. The WP08 registry entry point is the `review` command. Test: after a refusal the WP's lane/status is unchanged (no in_review event).
- Fixture: use the LANES topology (`tests/terminus/lanes_fixture.py`, status on the target) — that is the #5758 shape: A's `git pull` of the target brings B's `for_review` status while A's local lane stays at v1. Do not rely on coordination topology for arm A (A's coordination view would block review at the lane gate).
- Arm B must NOT do a full fetch in A: use `git pull origin <target>` (fetches only the target), so the arm proves the review step refreshes the lane itself (FR-006).
- Arm C (consolidate lands v2) is MANDATORY (SC-002).
- Exceptions: dirty checkout → `RefAdvanceDirtyWorktreeError` (git/ref_advance.py ~:225, a `RuntimeError`, NOT a `RefAdvanceError` subclass); non-fast-forward → `RefAdvanceNonFastForwardError`; CAS race → the module's CAS error. Catch each explicitly.

## Activity Log

- 2026-10-06 — prompt generated.
