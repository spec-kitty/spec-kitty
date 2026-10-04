# tooling-friction

- 2026-10-04: `agent mission create` auto-committed the scaffold with the message "Add scaffold for feature …". That message lacks the operator's required co-author trailer and uses the retired term "feature". I amended it before pushing.
- The first pytest run in a fresh container spends about 66–95s in a session fixture that builds `.pytest_cache/spec-kitty-test-venv.*` (`pip install -e`). Later runs take under 2s.
- The eacces helpers cover `builtins.open` and `Path` methods only. `sqlite3.connect` opens in C, so the history-db denial goes through `Path.mkdir`, the first filesystem call in `_connect`.
- WP01 status was recorded after the fact on operator instruction: `move-task` planned → claimed → in_progress → for_review.
  - `mark-status` wrote the subtask annotations to the event log but neither committed them nor ticked `tasks.md` (#5655). The boxes were ticked by hand.
  - The `for_review` gate found no implementation commit after the back-dated claim, so the move used `--force`, with a note naming 0ed4b0c2 and 9fdfc733.
  - Every CLI status commit lacked the operator's co-author trailer; they were reworded before pushing.
