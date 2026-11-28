# Quickstart: verify the planning lane write branch

1. Reproduce (red before this Mission, green after):

   ```bash
   PWHEADLESS=1 .venv/bin/python -m pytest tests/integration/test_7860_planning_evidence_window.py -q
   ```

2. Manual check on a scratch repository:
   1. `spec-kitty init`, then commit.
   2. `spec-kitty agent mission create fx --mission-type software-dev ...`, with **no** `--topology`.
   3. Write three code work packages and one `execution_mode: planning_artifact` work package that owns `kitty-specs/<slug>/research/notes.md`.
   4. `spec-kitty agent mission finalize-tasks --mission <slug>`. The Mission settles `lanes_with_coord`.
   5. `spec-kitty agent action implement WP02 --agent you --mission <slug>`. The workspace printed is `.worktrees/<slug>-coord`, and the message names the Mission branch.
   6. Commit the notes file there, then run `spec-kitty agent tasks move-task WP02 --to for_review --mission <slug>`. It succeeds without `--force`.

3. In-flight check: commit the owned file on the target only. `move-task` refuses with `IMPLEMENTATION_MISSING`, names that commit, and gives both remedies.
