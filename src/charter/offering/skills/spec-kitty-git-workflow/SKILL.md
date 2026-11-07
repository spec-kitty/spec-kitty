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

**Python handles infrastructure git** — worktrees, status commits, lane
consolidation, cleanup. **Agents handle content git** — implementation commits, rebases,
conflict resolution.

| Git Operation | Who Does It | When |
|---|---|---|
| `git worktree add` | Python | `spec-kitty implement WP##` |
| `git commit` (planning artifacts) | Python | Before worktree creation |
| `git commit` (status events) | Python | Every lifecycle command, on the resolved status surface (never a lane branch) |
| `git commit` (implementation code) | **Agent** | After writing code in worktree |
| Auto-rebase (stale lane refresh) | Python | `spec-kitty consolidate`, and the lane sync point `spec-kitty agent action implement` runs |
| Lane consolidation (lane → mission → target) | Python | `spec-kitty consolidate` (local only; no `--push`) |
| `git push` | **Agent** | Only when the user asks (a topic branch, never `main`) |
| Conflict resolution | **Agent** | When an auto-rebase stops on a conflict |
| `git worktree remove` | Python | Consolidation's final step, after the verified landing, under the destructive-operation guard |
| `git branch -d` (cleanup) | Python | Consolidation's final step, same guard |

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
`BookkeepingTransaction` and `safe_commit`, which takes exact file paths and refuses a
directory (`SAFE_COMMIT_DIRECTORY_ARGUMENT`); the `spec-kitty safe-commit <dir>` CLI expands one:

```
safe_commit(paths=["kitty-specs/042-mission/spec.md", "kitty-specs/042-mission/plan.md"], message="chore: Planning artifacts for 042-mission")
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

### 4. Status Event Log (Written by the CLI)

Every lifecycle command writes its status event to the resolved status surface
(the coordination branch for coordination topologies, otherwise the Mission
branch) and commits it there itself. Lane checkouts carry no status files.
Status files are never committed by hand; read status with
`spec-kitty agent tasks status --mission <slug>`.

### 5. Consolidation

Run `spec-kitty accept --mission 042-mission` before consolidation once every
WP is approved. Acceptance is a readiness nudge and artifact check;
consolidation still owns the final mission-close transition.

`spec-kitty consolidate --mission 042-mission` consolidates each lane branch
into the mission branch (auto-rebasing a stale lane first), lands the mission
branch on the target branch with the selected strategy, verifies the landing,
and then, as its final step, removes the lane and coordination checkouts and
branches. It prints a cleanup report: `Removed`, `Kept` (a guard refused the
removal; the line names the code) or `Retained` (retained by policy). A `Kept`
lane does not fail the run once the landing verified.

Consolidation order follows the dependency graph (topological sort).

Supports 3 strategies: `squash` (default), `merge` (--no-ff), `rebase`.

Consolidation is local only; it never publishes to the remote.

### 6. Pre-flight Validation (Read-Only)

Before consolidation, Python validates:
1. All expected WPs have worktrees
2. All worktrees are clean (`git status --porcelain`)
3. Target branch is not behind origin (`git rev-list --left-right --count`)
4. WPs in done lane with missing worktrees are skipped (already merged)

If any check fails, consolidation is blocked with specific error messages.

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
checks that the lane branch has commits ahead of its base
(`git rev-list --count <base>..refs/heads/<lane>`, from the repository root),
so the check works with no lane checkout. If zero commits, the transition is
rejected.

### 2. Refreshing a Stale Lane Workspace

The CLI refreshes a stale lane, not the agent. Re-run
`spec-kitty agent action implement WP## --mission 042-mission`: it runs the
lane sync point, which auto-rebases the lane onto the mission branch. When
`spec-kitty consolidate` reports a stale lane, run the command it prints.
Resolve conflicts by hand only when the CLI stops on one, in the lane checkout
it names.

If `implement` refuses with `DESTROYED_LANE` or `LANE_WORK_TIP_UNKNOWN` (the
lane's branch is gone), follow the command the CLI prints.

### 3. Multi-Dependency Work

Task finalization computes a lane that already contains the required dependency
shape. Agents do not choose one dependency as a manual base and do not manually
merge sibling lane outputs to reconstruct the lane.

### 4. Pushing

`spec-kitty consolidate` never pushes. Push a topic branch only when the user
asks; never push to `main`.

### 5. Conflict Resolution

If an auto-rebase stops on a conflict, the agent resolves it in the lane
checkout the CLI names, commits, and re-runs the command.

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

4. CONSOLIDATED
   spec-kitty accept --mission 042-mission
   spec-kitty consolidate --mission 042-mission
   → lanes consolidated, landing on the target branch verified

5. CLEANED UP (consolidation's final step)
   → lane checkout and branch removed under the destructive-operation guard
   → .kittify/workspaces/042-mission-lane-a.json removed
   → cleanup report: Removed / Kept / Retained
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
   the user explicitly requests it.

4. **Agent modifies other WPs from a worktree** — Each worktree is isolated
   to one WP. Don't modify files belonging to other WPs.

5. **Agent skips commits before for_review** — Spec-kitty validates that
   worktree has commits ahead of base before accepting the transition.

---

## References

- `references/git-operations-matrix.md` -- Complete matrix of every git command spec-kitty runs
