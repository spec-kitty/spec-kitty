# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-04 · claude-orchestrator · Seed: the cloud clone was shallow (50 commits), so `git log --since=90.days` under-counted churn as 1 per file until `git fetch --unshallow origin main`.

2026-10-04 · claude-orchestrator · `spec-kitty agent mission create` auto-commits its scaffold as "Add scaffold for feature <slug>". That is "feature" wording in a CLI-authored commit message (Terminology Canon), and the message carries no operator attribution trailer.

2026-10-04 · claude-orchestrator · `spec-kitty spec-commit` refuses a directory argument (`decisions/`); a shell glob (`decisions/*`) works.

2026-10-04 · claude-orchestrator · `spec-kitty agent mission finalize-tasks` commits "Add tasks for feature <slug>" ("feature" wording, no attribution trailer), the same as the create scaffold commit.

2026-10-04 · claude-orchestrator · #5459 hit on every WP. `agent action implement` on a single_branch Mission records no `refs/spec-kitty/wp-base/...` claim base, so `move-task --to for_review` always refuses ("no implementation commit since claim … beyond <no recorded claim base>") even with commits present. Used `--force` with a note naming the commits.

2026-10-04 · claude-orchestrator · #5655 hit: after mark-status / move-task, status.events.jsonl and status.json stay dirty in the repository root checkout and need a manual safe-commit.

2026-10-04 · claude-orchestrator · `move-task --to approved` refuses until every issue-matrix row has a verdict. The auto-classifier marked the two mission issues #5552 and #5298 as `not-applicable` (context-only) and left the context references `unknown`. Fixed by hand with `agent issue-verdict`.

2026-10-04 · claude-orchestrator · The repository conftest costs about 20 s of setup per pytest process, so a single targeted test file takes about 90-120 s. Batch files per invocation.

2026-10-04 · claude-orchestrator · ruff flags S105 ("hardcoded password") on any constant whose name contains TOKEN (`_CONTRACTS_TOKEN`), so it was renamed `_CONTRACTS_ARTIFACT`. The test_no_dead_symbols gate counts a public constant used only inside its own module as dead, so it was made private.
