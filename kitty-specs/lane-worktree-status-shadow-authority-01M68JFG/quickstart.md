# Quickstart — verifying #6466

## The report

A work package completed in a lane worktree, transitioned from the repository root, demanded
`--force` to reach `for_review`.

## Verify the fix

```bash
# 1. The regression fixture (real mission, real registered lane worktree)
uv run pytest tests/specify_cli/missions/test_lane_worktree_status_shadow.py -q

# 2. Prove the red-first leg (the lane-rooted reads fail without the rule)
git stash push src/specify_cli/missions/_read_path_resolver.py
uv run pytest tests/specify_cli/missions/test_lane_worktree_status_shadow.py -q   # 3 fail, 2 pass
git stash pop

# 3. The neighbouring surfaces stay green
uv run pytest tests/specify_cli/missions/ tests/mission_runtime/ tests/specify_cli/status/ -q
```

## On a live mission

Drive the transition from wherever you are — root, lane worktree, or a script that hands the lane
worktree in as its repository root. The read answers from the mission's authoritative status
surface, so the `for_review` move no longer needs `--force`.
