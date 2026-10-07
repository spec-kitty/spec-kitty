# Tooling friction — second-clone origin reconciliation (#5780, #5758, #5759)

- 2026-10-06: Setup used `uv sync --frozen --all-extras` (editable install into `.venv`) instead of a bare `pip install -e .`; same effect, matches the repo's own dev-setup.
- 2026-10-06: `spec-kitty charter context --action plan` from the repo root prints a `CharterCatalogMissWarning` for `toolguide:typescript-mutation-tools` (scope_filtered) on every call. Noise, not a blocker.
- 2026-10-06: Parallel lane agents contend for the repository-root `.git/index.lock` when lifecycle commands auto-commit status; orchestrator commits had to wait/retry.
- 2026-10-06: Lane worktrees have no `.venv`; tests that hard-code `<repo>/.venv/bin/python` (upgrade preview oracle) fail there — environment-only reds that cost review time to classify.
- 2026-10-06: `move-task`/`agent action review` print "verdict written but NOT committed (--no-auto-commit)" even when the flag was not passed; the orchestrator commits status by hand.
- 2026-10-06: One lane agent's broad `pkill -f pytest` killed another lane's run; dispatch prompts now forbid broad pkill patterns.
- 2026-10-06: Subagents re-sent completion reports repeatedly while background jobs were alive (needed explicit stand-down messages).
- 2026-10-06: The post-merge stale-assertion analyzer flagged 27 test files on string literals moved by the refactor; all 426 tests passed (false positives).
