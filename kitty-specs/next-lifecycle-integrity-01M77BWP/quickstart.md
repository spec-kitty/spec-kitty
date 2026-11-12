# Quickstart: verify next lifecycle integrity

1. **Finished board, not accepted:** `spec-kitty next --agent claude --mission <h> --result success --json`.
   - Expect `kind=blocked`, `error_code=MISSION_AWAITING_ACCEPTANCE`, and `next_command` set to the accept command.
   - Expect no new `NextStepIssued` rows in `.kittify/runtime/runs/*/run.events.jsonl`.
2. **After `spec-kitty accept`:** the same call returns `kind=terminal`, and repeated calls write no step rows.
3. **Fresh Mission:** `spec-kitty next --agent claude --mission <h> --json`. Expect `next_command` to be `spec-kitty next --agent claude --mission <h> --result success`, and `question` to be null.
4. **Narrowed rejection:** `spec-kitty agent tasks move-task WP01 --to planned --reset-subtasks T002 --note "T002 regressed" --review-feedback-file fb.md`.
   - Expect T001 to stay done.
   - Expect `rollback_reset.scope=narrowed` on the PLANNED event.
5. **Mid-implementation board (FR-016):** with a WP `in_progress` (or `claimed`) and a stale planning run, `spec-kitty next --agent claude --mission <h> --result success --json`.
   - Expect `kind=blocked`, `error_code=BOARD_STEP_NOT_DISPATCHABLE`, and `next_command` set to `spec-kitty agent action implement <WP> --agent claude --mission <h>`.
   - Expect the stale run to stay where it was and no new step rows.
6. **Acceptance freshness:** accept the Mission, then reopen a WP and approve it again.
   - Expect the next advance to return `kind=blocked` with `MISSION_AWAITING_ACCEPTANCE` again (the acceptance is older than the board's latest transition).
   - After a new `spec-kitty accept`, expect `kind=terminal`.
7. **Missing `lanes.json`:** delete `kitty-specs/<h>/lanes.json` on a finalized board, then advance.
   - Expect `kind=blocked`, `error_code=LANES_MANIFEST_MISSING`, the error's own message in `reason`, and no run started.
   - Expect `next_command` to be `spec-kitty agent mission finalize-tasks --mission <h>` while every WP is `planned`, and `spec-kitty doctor mission-state --fix --mission <h>` once any WP has left `planned`.
