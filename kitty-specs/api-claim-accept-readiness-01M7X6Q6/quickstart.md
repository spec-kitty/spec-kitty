# Quickstart: verifying the fix

1. Drive a Mission through `orchestrator-api`: `start-implementation --actor claude`, commit in the lane, `transition --to for_review`, `start-review --actor codex`, `transition --to approved`, record the verdict.
2. `spec-kitty orchestrator-api accept-mission --mission <m>` returns `success: true`.
3. Cancel a planned WP: `spec-kitty agent tasks move-task WP02 --to canceled --note "descoped" --mission <m>`. Both `spec-kitty accept` and `accept-mission` pass, and WP02 is listed under `canceled_wps`.
4. `spec-kitty orchestrator-api transition --wp WP01 --to planned ...` on a claimed WP. `spec-kitty agent tasks status` shows no owner, and another agent can claim it without `--force`.
