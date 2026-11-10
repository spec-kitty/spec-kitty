# Tooling friction trace: docsite-publication-llms-parity-01M70Z7A

Append-only, newest last.

- 2026-11-10 — **Rebasing a finalized single_branch Mission orphans `lanes.json`'s `planning_commit_sha`.** After #7486 merged, the orchestrator rebased the mission branch onto main (`git rebase --onto origin/main 0ebc12fc`) and moved the target branch to main. `implement` then refused the WP01 re-claim (orphaned planning commit), and both `finalize-tasks --refresh-planning-commit` and `... --allow-orphaned` refused (`PLANNING_REFRESH_FAIL_CLOSED`: "lanes.json does not resolve to the planning target branch"). The refresh path does not handle a single_branch Mission on its own topic branch. Workaround: the implementer re-claimed with `move-task`; the orchestrator hand-corrected `planning_commit_sha` to the target tip (136d38ca), the manual remedy the CLI's help names. Candidate gap.
- 2026-11-10 — The pre-review regression gate printed "no changed files detected for this WP" and skipped its check on both WP01 review cycles, although WP01 changes many files. Reviewers did not treat it as evidence. Candidate gap.
- 2026-11-10 — CLI-made commits (status transitions, review records) are unsigned, as in docsite-shared-build-01M70V33; the landing branch is compacted into signed commits.
