# Quickstart: verify next lifecycle integrity

1. **Finished board, not accepted:** `spec-kitty next --agent claude --mission <h> --result success --json`.
   - Expect `kind=blocked`, `error_code=MISSION_AWAITING_ACCEPTANCE`, and `next_command` set to the accept command.
   - Expect no new `NextStepIssued` rows in `.kittify/runtime/runs/*/run.events.jsonl`.
2. **After `spec-kitty accept`:** the same call returns `kind=terminal`, and repeated calls write no step rows.
3. **Fresh Mission:** `spec-kitty next --agent claude --mission <h> --json`. Expect `next_command` to be `spec-kitty next --agent claude --mission <h> --result success`, and `question` to be null.
4. **Narrowed rejection:** `spec-kitty agent tasks move-task WP01 --to planned --reset-subtasks T002 --note "T002 regressed" --review-feedback-file fb.md`.
   - Expect T001 to stay done.
   - Expect `rollback_reset.scope=narrowed` on the PLANNED event.
