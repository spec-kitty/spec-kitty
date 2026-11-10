# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-10 · claude:claude-opus-5-5:planner-priti · **[2026-11-10][plan] Seed: tooling this Mission touches.** status event-log store and sanitiser, the WP task-file locators (core/status), mission metadata loading and glossary conflict listing; gates: archive byte-freeze, dead-symbol, layer rules, meta-decode census. Friction so far: create minted and checked out the Mission branch in the root checkout (expected per ADR 2026-11-06-3), and setup-plan reports that branch, not meta target_branch, as the merge target until landing; disposition: noted, no gap.

2026-11-10 · claude:claude-opus-5-5:planner-priti · **[2026-11-10][tasks] Branch-context helpers disagree before topology settles.** Before finalize-tasks, setup-plan reported branch_matches_target=true (target = Mission branch) while check-prerequisites reported false (target = meta target_branch fix/quick-win-remediation) on the same checkout; the tasks prompt says to stop on false. Proceeded because ADR 2026-11-06-3 puts pre-landing PRIMARY artifacts on the Mission branch; candidate gap: one branch-context authority for both commands.

2026-11-10 · claude:claude-opus-5-5:python-pedro (WP02) · WP02: the lane worktree has no .venv and no packs/built-in tree; tests ran with the root .venv interpreter (pytest.ini pythonpath=src resolves the lane's sources) after scripts/sync_packs.py --pack all in the lane. 'make sync-packs' would have used uv run, creating a second venv.

2026-11-10 · opencode:glm-5.3:python-pedro · **[2026-11-10][implement] WP03 start waited ~1 min on STATUS_LOCK_HELD (sibling WP04 implement held the mission status lock); lane-c worktree needed make sync-packs before any test run (BuiltInPackMissing on first collection, which also minted the lane .venv).**

2026-11-10 · claude:claude-opus-5-5:python-pedro · **[2026-11-10][implement] Fresh lane worktree had no packs or venv.** Importing specify_cli in the lane failed with BuiltInPackMissing until `make sync-packs` ran there (which also built the lane .venv); the root venv cannot stand in because the lane src needs its own packs/built-in sibling.
