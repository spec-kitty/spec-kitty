---
work_package_id: WP03
title: No lane leaves through the older remover without a proof
dependencies:
- WP01
requirement_refs:
- FR-008
- C-001
- C-003
- SC-003
planning_base_branch: fix/7747-lane-cleanup-landing-proof
merge_target_branch: fix/7747-lane-cleanup-landing-proof
branch_strategy: Planning artifacts for this mission were generated on fix/7747-lane-cleanup-landing-proof. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7747-lane-cleanup-landing-proof unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-lane-cleanup-landing-proof-01M81KHJ
base_commit: b4990b07205bf36bce6eb60c4d9f5154730f41c4
created_at: '2026-11-23T21:07:43.836965+00:00'
subtasks:
- T011
- T012
- T013
phase: Phase 2 - Adoption
history:
- at: '2026-11-23T18:30:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/consolidation/
create_intent:
- tests/consolidation/test_lane_remover_proof_unavailable_7325.py
execution_mode: code_change
owned_files:
- tests/consolidation/test_lane_remover_proof_unavailable_7325.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – No lane leaves through the older remover without a proof

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address every feedback item; record progress with `spec-kitty agent tasks add-history WP03 --note "..."`.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

- `GuardedLaneRemover.remove` never hands a lane with a branch leg to `MainTodayRemover`. When no usable landing proof exists the lane is `kept` with `LANDING_PROOF_UNAVAILABLE` and its branch survives (#7325).
- A lane whose worktree and branch are both gone is `removed` (nothing remains; FR-034 unchanged).
- The retained-branch leg (`item.branch is None`, worktree to remove) keeps today's guarded worktree removal (plan PD-1, Decision Moment 01M84SX5).

## Context & Constraints

- Spec FR-008, C-001 (no guard change), C-003 (`mission close --discard` keeps `MainTodayRemover`).
- **Out-of-map edit (rationale):** the change lives in `src/specify_cli/consolidation/lane_cleanup.py`, which WP01 owns; WP03 depends on WP01 and runs after it, so there is no parallel collision. Keep the edit to `GuardedLaneRemover.remove` and a new helper.
- Contract: `contracts/landing-proof.md` (kept line fields).

## Branch Strategy

- **Planning base branch**: fix/7747-lane-cleanup-landing-proof
- **Merge target branch**: fix/7747-lane-cleanup-landing-proof

Implement with `spec-kitty agent action implement WP03 --agent claude --mission lane-cleanup-landing-proof-01M81KHJ`.

## Subtasks & Detailed Guidance

### Subtask T011 – Red-first tests

- **File**: `tests/consolidation/test_lane_remover_proof_unavailable_7325.py` (new, in-matrix). Fixture like `tests/consolidation/test_lane_remover_guard_binding.py::unlanded`.
- Cases:
  - worktree removed by hand (`git worktree remove`), a unique commit then added on the branch (`git commit-tree` + `update-ref`, or a temporary worktree), cleanup with `LocalTargetAtPass(main, <main tip>)` → `KEPT`, code `LANDING_PROOF_UNAVAILABLE`, branch exists at the unique commit (today: deleted, `Removed`);
  - worktree present, `LocalTargetAtPass(passed_sha="")` → `KEPT LANDING_PROOF_UNAVAILABLE`, worktree and branch exist;
  - `landing=None` → `KEPT LANDING_PROOF_UNAVAILABLE`;
  - worktree and branch both gone → `REMOVED`;
  - `item.branch is None` with a removable worktree (retained branch) → worktree removed, branch untouched (PD-1; today's behavior, pinned);
  - through `lane_cleanup.apply(..., retention=LaneRetention(delete_branch=False))`: the report reads "worktree removed; branch retained" (unchanged);
  - the kept line's `command` is `None` when no worktree remains, `spec-kitty doctor workspaces --prune` when one does; the remedy names the branch and `git log <landing>..<branch>`.
- Commit red-first before T012.

### Subtask T012 – Keep the lane

- In `GuardedLaneRemover.remove`:
  1. `item.branch is None` → `self._fallback.remove(...)` (PD-1; comment names the decision).
  2. `_proof_unavailable(item, landing)` → a kept result or `None`:
     - `landing is None` → "no landing proof was given";
     - `LocalTargetAtPass` with blank `passed_sha` → "no reconciliation PASS anchor was recorded";
     - worktree missing (`item.worktree is None` or not `safe_is_dir`): branch tip absent → `REMOVED` (nothing left); else kept, "the worktree is gone, so the landing cannot be proven here";
     - no tip (`item.expected_tip` and the branch tip both absent) → kept.
  3. Otherwise the guarded path, unchanged.
- Add `LANDING_PROOF_UNAVAILABLE = "LANDING_PROOF_UNAVAILABLE"` and export it in `__all__`.

### Subtask T013 – Kept line and docs

- Remedy: `"{reason}; check {branch} with `git log {landing_ref}..{branch}` and delete it by hand only if its work is on {landing_ref}"`.
- `command`: `BACKSTOP_COMMAND` only when the worktree still exists (extend `_kept` with an optional `command`, default unchanged).
- Update the module and class docstrings (the fallback is now only the retained-branch leg).

### WP01 review folds (dispatcher relay 2026-11-23)

The WP01 reviewer's non-blocking findings 1-3 are folded here, not on the approved lane-a:
- the status-log-deletion exception is pinned by a test and stated in the docstring, the ADR, FR-005 and C-004;
- direct tests cover the both-sides clause, the own-Mission-only set-aside, the git-error path, the root-commit helper and the lost-through-a-sync-merge rule;
- the ADR says the set-aside applies to the lane's own changes only.

**Out-of-map edits (rationale):** `src/specify_cli/consolidation/lane_cleanup.py`, `src/specify_cli/lanes/lane_tip.py` (docstring), `tests/lanes/test_lane_tip_mission_bookkeeping.py`, the ADR, and `tests/consolidation/test_lane_cleanup_kept_report.py`. Two cases in that last file relied on the old fallback deleting the branch of a worktree-less lane, so they are re-pinned. WP01 is approved and no other WP touches these files.

## Test Strategy

```bash
uv run --frozen pytest tests/consolidation/ -q -n auto --dist loadfile
uv run --frozen pytest tests/architectural/test_destructive_op_routing.py -q   # out-of-matrix: disclose
uv run --frozen pytest tests/specify_cli/git/test_landed_removal_obligations.py -q   # out-of-matrix: disclose
make test-fast
uv run --frozen mypy src/specify_cli/consolidation/lane_cleanup.py
```

## Risks & Mitigations

- A resumed cleanup whose worktree was removed before a kill now keeps the branch: intended (#7325); the remedy names the check.

## Review Guidance

- No guard change; `MainTodayRemover` is reached only for `item.branch is None`.

## Progress & Status

Progress lives in the status event log. Use `spec-kitty agent tasks add-history WP03 --note "..."`.
