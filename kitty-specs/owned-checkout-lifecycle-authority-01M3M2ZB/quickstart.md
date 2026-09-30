# Quickstart: running a mission from an owned checkout

This walkthrough is the SC-001 acceptance path. R is the repository root checkout and P is a linked worktree you own.

```bash
# In R: create a linked worktree on its own branch
git worktree add -b kitty/demo-owned ../demo-owned main
P=$(cd ../demo-owned && pwd)

# Create the mission in P (single_branch)
spec-kitty agent mission create demo --mission-type software-dev \
  --owned-checkout "$P" --target-branch kitty/demo-owned --topology single_branch --json

# Write spec.md in P, then commit it in P
spec-kitty spec-commit --owned-checkout "$P" --mission demo-<mid8> \
  "$P/kitty-specs/demo-<mid8>/spec.md" "$P/kitty-specs/demo-<mid8>/meta.json"

# Plan and status, in P
spec-kitty agent mission setup-plan --owned-checkout "$P" --mission demo-<mid8> --json
spec-kitty agent tasks status --owned-checkout "$P" --mission demo-<mid8> --json

# Tasks: write tasks.md and WP files in P, then finalize
spec-kitty agent mission finalize-tasks --owned-checkout "$P" --mission demo-<mid8> --json

# Drive the loop
spec-kitty next --agent claude --owned-checkout "$P" --mission demo-<mid8> --result success --json   # → implement WP01, workspace = P
spec-kitty agent tasks move-task WP01 --to claimed     --owned-checkout "$P" --mission demo-<mid8>
spec-kitty agent tasks move-task WP01 --to in_progress --owned-checkout "$P" --mission demo-<mid8>
# ... implement in P, commit ...
spec-kitty agent tasks move-task WP01 --to for_review  --owned-checkout "$P" --mission demo-<mid8>
spec-kitty next --agent claude --owned-checkout "$P" --mission demo-<mid8> --json                     # → review prompt, base = WP01 claim commit

# Work-package context
spec-kitty agent context resolve --owned-checkout "$P" --action implement --mission demo-<mid8> --wp-id WP01 --json
```

**Expected throughout**:
- every command exits 0;
- R is unchanged, per spec.md NFR-001's definition (working tree including ignored files, `HEAD`, index, the shared lock root and `SPEC_KITTY_HOME`);
- if R still holds an old copy of `demo-<mid8>`, every JSON payload carries `stale_repository_root_copy` and every path stays under P.

**Not supported for owned missions**: `agent action implement` and `agent action review` refuse with `OWNED_ACTION_UNSUPPORTED` and point to the commands above. Full support is tracked in #5100.

**Flagless**: running the same commands from inside `$P` without `--owned-checkout` adopts P after validation. Running them from R, a lane worktree or a coordination worktree behaves as before.
