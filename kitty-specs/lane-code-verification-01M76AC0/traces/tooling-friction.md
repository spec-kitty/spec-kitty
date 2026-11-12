# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-11 · claude-orchestrator · **[2026-11-11][setup] Global spec-kitty shim pointed at /opt/spec-kitty, not this checkout.** The preinstalled uv-tool CLI imported specify_cli from /opt/spec-kitty/src; reinstalled with `uv tool install --force --editable .` so the CLI runs this checkout. This is the M3a mechanism of #7554 hitting this very mission; disposition: workaround, in scope.

2026-11-12 · claude-orchestrator · **[2026-11-12][specify] `agent decision open/resolve` writes decision files and status events but does not commit them, and leaves an untracked `decisions/index.json.lock`.** Committed the records by hand and left the lock untracked; the lock is the subject of open PR #7561 (#7549). Disposition: workaround, tracked upstream.

2026-11-12 · claude-orchestrator · **[2026-11-12][tasks] check-prerequisites reported branch_matches_target=false on the default Mission topic branch, and finalize-tasks then switched the repository root checkout back to the create-return branch.** Both are the documented size-default topology flow (ADR 2026-11-06-3), but the tasks prompt tells the agent to stop on a false branch_matches_target; candidate gap in the prompt wording. Also: CLI-made commits carry no Co-Authored-By trailer, so history compaction must add it.

2026-11-12 · claude-orchestrator · **[2026-11-12][tasks] After topology settlement, spec-commit resolves the planning surface to the mission branch but places it at the repository root checkout, then refuses ('Artifact(s) not present at resolved placement').** The mission branch is checked out in the coordination worktree, so the canonical spec-commit cannot amend the spec after finalize-tasks; committed with git in the coordination worktree. Also: agent action implement left vcs-lock and WP base stamps staged but uncommitted there (#7545 class). Candidate gap.

2026-11-12 · claude-orchestrator · **[2026-11-12][implement] Implement claims made with only --agent claude record tool=claude and no profile/model, so a reviewer on the same tool cannot prove independence (REVIEW_NOT_INDEPENDENT risk).** The reviewer claims as a distinct agent instance (claude-reviewer, profile reviewer-renata); later implementers pass --profile. Disposition: workaround.

2026-11-12 · wp06-implementer · **[2026-11-12][implement] Lane warnings have no shared channel.** open_lane_checkout has no console, and the allocator's own warnings are bare print(file=sys.stderr); the packs remedy line follows that convention because the implement command (WP02-owned) offers no warning sink. Also: charter.packs is mypy follow_imports=skip, so names imported from it read as Any and needed explicit str() returns.

2026-11-12 · wp06-implementer · **[2026-11-12][implement] Erratic pytest wall-clock in the lane.** The same 12-test selection ran in 5.5 s once and 100+ s (mostly CPU, outside test calls) on other runs, likely contention with the concurrent lane-a implementer; the test calls themselves take ~1.5 s each.

2026-11-12 · claude-orchestrator · **[2026-11-12][implement] Correction: the 'CLI left writes uncommitted' entries above are this repository's own setting, not CLI bugs.** .kittify/config.yaml sets auto_commit: false, so claims, finalize, approvals and review cycles stay uncommitted by design; the orchestrator commits the coordination worktree after each step. The spec-commit placement refusal after settlement stands as a separate candidate gap.
