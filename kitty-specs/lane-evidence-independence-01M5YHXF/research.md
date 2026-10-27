# Research: Lane evidence and review independence (#6715)

Base: `main` at `7c45fa43` (4.0.0rc8). Every claim below was checked against live code and a
CLI-driven reproduction in an isolated HOME and temp repository.

## Red baseline (reproduced)

| Topology | Hollow self-approval (`move-task --to approved --agent claude`) | accept | consolidate | WPs done | owned file on target |
|----------|------|--------|-------------|----------|------|
| coord | rc 0 (auto-walk in_progress→for_review→in_review→approved) | rc 0 | rc 0, "Reconciliation verified" | 2/2 | absent |
| lanes | rc 1 ("No implementation commits on lane branch") | – | – | – | – |

On lanes the move is only caught because the lane has zero commits beyond the Mission branch;
`--force`, or any non-owned commit on the lane, gets past it, and nothing behind it checks.

## Findings

1. **Move gate.** `tasks_move_task._mt_require_single_branch_implementation` returns early for
   any non-single_branch Mission. The lanes readiness check counts commits
   (`lanes._git.lane_has_commit_beyond_base`, `rev-list base..HEAD`). Under coord the lane carries
   tool bookkeeping commits ("Merge recorded planning-artifact commit into lane-b (FR-009)",
   "chore: Start WP02 implementation", merges of the Mission branch), so the count is > 0.
   - Decision: an owned-file content check, not a commit count.
2. **Consolidate.** `approved_bound.check_lane` refuses only commits after the approval stamp; an
   empty lane is "nothing to bound" (deliberate, ADR `2026-10-04-5`). The #5939 axis
   (`reconciliation._single_branch_evidence_refusal`) runs only for single_branch.
   - Decision: generalise that axis; leave `approved_bound` unchanged (C-001).
3. **Accept** has no evidence or independence check on any topology.
   - Decision: a hard preflight before the summary, independent of `--lenient`.
4. **orchestrator-api.** `consolidate-mission` runs only the single_branch check
   (`_refuse_single_branch_hollow_content`); `accept-mission` checks lanes only.
   - Decision: run the shared predicate in both, as `PREFLIGHT_FAILED` / `MISSION_NOT_READY`
     with codes in `data`.

## Independence identity

- The recorded role is stamped from the target lane (`tasks_move_task_hops._binding_role_for_lane`:
  claimed→implementer, in_review/approved/done→reviewer; `workflow_executor._IMPLEMENT_CLAIM_ROLE`)
  and the role segment of `--agent` is discarded (`emit.build_self_asserting_actor`). A role
  comparison would always differ, so it cannot detect self-approval.
- Decision (operator, 2026-10-27): keep the #5939 identity `tool:model:profile`
  (`preflight._independent_reviewer_confirmed` / `status.models.actor_full_identity`) unchanged.
- Alternatives considered: profile-else-tool; strict profile; persisting a chosen role (new
  field). All rejected by the operator.

## Evidence window

- Decision: code lane `planning_commit_sha..<lane branch>`; planning lane
  `planning_commit_sha..<target branch>`; single_branch unchanged.
- Rationale: `planning_commit_sha` is recorded by `finalize-tasks`, is a fixed point (survives a
  resume after lanes landed on the target), and is already the single_branch base. A tree diff
  makes a commit-then-revert count as nothing. Disjoint ownership keeps sibling-lane content
  merged into a lane out of this WP's match.
- Alternatives: `merge-base(target, lane)`, rejected because after a lane lands on the target the
  merge-base is the lane tip and the diff empties on a resume; commit-log path union, rejected
  because a revert would still count.
- Bookkeeping exclusions: `kitty-specs/<slug>/status.*`, `issue-matrix.*`, `meta.json`, `.kittify/`
  (the `for_review_gate` set), so a planning-lane WP owning `kitty-specs/<slug>/**` cannot pass on
  status commits.

## Attestation

- Modelled on `approved_attestation` / `canceled_attestation`: forced self-transition through
  `emit_status_transition_transactional`, `reason_source = operator`, required reason.
- Must be excluded from `_latest_actor_for_transition` (else the operator becomes the "approver")
  and is never an approval stamp (`approved_bound.approval_stamp` reads only review approvals and
  `approved_reviewed`; the new value is neither: verified, no change needed).
- Recordable from `accept` and `consolidate` because accept now refuses first.

## Adversarial evidence

No dependency decision is made; the pre-PR adversarial squad (correctness + boundary lenses) runs
on the aggregate diff before the draft PR.
