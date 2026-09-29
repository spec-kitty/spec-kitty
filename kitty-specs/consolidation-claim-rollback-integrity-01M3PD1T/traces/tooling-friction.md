# Tooling friction — consolidation-claim-rollback-integrity-01M3PD1T

Tooling touched: `spec-kitty consolidate` (executor claim/rollback/teardown), `spec-kitty agent action implement` (planning-lane self-heal), terminus test fixtures (`tests/terminus/conftest.py`).

- 2026-09-29 — Container restart left HEAD detached; `spec-kitty agent mission branch-context` refuses on a detached HEAD ("Must be on a branch"), so the specify preflight needs a manual `git checkout -B main origin/main` first.
- 2026-09-29 — `spec-kitty spec-commit` rejects a directory argument (`decisions/`); every Decision Moment file must be listed individually (`find … -type f`).
- 2026-09-29 — No LANES-topology (no coordination branch) fixture exists in `tests/terminus/conftest.py`; the grounding repros used `build_coord_mission`, so #5296/LANES behaviour of #5318 is only code-read, not reproduced.
- 2026-09-29 — A grounding subagent placed a scratch repro under `tests/terminus/` to reuse conftest fixtures; that tripped the stop-hook "untracked files" check. Scratch repros belong in the scratchpad (import fixtures via `tests.terminus.conftest`).
- 2026-09-29 — `spec-kitty agent action implement` wrote `vcs`/`vcs_locked_at` into `meta.json` on the planning branch but did not commit them; the stop hook then flags the tree dirty. The `analysis_report_required` gate also went stale after the post-tasks folds, so `record-analysis` had to be re-run.
- 2026-09-29 — A container restart killed the WP03 and WP05 implementers mid-work. Their red-first commits survived; the uncommitted edits were saved as `wip:` commits, and both implementers were re-dispatched to resume and squash. Lesson: implementers should commit at each subtask boundary, not only at the end.
