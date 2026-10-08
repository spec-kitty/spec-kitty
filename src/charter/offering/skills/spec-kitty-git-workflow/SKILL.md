---
name: spec-kitty-git-workflow
description: >-
  Understand how Spec Kitty manages git: what git operations Python handles
  automatically, what agents must do manually, worktree lifecycle, auto-commit
  behavior, merge execution, and the safe-commit pattern.
  Triggers: "how does spec-kitty use git", "worktree management", "auto-commit",
  "who commits what", "git workflow", "merge workflow", "rebase WPs",
  "worktree cleanup", "safe commit".
  Does NOT handle: runtime loop advancement (use runtime-next),
  setup or repair (use setup-doctor), mission selection (use mission-system).
---

# spec-kitty-git-workflow

Understand the boundary between what spec-kitty's Python code does with git
and what LLM agents are expected to do. This boundary is critical — agents
that try to create worktrees manually or skip implementation commits will
break the workflow.

---

## The Core Boundary

**Python handles infrastructure git** — worktrees, lane commits, merges,
cleanup. **Agents handle content git** — implementation commits, rebases,
conflict resolution.

| Git Operation | Who Does It | When |
|---|---|---|
| `git worktree add` | Python | `spec-kitty implement WP##` |
| `git commit` (planning artifacts) | Python | Before worktree creation |
| `git commit` (lane transitions) | Python | WP moves through claimed/in_progress/for_review/in_review |
| `git commit` (implementation code) | **Agent** | After writing code in worktree |
| `git merge`/auto-rebase (stale lane sync) | Python or **Agent** | When stale checks classify the lane as recoverable |
| `git merge` (lane → mission → target) | Python | `spec-kitty merge` |
| `git push` | Python (opt-in) | `spec-kitty merge --push` only |
| `git push` | **Agent** | Any other push scenario |
| Conflict resolution | **Agent** | During rebase or manual merge |
| `git worktree remove` | Python | After successful merge |
| `git branch -d` (cleanup) | Python | After successful merge |

---

## What Python Does Automatically

### 1. Worktree Creation

When you run `spec-kitty implement WP01`, Python:

```
git worktree add -b kitty/mission-042-mission-lane-a .worktrees/042-mission-lane-a kitty/mission-042-mission
```

It also records the lane workspace context in
`.kittify/workspaces/<feature>-<lane>.json` so later commands resolve the same
lane worktree deterministically.

The agent never creates worktrees. Always use `spec-kitty implement`.

For dependent WPs in the same execution lane:

```
spec-kitty implement WP02
```

This reuses the lane worktree instead of creating a second workspace:

```
# WP02 reuses .worktrees/042-mission-lane-a
```

### 2. Planning Artifact Auto-Commits

Before creating a worktree, Python checks if `kitty-specs/042-mission/` has
uncommitted changes on the primary branch. If so, it commits through
`BookkeepingTransaction` and `safe_commit`:

```
safe_commit(paths=["kitty-specs/042-mission/"], message="chore: Planning artifacts for 042-mission")
```

**Controlled by:** `auto_commit: true` in `.kittify/config.yaml` (default: true).
Can be disabled per-command with `--no-auto-commit`.

### 3. Lane Transition Auto-Commits

When a WP moves to `doing` or `for_review`, Python uses the **safe-commit
pattern** to commit only the WP frontmatter file:

- Moving to doing: `"chore: Start WP01 implementation [claude]"`
- Moving to for_review: `"chore: Start WP01 review [claude]"`

**The safe-commit pattern** prevents accidentally committing agent
work-in-progress:
1. Stash current staging area
2. Stage only the target files (WP frontmatter, status artifacts)
3. Commit
4. Pop stash to restore previous staging

### 4. Status Event Log (No Auto-Commit)

`emit_status_transition()` appends to `status.events.jsonl`, updates
`status.json`, and modifies WP frontmatter — but does **NOT** auto-commit
these files. They accumulate as uncommitted changes until the next lane
transition auto-commit or the agent commits them.

This is by design — status changes happen frequently and committing each
one would create excessive git noise.

### 5. Merge Execution

Run `spec-kitty accept --mission 042-mission` before merge once every WP is
approved. Acceptance is a readiness nudge and artifact check; merge still owns
the final mission-close transition.

`spec-kitty merge --mission 042-mission` runs the full merge sequence:

Python creates a detached merge worktree from the target branch, merges lane
branches into the mission branch, merges the mission ref using the selected
strategy, advances the target branch ref to the detached result, then removes
merged lane worktrees and branches.

