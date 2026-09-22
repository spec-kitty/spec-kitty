# Tracer — Tooling Friction (verdict-matrix RMW preservation)

Append friction encountered with tooling/workflow. Seeded at planning.

- **Two-missions-one-clone collision (major).** The brief pointed Mission B at `spec-kitty_TWO`,
  but a concurrent Mission A was already live there. Spec Kitty planning (specify/plan/tasks) runs
  in the repo ROOT checkout, not a worktree, so both missions fought over `HEAD`; Mission A's
  branch got checked out mid-specify and a Mission-B commit landed on Mission A's branch. Lesson:
  each concurrent mission needs its OWN clone; confirm the clone is unoccupied before `mission
  create`. Recovery: operator reassigned this mission to `spec-kitty_THREE` (a separate clone).
- **Shell cwd resets between Bash calls** to the session launch dir. Mitigation: prefix every
  command with `cd <clone> &&`; use `git -C <clone>` for git.
- **Upstream remote is named `skupstream`** in THREE (not `upstream` as in TWO). Fetch/rebase
  target is `skupstream/main`.
- **Global `spec-kitty` shim is 4.0.0rc4** (pyenv). THREE's `.venv` is editable-installed to
  THREE's own `src/specify_cli`, so `.venv/bin/python -m pytest` exercises the fix directly; watch
  the CLAUDE.md stale-install gotcha only for paths that shell out to the global `spec-kitty`.

## Implementation phase friction (2026-09-22)

- **opus session rate-limit mid-dispatch.** Both first-wave implementer subagents (opus) died
  with HTTP 429 "session limit" partway through. WP02 had already committed test+fix; WP01 was
  still writing the red-first test (uncommitted partial, discarded on resume). Recovery: re-dispatch
  on **sonnet**. Lesson: for long parallel implement waves, prefer sonnet implementers or stagger
  to avoid exhausting the opus session budget; the orchestrator (also opus) must watch its own budget.
- **Claim-step writes `base_commit` metadata into `kitty-specs/` ON THE LANE BRANCH, which the
  review-gate then refuses.** `spec-kitty agent action implement` auto-commits base_branch/
  base_commit/created_at into the WP file (on the lane branch); `move-task --to for_review` then
  refuses with "kitty-specs/ changes are not allowed on lane branches." Worse, the gate's suggested
  remediation `git restore --source <planning-branch> --staged --worktree -- kitty-specs/` is
  UNSAFE at directory scope — it wholesale-replaces the lane's kitty-specs tree (deletes
  issue-matrix.json/acceptance-matrix.json, re-adds planning files). Safe fix: scope the restore to
  the single offending WP file only (verify the diff is exactly the metadata lines), commit as a
  cleanup, retry move-task. **Upstream gap to file** (with the WP02 finisher's repro).
- **Worktrees have no own `.venv`.** Tests in a lane worktree must run as
  `PYTHONPATH="$PWD/src" <main>/.venv/bin/python -m pytest ...` or they silently import the MAIN
  checkout's (unfixed) editable source. Verify import resolution before trusting results.
