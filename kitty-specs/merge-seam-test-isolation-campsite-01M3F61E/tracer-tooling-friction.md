# Tooling Friction Log

> Log every place the tooling fought you so it can feed the tooling-gap backlog.

**Prompting questions**
- What tooling or command did you have to work around?
- What blocked you unexpectedly, and how long did it take to unblock?
- Was this a known issue or something discovered fresh?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what happened, why it slowed you down. -->
- 2026-09-26 — `spec-kitty` on PATH (pyenv shim) resolves to a *different* checkout (`fork/spec-kitty`), so `decision open` tracebacked from the wrong source tree; switched to `.venv/bin/spec-kitty` for the whole mission.
- 2026-09-26 — Fresh coord worktree did not self-materialize on the first `decision open` (branch at base head); `doctor workspaces --fix` only clears husks. Materialized via `CoordinationWorkspace.resolve(repo_root, slug, mid8)` (known gap, also seen in ci-coverage-honesty).
- 2026-09-26 — Decision-moment events land in the primary checkout's `status.events.jsonl` + `decisions/` (coord worktree has no mission dir yet); `spec-commit` correctly refuses to carry them, so they wait for the lifecycle-trail commit.
- 2026-09-26 — `mission-tracer-files` procedure still points at `src/doctrine/templates/mission-tracer-files/`; canonical location is `src/charter/offering/templates/mission-tracer-files/` (post doctrine→charter absorption).
- 2026-09-26 — `.kittify/overrides/missions/software-dev/templates/task-prompt-template.md` is stale vs `packs/built-in/.../task-prompt-template.md` (lacks `execution_mode`/`owned_files`/`authoritative_surface`/`create_intent` that finalize-tasks requires); used the built-in.
- 2026-09-26 — Each `spec-kitty implement WPnn` stamps `base_commit` into the WP file and refuses the next `implement` until it is committed (auto-commit disabled) — four lanes needed four interleaved stamp commits; the first refusal also wanted the untracked decision trail force-added.
- 2026-09-26 — `mark-status`/`move-task` intermittently raised `RuntimeError: Global asset input changed: ~/.kittify/cache/slash_commands-assets.json` on first call; a bare retry self-healed (WP05 implementer).
- 2026-09-26 — Approving as a reviewer identity requires the `agent action review WPnn --agent <reviewer>` claim first (for_review→in_review rebinds the assignee); `move-task --to approved --agent claude-reviewer` straight from for_review hits the ownership guard. `--profile reviewer-renata` on the claim still recorded `agent_profile: __resolved_profile_absent__` in the event.
- 2026-09-26 — Approval is mission-gated on every cited `#NNNN` having a verdict: context citations #2633 and #5055 needed `not-applicable` rows before WP05 could be approved. The approval's review-cycle verdict is written but not committed (`--no-auto-commit`): `review-cycle-1.md` lands on the primary checkout, the verdict event on the coord worktree.
- 2026-09-26 — Running CLI-subprocess suites from a lane worktree trips "Refusing charter write from linked git worktree" (3 `test_charter_json_error_contract.py` reds in `make test-fast`) — environmental, not diff.
- 2026-09-26 (WP02) — Pulling a second symbol through an existing import from a `follow_imports="skip"` module (`[[tool.mypy.overrides]] module=["specify_cli.*"]`) makes its return type `Any` under narrow-file `mypy --strict`, surfacing new-looking `no-any-return` on unrelated lines; fix by annotating the receiving local with its concrete type.
- 2026-09-26 (WP02) — A pure call-site edit inside a function body changes its content-anchored `SymbolKey.body_hash`, silently redding `tests/architectural/test_no_dead_symbols.py`; recompute via the gate's own `resolve_symbol_key`/`key_tier` helpers (out-of-map edit, necessary).
- 2026-09-26 (WP02) — `move-task --to for_review` attributes ANY dirty mission-dir file on the primary checkout (here the orchestrator's uncommitted tracer entries) to the moving WP and refuses; orchestrator bookkeeping must be committed before implementers transition.
- 2026-09-26 (WP03) — A subprocess `python -m specify_cli …` under a FRESH `HOME` pays ~13.3 s of cold-install bootstrap (writes 12 agent dirs + `.spec-kitty-cold-install`); a warm HOME costs ~1.16 s. `SPEC_KITTY_NO_UPGRADE_CHECK=1` does not avoid it and `SPEC_KITTY_TEST_MODE=1` made it worse. A session-scoped shared HOME took the goldens file from ~359 s to ~42 s. `pytest-randomly` is absent from the venv.
- 2026-09-26 (WP01) — Concurrent agent sessions race on the global CLI startup cache (`~/.kittify/cache/slash_commands-assets.json`, `ensure_global_agent_commands`): every `spec-kitty` subcommand except `--version` transiently raises `RuntimeError: Global asset input changed`; a plain retry succeeds. Full `tests/architectural/` from a lane took ~22 min.
- 2026-09-26 — `move-task --to for_review` attributes an UNTRACKED sibling review-cycle dir (`tasks/WP09-*/`) to whichever WP is moving (WP10, WP12 both refused). Every review verdict must be committed immediately or it blocks all concurrent transitions.
- 2026-09-26 (WP11) — Committing tracer edits in a lane is refused ("implementation branches must not modify kitty-specs/") and the suggested remediation (`git restore --source <planning> -- kitty-specs/`) silently wipes them; tracer notes must travel via the orchestrator. Also: a `git stash` taken for a race-free baseline and not popped in the same step silently reverted 7 edits for ~40 min until the census gate re-flagged them; zsh does not word-split unquoted `$FILES`.
- 2026-09-26 (orchestrator) — An UNQUOTED heredoc (`<<EOF`) containing backticked command names in prose was command-substituted by zsh: it executed a test path, a bare `agent` (Cursor Agent CLI, stopped at its trust prompt) and aborted a brief append. No repo damage (verified clean `git status`), but always quote heredocs (`<<'EOF'`) whose body mentions commands.
- 2026-09-27 (WP14) — The lane kitty-specs drift gate's printed remediation (`git restore --source <planning> -- kitty-specs/`) is unsafe as a blanket command: it would collapse a lane's `status.events.jsonl` (227 lines of WP01–WP13 history) to planning's copy. WP14 scoped the restore to the four flagged files. (Orchestrator ran the blanket form on lane-k earlier; the coord branch stays authoritative for status, so no data was lost there.)
