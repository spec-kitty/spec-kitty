# Git Operations Matrix

Complete matrix of every git command spec-kitty executes and every git
command agents are expected to run.

## Python-Executed Git Commands

| Command | When | Source File | Function |
|---|---|---|---|
| `git branch <mission-branch> <target-branch>` | First lane allocation for a feature | `lanes/worktree_allocator.py` | `_ensure_mission_branch()` |
| `git worktree add -b <lane-branch> <path> <mission-branch>` | `spec-kitty implement WP##` when lane worktree missing | `lanes/worktree_allocator.py` | `_create_lane_worktree()` |
| `safe_commit(paths=["kitty-specs/<mission>/"])` | Before worktree creation (auto-commit) | `cli/commands/implement.py`, `git/commit_helpers.py` | `BookkeepingTransaction` / `safe_commit()` |
| `git stash` | Lane transition safe-commit | `git/commit_helpers.py` | `safe_commit()` |
| `git add <wp-file>` | Lane transition safe-commit | `git/commit_helpers.py` | `safe_commit()` |
| `git commit -m "chore: Start WP##..."` | Lane transition safe-commit | `git/commit_helpers.py` | `safe_commit()` |
| `git stash pop` | Lane transition safe-commit | `git/commit_helpers.py` | `safe_commit()` |
| `git worktree add --detach <path> <target-branch>` | Target-branch merge workspace creation | `lanes/consolidation.py` | `_merge_refs_detached()` |
| `git merge --no-ff <lane-branch>` | Lane merged into mission branch | `lanes/consolidation.py` | `merge_lane_into_mission()` |
| `git merge --no-ff <mission-branch>` | Mission merged into target branch | `lanes/consolidation.py` | `_merge_refs_detached()` |
| `git update-ref refs/heads/<target> <sha>` | Advance target branch to detached merge result | `lanes/consolidation.py` | `_merge_refs_detached()` |
| `git push origin <target>` | Merge execution (opt-in `--push`) | `cli/commands/consolidate.py` | `merge_command()` |
| `git worktree remove <path> --force` | After successful merge | `cli/commands/consolidate.py` | `_cleanup_merged_lanes()` |
| `git branch -d <lane-branch>` | After successful merge | `cli/commands/consolidate.py` | `_cleanup_merged_lanes()` |
| `git branch -d <mission-branch>` | After successful merge | `cli/commands/consolidate.py` | `_cleanup_merged_lanes()` |
| `git rev-list --count <base>..HEAD` | Topology analysis (read-only) | `core/worktree_topology.py` | `_count_commits_ahead()` |
| `git worktree list` | Worktree discovery | `core/worktree_topology.py` | `discover_worktrees()` |
| `git rev-parse --show-toplevel` | Repo root detection | Multiple files | Various |
| `git branch --show-current` | Branch detection | `core/git_ops.py` | `get_current_branch()` |
| (branch name → mission slug) | Branch-based mission-slug detection | `lanes/branch_naming.py` | `parse_mission_slug_from_branch()` |

## Agent-Expected Git Commands

| Command | When | Why |
|---|---|---|
| `git add <files>` | After writing implementation code | Stage deliverables |
| `git commit -m "feat(WP##): ..."` | After implementation work | Record changes |
| `git rebase <mission-branch>` | When the lane is stale relative to the mission branch | Resync the lane before review or merge |
| `git add . && git rebase --continue` | During rebase conflict resolution | Complete rebase |
| `git push origin <branch>` | When explicitly asked by user | Publish changes |

## Operations Nobody Should Do

| Anti-Pattern | Why Not |
|---|---|
| `git worktree add` (manual) | No workspace context, wrong lane assignment, wrong branch naming |
| `git commit` in repository root checkout during implementation | Implementation belongs in worktree |
| `git push` without user request | Never auto-push |
| `git checkout` in worktree to another branch | Breaks worktree isolation |
| Edit `.git/hooks/` | Spec Kitty owns scoped commit-guard hooks; repair through CLI |
| `git reset --hard` in worktree | Destroys agent work without recovery |
