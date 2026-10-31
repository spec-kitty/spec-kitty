# Discovery — pruned lane evidence window (#6780)

## Reproduction (reproduced on `main` at 512567eee7)

The issue says "not reproduced yet: the failure is inferred from the code". It
does reproduce.

Fixture (real git repository, production entry point `specify_cli.cli.commands.accept.accept`):

1. lanes Mission on `kitty/mission-321-pr-accepted-mission-01TEST`; WP01 done,
   implemented by `test-agent`, approved by the independent `test-reviewer`;
   `lanes.json` records `planning_commit_sha` (as `finalize-tasks` writes it).
2. `commit_lane_implementation` writes `src/wp01.py` on `lane-a`'s branch, which
   is created at the planning commit.
3. The lane branch is merged into the mission branch (`spec-kitty merge`
   semantics: lane content lands on the mission branch).
4. The mission branch lands on `main` through a PR-shaped `--no-ff` merge
   commit; its first parent predates the mission corpus, so
   `verify_pr_merge_evidence` accepts it with `--attest-first-landing-commit`.
5. `git branch -D kitty/mission-321-pr-accepted-mission-01TEST-lane-a`
   (post-merge cleanup).
6. `accept(mode="pr", merge_commit=<sha>, attest_first_landing=True)`.

Observed on current `main`:

```
IMPLEMENTATION_UNREADABLE: WP01's evidence window
3c25357f21cf809b7b067093521f3f9efe46fcb3..kitty/mission-321-pr-accepted-mission-01TEST-lane-a
(lane-a) could not be diffed (git diff --name-status <base>..<branch> failed
(exit 128): fatal: bad revision ...), so implementation evidence cannot be
verified.
Recovery for IMPLEMENTATION_UNREADABLE: make the lane branch and the recorded
planning commit readable (restore or fetch them), then re-run.
```

exit 1, `meta.json` unchanged (`baseline_merge_commit` not recorded) — the
mission cannot be accepted through its documented PR path even though
`src/wp01.py` is on `main`.

## Where the window is chosen (survey)

| File | Role |
| --- | --- |
| `src/specify_cli/consolidation/wp_evidence.py` | The #6715 axis. `lane_evidence_window()` returns `(planning_commit, lane_created_branch(...))` for a code lane, `(planning_commit, target_branch)` for a planning lane; `_scan_lane()` diffs it and turns a `GitProbeError` into one `IMPLEMENTATION_UNREADABLE` line per work package. `_RECOVERY[IMPLEMENTATION_UNREADABLE]` is the sole recovery sentence. |
| `src/specify_cli/consolidation/git_probes.py` | `changed_paths_in_range()` raises `GitProbeError` on any git error (fail-closed); `sha_reachable_from()` is the existing ancestor probe. |
| `src/specify_cli/lanes/_git.py` | `branch_exists()` (local ref only) and `ref_exists()` (any revspec that resolves to a commit) — the seams already used by `_dependency_evidence_windows()`. |
| `src/specify_cli/cli/commands/accept.py` | `accept()` verifies `--merge-commit` **before** the evidence gate (`pr_merge = _verify_merge_commit(...)` then `_refuse_unevidenced_work(...)`), so a verified landing commit is already in scope at the gate. `_refuse_unevidenced_work()` calls `mission_evidence_report()` and renders one `EvidenceReport` on both output lanes. |
| `src/specify_cli/consolidation/no_implementation_attestation.py` | `plan_no_implementation_attestations()` re-runs `evaluate_evidence()` for `--attest-no-implementation`; it is called by `accept` before the gate. |
| `src/specify_cli/cli/commands/agent/tasks_move_task.py` | The pre-review gate; separate call site, runs while lanes exist. Not in scope. |

## Decisions

- **D-1: The stand-in tip is the verified landing commit, not the target tip.**
  `verify_pr_merge_evidence` has already proven the commit (a) exists, (b)
  introduces the mission corpus, (c) is on the target branch. Diffing
  `planning_commit..landing_commit` therefore describes exactly the landed
  mission's content, which is what the gate is about ("did the owned deliverable
  land?"), and it needs no live branch ref.
- **D-2: The lane branch stays the first choice.** The fallback is consulted only
  when the window's tip does not resolve to a commit. A readable lane branch with
  a failing diff keeps today's `IMPLEMENTATION_UNREADABLE` — the fallback must
  never reinterpret a Mission whose lanes are intact (FR-002).
- **D-3: The fallback is opt-in from the caller that verified the landing.**
  `evaluate_evidence`/`mission_evidence_report` gain an optional
  `landed_commit`; only `accept --mode pr --merge-commit` supplies it. Consolidate,
  orchestrator-api, `move-task` and the single_branch leg call the axis exactly as
  today (C-003), so no other command silently broadens a window.
- **D-4: The base is unchanged, so the pass criterion is unchanged.** Same
  `planning_commit` base, same per-work-package `owned_files` match, same
  bookkeeping exclusion, same independence check. Only the tip standing in for a
  deleted ref changes; a work package with no owned-file change in the landed
  window still refuses `IMPLEMENTATION_MISSING` (FR-003, SC-002).
- **D-5: The fallback fails closed on a bad base.** If the planning commit is not
  an ancestor of the landing commit, the window would describe another history;
  refuse with an explicit reason instead of diffing (FR-006).
- **D-6: Dependency widening must use the same tip.** `_dependency_evidence_windows()`
  computes `merge-base(<dependency branch>, <lane branch>)`; with a pruned lane
  branch that probe would itself raise and re-introduce the blanket refusal. The
  effective tip is therefore threaded into the widening path (edge case in the spec).
- **D-7: The refusal gets honest.** The `IMPLEMENTATION_UNREADABLE` line names the
  absent ref and the recovery names both remedies (restore/fetch, or
  `--merge-commit`); nothing else about the refusal semantics changes (FR-004).
- **D-8: The attestation planner reads the same window.** `accept` passes the same
  verified landing commit into `plan_no_implementation_attestations()` so
  `--attest-no-implementation` cannot contradict the gate it runs before (FR-005).

## Alternatives considered

- **Diff against the target branch tip** instead of the landing commit: broader
  (every later commit on the target joins the window) and not anchored to the
  verified landing. Rejected.
- **Record per-lane merge commits in `lanes.json`/`meta.json`**: changes a
  persisted format that `--mode pr` never writes, and needs a new write in a flow
  that deliberately never runs `consolidate`. Rejected as out of scope.
- **Persist the lane branch tip SHA when the PR is opened**: needs a new write in
  a flow that has no hook for it, and still cannot help a mission already pruned.
  Rejected.
- **Lift the refusal by attestation**: the issue and #6715 both say
  `IMPLEMENTATION_UNREADABLE` is unliftable, and an attestation asserts "no
  implementation owed", which is the wrong statement for a landed mission.
  Rejected.

## Open questions (for plan)

- Should the fallback also apply to a *planning* lane whose target ref cannot be
  resolved? (Design: yes, it takes the same tip substitution, since the tip is a
  ref and not a semantics change.)
- Do the existing #6715/#5939 test modules pin the exact `IMPLEMENTATION_UNREADABLE`
  wording? (`grep` says only `wp_evidence.py` contains "restore or fetch";
  `tests/integration/test_6715_squad_identity_and_evidence.py` asserts the code
  and "Nothing was recorded", not the recovery sentence.)
