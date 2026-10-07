# Tooling friction

Context: a P0 fix to `upgrade` and the mission-state repair. Record CLI, test-harness and gate friction here as it happens.

- 2026-10-06: `.venv/bin/spec-kitty` had a stale shebang pointing at a deleted isolation worktree; fixed with `uv sync --reinstall-package spec-kitty-cli`.
- 2026-10-06: `agent mission create` on a non-primary topic branch resolved to `coord` topology (no `origin/HEAD`); expected `lanes`.
- 2026-10-07: `spec-kitty consolidate` crashed mid-run with `ImportError: cannot import name 'is_mission_dir'`. Cause: the CLI's editable install runs from the repository root checkout that consolidation lands the merged code into. The birth-cutover phase lazily imported the new `mission_state.py` against an already-imported old `mission_resolver.py`. It rolled back cleanly. Worked around by running consolidate from a frozen `git archive` of `src/` and `packs/` (`PYTHONPATH=<copy>/src`). This is a self-hosting hazard; file upstream.
- 2026-10-07: default squash consolidate refused with "projected coordination bookkeeping content did not land on the target", which matches #5552 even though #5552 is closed. Worked around with abort, re-adding the coord worktree, and `--strategy merge`. File upstream.
- 2026-10-07: the plan auto-commit message says "Add plan for feature …" (terminology canon drift in the CLI).
- 2026-10-07: review and status verdicts are written uncommitted on coord (`--no-auto-commit`), so each one needed a manual commit in the coord worktree.
- 2026-10-07: the reviewer's `move-task --agent claude-reviewer` was refused with "Agent mismatch". The orchestrator relayed it with the review-claim identity `claude`.
- 2026-10-07: `scripts/docs/build_cli_reference.py` hardcodes `uv run`, so a scratch shim pointing at `.venv/bin` was needed.
