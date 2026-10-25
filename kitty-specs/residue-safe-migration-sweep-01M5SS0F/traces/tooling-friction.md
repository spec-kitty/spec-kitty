# Tooling friction: residue-safe-migration-sweep-01M5SS0F

- **[2026-10-25][plan] Clean-source tests need a committed tree.** `tests/upgrade/test_upgrade_cli_contract.py` and the preview acceptance suites refuse with "Baseline source is dirty" while a mission edit is uncommitted. Commit or stash before running them. Disposition: workaround, known.
- **[2026-10-25][plan] Shallow clone reds.** `tests/upgrade/test_mission_corpus_recovery.py` needs historical commit `c0054153`, which the session's shallow clone lacks (exit 128). It is red on `origin/main` too. Disposition: environmental, not chased.
- **[2026-10-25][plan] Agent command copies absent.** This checkout has no generated `.claude/commands/`, so planning runs through the published `spec-kitty.*` skills. Disposition: works, no gap.
