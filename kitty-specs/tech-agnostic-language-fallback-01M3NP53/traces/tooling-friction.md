# Tooling friction — tech-agnostic-language-fallback-01M3NP53

Tooling touched: `spec-kitty agent mission create --topology lanes`, charter generate/context, `spec-kitty review`, decision moments, issue-verdict.

- 2026-09-29 — Container restart left HEAD detached and local `main` pointing at a pre-rewrite upstream history (origin/main had been force-updated). Resetting local `main` was refused by the environment's safety classifier, so the mission targets the topic branch `issue-5283-tech-agnostic-language-fallback` (cut from origin/main) instead of local `main`. `branch-context` correctly refused the detached HEAD.
- 2026-09-29 — `mission create` scaffold commit message still says "Add scaffold for feature …" (terminology canon: Mission, not feature).
- 2026-09-29 — `setup-plan` auto-commits plan.md with the message "Add plan for feature …" (terminology canon drift again); research/data-model/contracts/quickstart needed a separate `spec-commit`.
- 2026-09-29 — `spec-kitty review`'s neutrality lint does not scan Python string constants, ERROR_CODES.md or docs/, so consumer-facing advisory text has no automated neutrality guard; explicit tests needed.
- 2026-09-29 — `finalize-tasks` preserves existing WP frontmatter `dependencies` instead of re-parsing tasks.md, so a dependency added to tasks.md after the first finalize needed a manual frontmatter edit before re-running finalize.
- 2026-09-29 — The generic-artifact language-bias test exempts any file containing the substring `applies_to_languages:`, which incentivised scoping language-independent tactics to silence it (fixed in WP07).
- 2026-09-29 — finalize-tasks flags WP01 as post-integration-only because tests use the CLI flag `--mode post-merge` (keyword false positive).
- 2026-09-29 — `spec-kitty doctrine regenerate-graph` prints a deprecation warning pointing at `charter` while CLAUDE.md/charter still prescribe `spec-kitty doctrine regenerate-graph`; ~25 s setup per doctrine test module.
- 2026-09-29 — `glossary-curation-interview.tactic.yaml` still carries spec-kitty `src/specify_cli/` paths in a shipped pack (baselined repo_paths: 3) — out of scope, candidate follow-up.
- 2026-09-29 — real-git review tests take ~100 s under xdist; `-n0` faster. Two touched files (language_scope.py, test_dead_code_baseline_git.py) are already unformatted on main although CI runs whole-repo `ruff format --check`.
- 2026-09-29 — first pytest run in a lane worktree spends 70–100 s in setup (foreground timeouts); run in background and poll.
- 2026-09-29 — reviewers' approve transitions were refused by the issue-matrix gate because in-mission rows had empty evidence_ref (issue-verdict accepts in-mission without --evidence-ref, move-task --to approved then refuses it); also move-task writes review-cycle records with --no-auto-commit, blocking the NEXT WP's approval until committed. Follow-up filed for glossary-curation-interview in-house paths: #5341.
- 2026-09-29 — pre-existing red on main found during WP02 review: single-reader gate for catalog.mission fails on m_4_0_0rc5 migration → filed #5342.
- 2026-09-29 — lane pytest cold runs 70–180 s; the out-of-map edit triggered an ACTIVE_WP_SCOPE_VIOLATION warning (advisory only).
- 2026-09-29 — CLI tests that run `charter generate` in-process fail from a lane worktree unless they chdir into the tmp project: the linked-worktree write-root guard ("Refusing charter write from linked git worktree") fires first; existing test_charter_cli.py tests hit it when run from a lane.
- 2026-09-29 — WP05 CLI fixtures cost ~40 s each (new test file ~4 min).
- 2026-09-29 — docs tooling: scripts/docs/docs_index.py needs PYTHONPATH=$PWD (else "No module named scripts"); inventory_lockfile.py --write needs a path argument; the freshness gate errors until new pages are in docs/development/3-2-page-inventory.yaml.
- 2026-09-29 — acceptance-matrix.json is generated once from the FRs at that moment; FR-018 (added after tasks) cannot receive an acceptance verdict ("Unknown criterion") and there is no CLI to add a criterion; FR-018 evidence lives in WP07's approved review.
- 2026-09-29 — consolidate: the planning lane (== target branch) was stale; the CLI-prescribed 'git merge kitty/mission-…' into the target then made the squash reconciliation gate fail closed (empty authorship sets) after all WPs were recorded done; teardown skipped, lane worktrees retained. Matches open #5296 (comment added with repro).
