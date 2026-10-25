# Tooling friction: residue-safe-migration-sweep-01M5SS0F

- **[2026-10-25][plan] Clean-source tests need a committed tree.** `tests/upgrade/test_upgrade_cli_contract.py` and the preview acceptance suites refuse with "Baseline source is dirty" while a mission edit is uncommitted. Commit or stash before running them. Disposition: workaround, known.
- **[2026-10-25][plan] Shallow clone reds.** `tests/upgrade/test_mission_corpus_recovery.py` needs historical commit `c0054153`, which the session's shallow clone lacks (exit 128). It is red on `origin/main` too. Disposition: environmental, not chased.
- **[2026-10-25][plan] Agent command copies absent.** This checkout has no generated `.claude/commands/`, so planning runs through the published `spec-kitty.*` skills. Disposition: works, no gap.
- **[2026-10-25][plan] Tracer files route to the coordination branch.** `spec-commit` sent `traces/*.md` to `kitty/mission-<slug>` (a lifecycle surface) and the rest to the primary branch. The authored copies stayed untracked in the repository root checkout and were removed by hand after a byte-identity check. Disposition: candidate gap. The procedure could say where to author tracer files under coord topology.

## Implement-review loop (2026-10-25)
- `move-task --to for_review` runs `make test-fast` twice (head + baseline worktree); 10-25 min per WP with parallel lanes on one machine. A foreground timeout leaves the CLI child alive; a retry starts a second gate.
- Each pre-review gate commits an unsigned `chore: Capture baseline tests for WPxx` on the planning branch; re-signed by rebase --exec --reset-author after every gate.
- Reviewer verdicts land with --no-auto-commit: status.events.jsonl, status.json and review-cycle-N.md stay uncommitted in the coord worktree until committed by hand.
- Approval was refused on unknown issue-matrix rows (#6668 had been auto-classified not-applicable although WP06 closes it).
- Lane worktrees carry the pre-re-cut tasks/*.md copies; the generated implement prompts are current.
- Pre-review gate reported `source_mismatch` (text baseline vs junit head) without blocking.
