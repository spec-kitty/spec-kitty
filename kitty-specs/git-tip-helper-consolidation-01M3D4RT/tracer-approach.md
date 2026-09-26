# Tracer: Approach

Mission: git-tip-helper-consolidation (01M3D4RT) — Epic #4883 slice.

## Strategy
- Anchor #4857: give `classify_recorded_pin`'s target-branch tip ONE canonical
  capture authority (currently `lanes/merge._rev_parse` + `mission_finalize.
  _capture_target_branch_tip`). Consolidate to `git rev-parse --verify` + the
  merge-env authority (inert for rev-parse, required by the FR-008b ratchet).
  Prove the closed drift with an agreement test on valid/missing/AMBIGUOUS refs
  (ambiguous is RED pre-fix).
- Fold #4593 item1 (`--full-history` on the move-task behind-count) — shares the
  `core/vcs/git.py` blast radius with the anchor.
- Fold #4152 items 2&3 (dead-guard removal; load-bearing test exit-code).
- Excluded/declined recorded in spec.md issue-matrix: #4611 (→#4441), #4152 item1,
  #4593 item2.

## Grounding
- Two-lens grounding squad (paula-patterns alignment + planner-priti scope) run
  pre-spec; verdicts folded. Key corrections captured: real owned_files collision
  is `core/vcs/git.py` (not mission_finalize.py); #4611 reparented to #4441.

## Append during implement
- (WP notes go here)

## WP01 outcome (implemented + reviewed)
- All 7 subtasks landed in lane-a; 3 per-issue code commits (kept individual for the
  rebase-merge model). Opus reviewer-renata APPROVED: 193 targeted tests green, both
  RED-first regressions (#4857 tag-collision, #4593 TREESAME undercount) verified live,
  #4152 item2 behaviour-preserving + item3 load-bearing. No suppressions, no scope creep.
- Coord/lane friction encountered (recorded in tooling-friction): lane sparse-checkout +
  lifecycle writes (status.json/events) polluting the lane's kitty-specs tripped the
  for_review/approve gates; resolved by disabling sparse per-worktree and syncing the
  lane's kitty-specs to the primary partition.
