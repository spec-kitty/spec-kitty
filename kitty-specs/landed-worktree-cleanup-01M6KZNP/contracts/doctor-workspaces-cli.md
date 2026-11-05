# Contract: `spec-kitty doctor workspaces`

```
spec-kitty doctor workspaces [--fix] [--prune] [--json]
```

| Flag | Effect |
|------|--------|
| (none) | Husk report (unchanged) + landed-worktree report. Writes nothing. |
| `--fix` | Unchanged: removes unregistered husks only. |
| `--prune` | Removes each worktree whose verdict is `landed`, then its local branch, through the destructive guard (no `--force`). |
| `--json` | Adds `worktrees: [WorktreeVerdict]` (each with `ignored_paths` and `ignored_count`), `uninspected_processes` and, with `--prune`, `pruned: [PruneOutcome]` beside the existing husk keys. |

Exit codes: 0 when there are no husks and no guard refusal; 1 when husks remain, the worktree list cannot be read, or a removal the verdict allowed was refused by the guard. Landed worktrees alone never make the exit non-zero.

`healthy` in the JSON payload equals exit code 0, so a worktree refusal makes it `false` (amended at closeout, #7173 squad).

Text output per removal:

```
Removed .worktrees/land-7086 (branch land-7086 at 1a2b3c4d5e6f)
  recreate: git branch land-7086 1a2b3c4d5e6f...
  tip kept at refs/spec-kitty/discarded/land-7086
```

The `tip kept at` line appears when no local branch or tag reaches the tip (remote-tracking refs do not count). A detached worktree's tip is kept at `refs/spec-kitty/discarded/detached/<sha>` (amended at closeout, #7173 squad).

Text output per kept worktree: path, branch, verdict, reason, and for `landed` without `--prune` the command `spec-kitty doctor workspaces --prune`. A verdict that found ignored files adds `will also delete ignored: <up to five paths> (+N more)`. A worktree unproven only because running processes cannot be checked (`PROCESS_PROOF_UNAVAILABLE`, no `/proc`) adds the hand commands `git worktree remove <path>` and `git branch -D <branch>`, to run only after checking (amended at closeout, #7173 squad). Detached worktrees outside `.worktrees/` (`excluded`) appear only in JSON.

A worktree with a rebase, merge, cherry-pick, revert or bisect in progress (`rebase-merge/`, `rebase-apply/`, `MERGE_HEAD`, `CHERRY_PICK_HEAD`, `REVERT_HEAD` or `BISECT_LOG` in its git dir) is `not_landed` with reason `OPERATION_IN_PROGRESS`; a rebase whose `head-name` is a Mission branch is `mission_owned` (`MISSION_LANE`) (amended at landing, #7173).
