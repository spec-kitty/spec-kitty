# Tooling friction — upgrade-project-global-state-01M44538

Tooling touched: `spec-kitty upgrade` (runner + autocommit), `consolidate` (stale check, squash gate), lane auto-rebase / lifecycle sync, the conflict classifier, the state contract.

- 2026-10-04 — `spec-kitty` was not on PATH in the cloud container even after `uv sync`; linked `.venv/bin/spec-kitty` into a PATH dir. `~/.local/bin` is not on PATH here.
- 2026-10-04 — `spec-kitty spec-commit` requires `-m`; the specify prompt does not show the flag. It also commits `decisions/index.json.lock` (tracked by convention in other missions).
- 2026-10-04 — Git history in the container is grafted to 50 commits, so `git log -S` cannot reach #2385/#2392/#4972 provenance; lenses relied on CHANGELOG and in-code citations.
- 2026-10-04 — WP01: the repo `.venv` is installed editable from the repository root checkout, so tests run inside a lane worktree import root `src/` unless `PYTHONPATH=src` is set. The first `run_cli` use builds `.pytest_cache/spec-kitty-test-venv` (~80-140 s); `-p no:cacheprovider` forces a rebuild every run.
- 2026-10-04 — WP01: `test_no_dead_symbols.py` flags a new public predicate before its consumers land in later WPs; cross-WP sequencing and the dead-symbol gate pull against each other.
- 2026-10-04 — WP01: `move-task --note` left a note event uncommitted in status.events.jsonl/status.json on the planning branch (no status commit for the note delta).
- 2026-10-04 — Orchestrator: a commit in the repository root checkout racing a subagent's `implement` claim swept the CLI's staged status events into an unrelated commit; the CLI then rolled its working copy back, leaving the working tree a strict prefix of HEAD. Restored the two status files path-scoped from HEAD. Rule adopted: no root-checkout commits while a subagent runs status commands.
- 2026-10-04 — WP01 approval refused twice by the issue-matrix gate: rows are auto-extracted from every bare #NNN cite (including false #10/#15) and default to `unknown`; record verdicts for all cites before the first approval.
- 2026-10-04 — `move-task` approvals are written with `--no-auto-commit` and leave status files + review-cycle verdicts uncommitted in the repository root checkout; the orchestrator committed each via `spec-kitty safe-commit` once no other agent was mid-transition.
- 2026-10-04 — 47 `tests/upgrade` preview/contract tests hard-code `<cwd>/.venv/bin/python`, so they are red whenever run from a lane worktree (identical on base; tracked by #5096).
- 2026-10-04 — Lane worktrees import the repository root checkout's `src/` through the editable install unless `PYTHONPATH=src` is set (also #5096 territory).
