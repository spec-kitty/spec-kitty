# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-11 · claude-orchestrator · **[2026-11-11][setup] Global spec-kitty shim pointed at /opt/spec-kitty, not this checkout.** The preinstalled uv-tool CLI imported specify_cli from /opt/spec-kitty/src; reinstalled with `uv tool install --force --editable .` so the CLI runs this checkout. This is the M3a mechanism of #7554 hitting this very mission; disposition: workaround, in scope.

2026-11-12 · claude-orchestrator · **[2026-11-12][specify] `agent decision open/resolve` writes decision files and status events but does not commit them, and leaves an untracked `decisions/index.json.lock`.** Committed the records by hand and left the lock untracked; the lock is the subject of open PR #7561 (#7549). Disposition: workaround, tracked upstream.

2026-11-12 · claude-orchestrator · **[2026-11-12][tasks] check-prerequisites reported branch_matches_target=false on the default Mission topic branch, and finalize-tasks then switched the repository root checkout back to the create-return branch.** Both are the documented size-default topology flow (ADR 2026-11-06-3), but the tasks prompt tells the agent to stop on a false branch_matches_target; candidate gap in the prompt wording. Also: CLI-made commits carry no Co-Authored-By trailer, so history compaction must add it.

2026-11-12 · claude-orchestrator · **[2026-11-12][tasks] After topology settlement, spec-commit resolves the planning surface to the mission branch but places it at the repository root checkout, then refuses ('Artifact(s) not present at resolved placement').** The mission branch is checked out in the coordination worktree, so the canonical spec-commit cannot amend the spec after finalize-tasks; committed with git in the coordination worktree. Also: agent action implement left vcs-lock and WP base stamps staged but uncommitted there (#7545 class). Candidate gap.
