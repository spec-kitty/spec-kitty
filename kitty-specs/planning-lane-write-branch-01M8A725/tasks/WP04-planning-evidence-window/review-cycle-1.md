---
affected_files: []
cycle_number: 1
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-26T02:25:37Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP04
---

# WP04 review feedback (claude::reviewer-renata)

Overall: the design is sound and the core claims hold. `planning_evidence_window` is the one decision. `_scan_lane` and move-task both call it. The opener rule matches the review range's `base_opener`. The code fails closed. T025 uses `is_shared_checkout`. The ADR amendment is Proposed and lists its residuals. Moving `mission_evidence_report` onto `consolidation_events` changes no verdict, because the evidence axis reads no window stamp. ruff, format, mypy and C901 are clean. Targeted suites: 3668 passed; the only 2 failures are the known WP03/WP05 integration reds.

Two findings remain. Both are small, but they need to be folded in before approval.

## 1. The in-flight addendum states a cause and an ownership it cannot know (low)

- **Where:** `src/specify_cli/consolidation/wp_evidence.py`, `target_only_evidence_addendum` (the returned string, around diff lines 342-347 of `f9ef5a6b`).
- **Problem:** The probe lists every target-only commit in `merge-base(pin, target)..target` that touches a path matching the work package's `owned_files`. Such a commit can be unrelated work: another Mission landing on the target, or a hotfix that edits the same doc. The text still states, as fact:
  - "Its owned change was found ..." (this work package's change);
  - "(committed there under the guidance before #7860)" (the cause);
  - and it then tells the operator to cherry-pick the commits.

  This module's own rule (`_lane_branches_absent_locally` / `absent_lane_window_cause`) is to state a shape as a possibility, never as a finding. Contract C2 only asks for "found on the target branch only: `<sha…>`".
- **Required fix:**
  - Word the addendum as a possibility, for example: "Changes to its owned_files were found on the target branch only: <shas>. If they are this work package's work (for example committed there under the guidance before #7860), cherry-pick them onto the Mission branch <branch> (in its coordination worktree), then re-run; or, if <WP> owes no implementation, record that with `--attest-no-implementation <WP> --attest-reason "<why>"` on `spec-kitty accept` or `spec-kitty consolidate`."
  - Keep the literal "found on the target branch only: <sha>" that the tests and contract C2 assert.
  - Adjust the test assertions in `tests/consolidation/test_planning_evidence_window_7860.py` and `tests/specify_cli/cli/commands/agent/test_move_task_planning_evidence_7860.py` only if they pin the old wording.

## 2. move-task's planning-window refusal gives no next step for most causes (low)

- **Where:** `src/specify_cli/cli/commands/agent/tasks_move_task.py`, `_mt_planning_window` (the `ActionContextError` built from `PlanningWindowUnresolved`).
- **Problem:** The message ends with "...cannot be computed: {detail}, so its implementation cannot be verified." Only the `ClaimCommitUnresolved` detail carries a remedy ("commit its status events on the Mission branch ..., then re-run"). Three causes end with no remedy:
  - no recorded opener ("no window-opening (claim) status event is recorded for WP02");
  - an unreadable status log;
  - an unreadable `meta.json` or write ref.

  Every other move-task evidence refusal in this function names its next step (for example "Run `spec-kitty agent mission finalize-tasks` ..., then retry"). On consolidate and accept the same codes get `_RECOVERY`; move-task does not.
- **Required fix:**
  - Append a remedy chosen by code. For `EVIDENCE_WINDOW_UNCOMPUTABLE`: the planning sentence now in `_RECOVERY[EVIDENCE_WINDOW_UNCOMPUTABLE]` (claim it through `spec-kitty agent action implement`, whose status commit lands on the Mission branch, then retry). For `IMPLEMENTATION_UNREADABLE`: make `meta.json`, the status log or the Mission branch readable, then retry.
  - Reuse one constant shared with `_RECOVERY` rather than a third copy of the wording.
  - Add a unit assertion in `test_an_unprovable_planning_window_refuses` that the refusal names its next step.