Merge order follows the dependency graph (topological sort).

Supports 3 strategies: `squash` (default), `merge` (--no-ff), `rebase`.

`--push` is opt-in — without it, the merge is local only.

### 6. Pre-flight Validation (Read-Only)

Before merge, Python validates:
1. All expected WPs have worktrees
2. All worktrees are clean (`git status --porcelain`)
3. Target branch is not behind origin (`git rev-list --left-right --count`)
4. WPs in done lane with missing worktrees are skipped (already merged)

If any check fails, merge is blocked with specific error messages.

---

## What Agents Must Do

### 1. Implementation Commits

All actual code work must be committed by the agent. Python creates the
worktree but never commits code:

```bash
cd .worktrees/042-mission-lane-a
# ... write code, run tests ...
git add -- src/auth/middleware.py tests/test_auth_middleware.py
git commit -m "feat(WP01): implement auth middleware"
```

**Validation:** When the agent tries to move WP to `for_review`, spec-kitty
checks that the worktree has commits ahead of the base branch
(`git rev-list --count <base>..HEAD`). If zero commits, the transition is
rejected.

### 2. Refreshing a Stale Lane Workspace

If a lane branch has advanced while you were away:

```bash
cd .worktrees/042-mission-lane-a
spec-kitty implement WP## --mission 042-mission
```

Let the stale-check and auto-merge classifier decide whether the lane can be
refreshed automatically from the mission branch. Only perform a manual rebase
when the CLI reports a conflict that requires agent resolution.

Python displays the lane workspace and branch, but the agent resolves conflicts
and completes the rebase manually when needed.

### 3. Multi-Dependency Work

Task finalization computes a lane that already contains the required dependency
shape. Agents do not choose one dependency as a manual base and do not manually
merge sibling lane outputs to reconstruct the lane.

### 4. Pushing

`spec-kitty merge` only pushes with `--push`. All other pushing is the
agent's responsibility.

### 5. Conflict Resolution

If `spec-kitty merge` encounters conflicts, the agent must resolve them.
Python does not attempt automatic conflict resolution.

---

## Auto-Commit Configuration

```yaml
# .kittify/config.yaml
auto_commit: true    # default
```

When `true`, spec-kitty auto-commits:
- Planning artifacts before worktree creation
- WP frontmatter on lane transitions (doing, for_review)

When `false`, agents must commit everything manually.

Per-command override: `--no-auto-commit` flag on `spec-kitty implement`.

---

## Worktree Lifecycle

```
1. CREATED
   spec-kitty implement WP01
   → git worktree add -b kitty/mission-042-mission-lane-a .worktrees/042-mission-lane-a kitty/mission-042-mission
   → .kittify/workspaces/042-mission-lane-a.json created

2. ACTIVE (agent works here)
   cd .worktrees/042-mission-lane-a
   → agent writes code, commits, tests
   → WP status: in_progress

3. FOR REVIEW
   spec-kitty agent tasks move-task WP01 --to for_review
   → auto-commit: "chore: Start WP01 review"
   → reviewer checks the diff

4. MERGED
   spec-kitty accept --mission 042-mission
   spec-kitty merge --mission 042-mission
   → detached merge worktree validates and advances target branch
   → git worktree remove .worktrees/042-mission-lane-a --force
   → git branch -d kitty/mission-042-mission-lane-a
   → .kittify/workspaces/042-mission-lane-a.json removed

5. CLEANED UP
   Worktree directory gone, branch deleted, workspace context removed
```

---

## Git Hooks

Spec Kitty installs a scoped commit-guard hook for managed workflows. Do not
edit `.git/hooks/` by hand; use the CLI repair path when hook state is stale.

---

## Key Anti-Patterns

1. **Agent creates worktree manually** — Don't `git worktree add` yourself.
   Use `spec-kitty implement`. Manual worktrees won't have workspace context,
   canonical workspace context, or proper branch naming.

2. **Agent commits in the repository root checkout during implementation** — Implementation
   commits belong in the worktree, not in the repository root checkout. The repository root checkout is
   for planning artifacts only.

3. **Agent pushes without being asked** — Never auto-push. Only push when
   the user explicitly requests it or when using `spec-kitty merge --push`.

4. **Agent modifies other WPs from a worktree** — Each worktree is isolated
   to one WP. Don't modify files belonging to other WPs.

5. **Agent skips commits before for_review** — Spec-kitty validates that
   worktree has commits ahead of base before accepting the transition.

---

## References

- `references/git-operations-matrix.md` -- Complete matrix of every git command spec-kitty runs
