# Contract: the lane landing proof and the proof-unavailable kept line

## `specify_cli.lanes.lane_tip.is_absorbed_but_for_mission_bookkeeping`

```python
def is_absorbed_but_for_mission_bookkeeping(repo_root: Path, tip: str, landing_ref: str, mission_slug: str) -> bool
```

- Returns `True` when `tip` is an ancestor of `landing_ref`, or when every difference between them is accounted for by the rules in research R3 (outside `kitty-specs/`: an in-memory merge that changes nothing on `landing_ref` and has no conflict there; under `kitty-specs/`: the per-path rules).
- Returns `False` on anything else, including any git error, an unknown ref, or a git without `merge-tree --write-tree`. Never raises.
- Callers: `consolidation.lane_cleanup.GuardedLaneRemover` (when the Mission slug is known) and `workspace.landed_worktrees` (for released Mission lanes). Both pass it to `guarded_landed_removal` as the O3 absorption proof.

## Cleanup report: `LANDING_PROOF_UNAVAILABLE`

`contracts/consolidate-cleanup-report.md` (S5) gains one kept code:

| Field | Value |
|-------|-------|
| `outcome` | `kept` |
| `code` | `LANDING_PROOF_UNAVAILABLE` |
| `remedy` | names why no proof was usable and the check to run (`git log <landing>..<branch>`) before deleting the branch by hand |
| `command` | `spec-kitty doctor workspaces --prune` when the lane's worktree still exists, otherwise `null` |
| `recreate` | `null` (nothing was removed) |
