# Tooling friction

Tooling touched: `spec-kitty upgrade`, `doctor skills`, tool-surface effect planner, pack-skill projection.

- 2026-10-06: A research subagent's CLI run regenerated `.kittify/command-skills-manifest.json` in the repo root checkout; discarded. Run CLI repros in a scratch project only.
- 2026-10-06: `spec-commit` refused a directory argument (`decisions/`); it needs explicit file paths.
- 2026-10-06: `setup-plan` scaffolds an untracked `plan.md`, which a stop-hook flagged before plan content existed.
- 2026-10-06: Parallel `implement` claims of WP01/WP03 three seconds apart corrupted the coordination worktree's `status.events.jsonl` working copy and both reported failure while HEAD recorded both claims. Filed #5804.
- 2026-10-06: Every `move-task --to approved` leaves review-cycle files and a metadata event uncommitted (`--no-auto-commit`); the orchestrator commits them via `spec-commit`.
- 2026-10-06: Approval gate refused until every cited issue (incl. context-only #1158, #3334) had a verdict; cite context issues as "see #" in plans to avoid this.
- 2026-10-06: `tests/upgrade/test_mission_corpus_recovery.py` (9) and other upgrade preview tests fail in this shallow cloud clone (`git archive` of a pinned sha); environment-only, red on origin/main too.
- 2026-10-06: Lane worktrees have no `.venv`; implementers needed `PYTHONPATH=<worktree>/src` or pytest.ini's pythonpath to exercise lane code.
