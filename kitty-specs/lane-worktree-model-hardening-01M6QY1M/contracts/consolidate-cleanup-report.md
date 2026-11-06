# Consolidation cleanup report (S5: FR-030 to FR-039a)

## Order (FR-031)

1. Coordination teardown (S10's codes and exits unchanged).
2. Lane legs: each lane is `removed`, `kept` or `retained_by_policy`.
3. The consolidation record is cleared. Nothing mutates afterwards.

## `spec-kitty consolidate` (text)

```
Lane cleanup
  Removed   lane-a  kitty/mission-<slug>-lane-a   (recreate: git branch kitty/mission-<slug>-lane-a refs/spec-kitty/discarded/...)
  Kept      lane-b  MERGE_UNSAFE_WORKTREE_DIRTY   .worktrees/<slug>-lane-b has uncommitted changes.
            Remedy: commit or discard them, then run: spec-kitty doctor workspaces --prune
  Retained  lane-c  retained by policy (retain_worktrees)
```

Exit code **0** when the landing is verified, whatever the lane outcomes (NFR-004). Coordination teardown refusals keep their non-zero exits (1, 75).

## `spec-kitty consolidate --json`: additive key

```jsonc
"lane_cleanup": [
  {"lane_id": "lane-a", "branch": "kitty/mission-<slug>-lane-a", "worktree": ".worktrees/<slug>-lane-a",
   "outcome": "removed", "code": null, "remedy": null, "command": null, "recreate": "git branch ..."},
  {"lane_id": "lane-b", "outcome": "kept", "code": "MERGE_UNSAFE_WORKTREE_DIRTY",
   "remedy": "...", "command": "spec-kitty doctor workspaces --prune", "recreate": null},
  {"lane_id": "lane-c", "outcome": "retained_by_policy", "code": null, "remedy": null, "command": null, "recreate": null}
]
```

## `orchestrator-api consolidate-mission`: contract **1.24.0** (minor, FR-039a)

- `data.lane_cleanup` is the array above (same objects).
- `data.teardown_error_code` stays for coordination teardown only. A lane refusal no longer fills it and no longer fails the envelope after a verified landing.
- `CONTRACT_VERSION` moves `1.23.0 → 1.24.0` (`src/specify_cli/orchestrator_api/envelope.py`). `docs/api/orchestrator-api.md` documents the field.
- The same bump also adds `topology_source` / `topology_provisional` to `orchestrator-api specify` and `topology_decision` to `orchestrator-api tasks` (DM `01M6R0BJQ6Q1MV6492EH6HB66H`).

## `accept --mode pr` (FR-036, after #7275)

- `cleanup_instructions` no longer contains raw `git worktree remove` / `git branch -d` advice.
- `--json` gains `lane_cleanup` (same shape). Lanes absorbed by `refs/remotes/<remote>/<pr-head>` are removed before the PR merges. Unpushed lanes are `kept` with `NOT_LANDED_ON_NAMED_REMOTE`.

## `doctor workspaces --prune` (FR-039, after #7275)

Lanes of a consolidated or PR-accepted Mission become removal candidates when no consolidation record is active and no `retain_*` is declared. Otherwise they stay report-only (verdict `mission_owned`).
