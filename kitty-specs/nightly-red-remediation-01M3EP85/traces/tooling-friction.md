# Tooling Friction Log

> Log every place the tooling fought you so it can feed the tooling-gap backlog.

**Prompting questions**
- What tooling or command did you have to work around?
- What blocked you unexpectedly, and how long did it take to unblock?
- Was this a known issue or something discovered fresh?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what happened, why it slowed you down. -->

> **Honesty note:** these tracer files were seeded late, at closeout (2026-09-26), rather than at mission start. The entries were reconstructed from the session record and carry the time each event occurred. This is the procedure's "retroactive fill-in" anti-pattern, recorded here as the first friction item.

- 2026-09-26 — Tracer files were not seeded at specify/plan. Nothing in the specify, plan or tasks prompts reminds the agent to do it; the step only lives in the charter standing orders.
- 2026-09-26 — `move-task --to approved` reports "review-cycle verdict written but NOT committed (--no-auto-commit)" even when that flag was never passed. Every approval therefore needed a manual commit of `status.events.jsonl`, `status.json` and `review-cycle-1.md` on the planning branch.
- 2026-09-26 — spec-kitty bookkeeping commits use `git -c commit.gpgsign=false` (`src/specify_cli/git/commit_helpers.py:875`). In a signing-required harness, every batch of status commits had to be re-signed before pushing.
- 2026-09-26 — The issue-matrix approve gate refused WP01 twice. The first refusal was for all rows still `unknown`; the second was for #1718, which only appeared in a test docstring. Citing an issue number anywhere, including test docstrings, creates a gating row.
- 2026-09-26 — A `single_branch` topology still allocated one lane worktree per WP (5 worktrees). This matches the open issue #5100.
- 2026-09-26 — Running tests from a lane worktree against the shared `.venv` (editable install of the main checkout) needs `PYTHONPATH=<worktree>/src`. The WP03 reviewer found that pointing PYTHONPATH at the base src did **not** switch the code under test, so it used a detached base worktree for red-first proof.
