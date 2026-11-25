# Quickstart: verifying the landing proof

```bash
# unit rules of the predicate
uv run --frozen pytest tests/lanes/test_lane_tip_mission_bookkeeping.py -q
# red-first acceptance: a real squash landing removes every lane
uv run --frozen pytest tests/integration/test_lane_cleanup_landing_proof_7747.py -q
# doctor
uv run --frozen pytest tests/specify_cli/workspace/test_landed_worktrees_mission_bookkeeping.py -q
# #7325 kept legs
uv run --frozen pytest tests/consolidation/test_lane_remover_proof_unavailable_7325.py -q
```

By hand, after `spec-kitty consolidate` of a `lanes_with_coord` Mission, the `Lane cleanup` block lists each lane as `Removed`. After pushing the target to the remote primary branch, `spec-kitty doctor workspaces` rates any remaining lane of that Mission `landed`.
