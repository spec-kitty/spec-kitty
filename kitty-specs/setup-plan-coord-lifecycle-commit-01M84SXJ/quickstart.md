# Quickstart: see the fix work

1. In a scratch repository, create a coordination Mission: `spec-kitty agent mission create demo --mission-type software-dev --topology lanes_with_coord ... --json`.
2. Write a substantive `spec.md` and commit it with `spec-kitty spec-commit`.
3. Run `spec-kitty agent mission setup-plan --mission <handle> --json`, populate the plan's Technical Context, run it again.
4. Check:
   - `git status --porcelain` in the repository root checkout and in `.worktrees/<slug>-coord` shows no change to the Mission's `status.events.jsonl` (before the fix the coordination worktree showed it modified).
   - `git -C .worktrees/<slug>-coord log -1 -- kitty-specs/<slug>/status.events.jsonl` shows the lifecycle commit, and the log holds `SpecifyCompleted`, `PlanStarted` and `PlanCompleted`.
   - The JSON result carries `lifecycle_commit`.
5. On a repository with old stranded events, `spec-kitty doctor coordination --json` warns `COORDINATION_WORKTREE_DIRTY` for each affected coordination worktree and exits 0.
