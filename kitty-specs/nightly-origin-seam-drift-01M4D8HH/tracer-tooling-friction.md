# Tracer: tooling friction
- `agent mission create` refuses inside a git worktree; the mission had to be created from the repository root checkout (switched it to the topic branch).
- Session-scoped install fixture costs ~30 s on the first test of a run; `git bisect run` per group took ~10 min each.
- `git bisect run` from a *linked* worktree leaked the bisect's git environment into the test fixtures: their `git init`/`git config`/`git commit` calls landed in the shared repository (stray `seed` commits, `codex/*` branches and fixture worktrees, and `core.bare=true` plus a `Test` user in the shared `.git/config`). Restored by hand. Bisect only from the repository root checkout, or run fixtures with `env -u GIT_DIR -u GIT_WORK_TREE`.
- The issue-matrix gate wants canonical columns (`issue | verdict | evidence_ref`) and a row for every `#NNN` the mission cites (it flagged #5845, cited only for context). Use `agent issue-verdict` from the start.
