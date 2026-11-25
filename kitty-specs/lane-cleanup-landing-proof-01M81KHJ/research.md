# Research: One landing proof for lane cleanup

## R1. What differs between a landed lane and its target (squash, lanes_with_coord)

- Decision: the reproduction (`build()` harness, three lanes, implement → approve → default squash consolidate, 2026-11-22) kept 3 of 3 lanes `NOT_LANDED_ON_NAMED_REMOTE`. For lane-a the lane copy differs from the target copy for `meta.json`, `status.json`, `status.events.jsonl`, `tasks/WP02-work.md`, `tasks/WP03-work.md`; the lane lacks files the target gained (review cycles, retrospective, `.kittify/workspaces/*.json`), which is no lane content.
- Finding: none of the lane's differing Mission-file versions is in the target's own history. The squash collapses the coordination history into one commit, and the coordination branch is deleted before cleanup. Target `meta.json` records `merged_commit` and `baseline_merge_commit`, not the coordination tip.
- Consequence: an "ancestor in the target's history" rule alone cannot pass any squash-landed lane (escalated; operator ruled Option A on 2026-11-23).

## R2. Reading "never authored by the lane" from the lane's graph (Option A)

- Decision: lane-own commits = `git rev-list --first-parent <tip> ^<landing> ^<S...>` where S is every non-first parent of a first-parent merge in `<landing>..<tip>`. The history a lane forked from is coordination history its first sync merge reaches, so it drops out.
- A path is authored when a lane-own non-merge commit changed it against its first parent, or a lane-own merge changed it against its first parent with a result equal to none of its other parents' versions (a driver or conflict resolution counts as authored).
- Prototype on the reproduction: own commits per lane = its `feat(WPxx)` commit and its sync merge; authored = only the lane's product file. Every Mission-file difference is not authored.
- Alternatives: Option B (recorded coordination tip as extra history) rejected by the operator: doctor would need a new `meta.json` field, and Missions landed before it could never be pruned.
- Residual (accepted, ADR amendment): a version merged in from a branch other than the coordination branch (e.g. a dependency lane) counts as not authored on this lane.

## R3. Never trusting a merge result on `kitty-specs/**`

- Decision: the predicate does not start with plain `is_absorbed` (its merge-tree leg would accept a lane whose Mission file a merge driver resolved to the target's bytes). Order: ancestor check → lane-own authorship → merge-tree judged only on paths outside `kitty-specs/` → per-path rules for `kitty-specs/` paths that differ.
- Per-path rules for a `kitty-specs/` path whose lane copy differs from the target copy:
  1. the lane has no copy and did not author that → nothing to lose;
  2. the lane's own Mission status log → every lane event line is in the target's log (unchanged #6736 rule);
  3. `status.json`, `meta.json`, `tasks/WP*.md` of the lane's own Mission → both sides have it, and the lane did not author it or the target's history holds the lane's version;
  4. anything else → not landed.
- Any `GitCommandError` → not landed.

## R4. #7325 legs

- Every `GuardedLaneRemover` caller passes a landing proof (consolidate, orchestrator-api, pr-mode accept); `mission close --discard` builds `MainTodayRemover` directly (out of scope).
- Decision: keep with `LANDING_PROOF_UNAVAILABLE` when: no landing proof; a local proof with an empty PASS anchor; the worktree is gone while the branch exists; no tip can be named. A lane whose worktree and branch are both gone is reported removed (nothing remains, FR-034 unchanged).
- Retained-branch leg (`retain_branches`: worktree to remove, no branch leg): stays on today's guarded worktree removal, which deletes no branch, so it is not the #7325 blind spot and the retention report (FR-033) is unchanged.
- The kept line names the branch and the check to run (`git log <landing>..<branch>`); the `doctor workspaces --prune` backstop is named only when a worktree remains for it to judge.

## R5. Red-first list

- Integration: real squash landing → every lane `Removed` (today Kept). Doctor: lanes retained by the run's flags, target pushed to `origin/main` → every lane `landed` (today `CONTENT_NOT_ON_PRIMARY`).
- Negatives: own WP body edit kept; product code beside the status log kept (`test_unlanded_work_beside_the_status_log_is_not_absorbed` stays green); merge-driver case kept (control: plain `is_absorbed` passes it); worktree deleted + unique commit kept with branch; `LocalTargetAtPass(passed_sha="")` kept.
