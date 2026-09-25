# Quickstart: reproduce & verify

Both defects reproduce with the actual CLI in an isolated HOME/XDG + disposable repo on `coord` topology.

## #4889 — silent empty re-cut
1. `init` → `agent mission create --topology coord` → planning (WP01, WP02 dep WP01) → `finalize-tasks`.
2. `spec-kitty implement WP01` → lane-a worktree + branch. Commit real work (`feature.txt`) in the lane; record the lane tip.
3. **Trigger**: `git worktree remove --force <lane-a>` and `git branch -D kitty/mission-<slug>-lane-a`.
4. `spec-kitty implement WP01` again.

- **Pre-fix (BUG)**: exit 0, `✓ Lane worktree ready`, new empty lane cut from coord tip, `feature.txt` absent, WP01 commit not an ancestor.
- **Post-fix**: exit non-zero, diagnostic names the missing branch + recovery ref, no `Lane worktree ready`, `.kittify/workspaces/*.json` unchanged. Same via `agent action implement WP01` / `start-implementation`.
- **Control (unchanged)**: nothing deleted → exit 0 no-op resume, `feature.txt` present.

## #4905 — WP file on coord branch → WP02 conflict
1. `coord` mission with WP01, WP02 (dep WP01).
2. `spec-kitty agent action implement WP01 --agent claude`.
3. `spec-kitty agent action implement WP02 --agent claude`.

- **Pre-fix (BUG)**: WP02 fails with `PlanningCommitMergeConflictError`, exit 1; coord tree carries `tasks/WP01-*.md`.
- **Post-fix**: coord tree has no `tasks/WP*.md` (after claim AND after WP01 review-claim); WP02 starts, exit 0.
- **Control**: `--topology lanes` starts both WPs unchanged.

## Test entry points
- `PWHEADLESS=1 .venv/bin/python -m pytest tests/lanes/ -q` (allocator routes, #4889)
- `.venv/bin/python -m pytest tests/orchestrator_api/ -q` (caller-independence, #4889)
- `.venv/bin/python -m pytest tests/specify_cli/ -k "coord and (claim or staging)" -q` (#4905)
