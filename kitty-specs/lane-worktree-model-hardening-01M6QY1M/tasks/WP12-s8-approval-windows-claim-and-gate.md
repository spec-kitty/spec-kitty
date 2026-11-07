---
work_package_id: WP12
title: S8 - per-WP approval windows at claim and gate
dependencies:
- WP11
requirement_refs:
- FR-071
- FR-072
- FR-073
- FR-074
- FR-076
- FR-078
- SC-008
- SC-012
- NFR-007
- C-012
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-lane-worktree-model-hardening-01M6QY1M
base_commit: a4e342649cfe4936e89b4da0e8599dffc658ace2
created_at: '2026-11-06T11:51:23.165655+00:00'
subtasks:
- T067
- T068
- T069
- T070
- T071
- T072
- T073
phase: Phase 4 - S8 approval windows for single_branch
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- src/specify_cli/consolidation/write_branch_bound.py
- tests/consolidation/test_write_branch_bound.py
- tests/integration/test_single_branch_approval_windows.py
- tests/orchestrator_api/test_single_branch_bound_preflight.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/write_branch_bound.py
- src/specify_cli/consolidation/reconciliation.py
- src/specify_cli/consolidation/phase_gate.py
- tests/consolidation/test_write_branch_bound.py
- tests/integration/test_single_branch_approval_windows.py
- tests/orchestrator_api/test_single_branch_bound_preflight.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP12 - S8: per-WP approval windows at claim and gate

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item; record progress with `spec-kitty agent tasks add-history WP12 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP12 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

## Objectives & Success Criteria

S8 (#7283), bound half, applied only when `lands_mission_branch` (a recorded `mission_branch` that differs from the target):

- FR-071 (tier 1): content committed after the newest approval stamp refuses `LANE_MOVED_AFTER_APPROVAL` at claim time, before any branch moves.
- FR-072 (tier 2): every content commit in `claim_base..mission_branch` (merges and bookkeeping excluded) lies in some approved WP's window `(O_k, S_k]`; otherwise `LANE_MOVED_AFTER_APPROVAL`, naming the commit and the preceding WP. Overlapping windows accepted. Missing `O_k` degrades to `(claim_base, S_k]` and is logged (A-8).
- FR-073: the gate re-check compares the Mission branch's live tip against its claim-time tip through the claim's `lane_id -> branch` map (never `_lane_branch_for("lane-planning")`, which resolves to the target) and restores through the one rollback authority; the run's own bookkeeping commits never refuse.
- FR-074: unstamped approvals refuse `APPROVAL_STAMP_MISSING`; `--attest-approved-reviewed <WP> --attest-reason` lifts per WP; a rebased Mission branch refuses `APPROVAL_STAMP_NOT_ON_LANE`.
- FR-076 / C-012 / SC-012: no new orchestrator-api code; `consolidate-mission` returns `PREFLIGHT_FAILED` with the reused codes in `preflight_error_codes`.
- FR-078: commit-to-target stays unbounded, pinned by a strict xfail naming the residual.
- NFR-007: the claim check adds <= 2 s for 10 WPs and 200 commits.
- SC-008: 100% of late/out-of-window commits refused; 0 false refusals.

## Context & Constraints

- Read: spec User Story 4 (scenarios 1-6), FR-071 to FR-078, A-4, A-8, Edge Cases ("rebased onto the target", "tool commits after approval"); `research.md` R-7, R-8; `data-model.md` §5 (`ApprovalWindow`, membership rule, `BoundRefusal` shape); WP02's ADR `2026-10-04-5` amendment; CLAUDE.md "Approved claim is bounded by the approval stamp" and "Refusals and failures roll back through one authority".
- Builds on WP11: `write_branch_for`, `stamp_refusal`, `_approval_is_bounded`, the `single_branch` `lane_head` stamps. `O_k` = `wp_attribution.first_governed_open_stamp`; `S_k` = newest approval stamp (or approved-reviewed attestation).
- Rollback: only through `consolidation/rollback.py::rollback_to_snapshot`; the AST pin `tests/consolidation/test_single_rollback_authority.py` must stay green.
- Reuse `_is_bookkeeping` for bookkeeping paths; reuse existing refusal rendering (`approved_bound.render_refusals`).
- C-011 red-first; complexity <= 15 (tier 2 lives in its own module for that).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

## Subtasks & Detailed Guidance

### Subtask T067 - Red-first claim scenarios

`tests/integration/test_single_branch_approval_windows.py`, a minted `single_branch` repository driven through `spec-kitty consolidate`:

- `test_late_commit_after_last_approval_refuses` (exit 1, target unchanged, names `X`)
- `test_commit_between_two_approvals_refuses_naming_preceding_wp` (WP01 approved, `X`, WP02 claimed after `X` and approved -> refuses naming `X` and WP01)
- `test_overlapping_review_passes` (WP02 committed while WP01 in review; both approved)
- `test_rework_after_later_approval_passes`
- `test_reapproval_lifts_refusal` (scenario 4)

### Subtask T068 - Red-first legacy, gate and contract scenarios

- `test_unstamped_approval_refuses_then_attest_lifts`
- `test_rebased_mission_branch_refuses_stamp_not_on_lane`
- `test_gate_recheck_mid_run_commit_rolls_back` (commit lands between claim and gate; target restored)
- `test_own_bookkeeping_commits_never_refuse`
- `test_target_merge_into_mission_branch_never_refuses`
- `tests/orchestrator_api/test_single_branch_bound_preflight.py::test_orchestrator_preflight_failed_carries_reused_code` (FR-076)
- `test_commit_to_target_unbounded_residual` marked `pytest.mark.xfail(strict=True, reason="FR-078 residual: commit-to-target single_branch is unbounded")`
- `tests/consolidation/test_write_branch_bound.py`: unit tests of window membership incl. missing `O_k` degrade logged; `test_bound_cost_10wp_200_commits` (NFR-007; mark per perf conventions, e.g. `timing` if that marker exists).

### Subtask T069 - `write_branch_bound.py`

- `check_write_branch(repo_root, mission, claim_base, mission_branch, approvals) -> tuple[BoundRefusal, ...]`:
  - tier 1 via WP11's `stamp_refusal` + existing `check_lane` logic on the Mission branch;
  - tier 2: list content commits `claim_base..mission_branch` (`git rev-list --no-merges`), drop bookkeeping-only commits, then for each commit test `reachable(c, S_k) and not reachable(c, O_k or claim_base)` for some approved `k`. Batch reachability (`git rev-list` per window once, set membership), never per-commit subprocesses (NFR-007).
  - Refusal: `BoundRefusal(code="LANE_MOVED_AFTER_APPROVAL", lane_id="lane-planning", branch=<mission_branch>, wp_ids=(<preceding approved WP>,), commits=(<sha>,))`.

### Subtask T070 - Claim arm

- `reconciliation._approved_bound_verdict` (`:~2145`): when the stored topology is `single_branch` and `lands_mission_branch`, call `check_write_branch`; compound with other claim-time refusals the same way (`_compound_refusal`). Run before the snapshot (nothing to roll back).

### Subtask T071 - Gate re-check

- `reconciliation.lane_tips_moved_refusal` (`:~2240`) takes a `lane_id -> branch` map from the claim; `phase_gate._lane_recheck_verdict` passes it. For `single_branch`, the map names the Mission branch. Commits made by this run (bookkeeping) are excluded via the existing anchors.

### Subtask T072 - Refusal text

- Text per `quickstart.md` §1: names commit and WP, "Send WP01 back for review and approve it again, or revert the commit." Add the tool-commits hint (e.g. `spec-kitty upgrade` committing agent directories on the Mission branch is a true positive; recover by re-approval or revert). Commands printed with the Mission slug.

### Subtask T073 - Quality gates and blast radius

See Validation.

## Validation

```bash
cd <workspace>
uv run --frozen pytest tests/integration/test_single_branch_approval_windows.py tests/consolidation/test_write_branch_bound.py tests/orchestrator_api/test_single_branch_bound_preflight.py -q
uv run --frozen pytest tests/consolidation tests/orchestrator_api tests/specify_cli/orchestrator_api -q -n auto --dist loadfile
uv run --frozen pytest tests/consolidation/test_single_rollback_authority.py tests/contract/test_orchestrator_api.py tests/architectural/test_layer_rules.py -q
make test-fast
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched>
uv run --frozen mypy --strict src/specify_cli/consolidation/write_branch_bound.py src/specify_cli/consolidation/reconciliation.py src/specify_cli/consolidation/phase_gate.py
```

Never `make test-full` or a bare `tests/architectural/` sweep.

## Tracer files

Return tracer lines in your completion summary (`- **[YYYY-MM-DD][implement WP12] ...**`, naming the trace file); the orchestrator appends them.

## Risks & Mitigations

- False refusals from target merges into the Mission branch: anchors exempt commits reachable from the claim base/target tip (test above).
- Performance: batched reachability.
- Contract drift: no new code; contract test guards it.

## Review Guidance

- Tier 1 + tier 2, per-WP not last-stamp only; gate reads via the map; one rollback authority; refuse-plus-attest; strict xfail residual; NFR-007 measured.

## Definition of Done

- T067-T073 done; tests green; tracer lines returned.

## Progress & Status

- `spec-kitty agent tasks mark-status T067 T068 T069 T070 T071 T072 T073 --status done --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks move-task WP12 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
