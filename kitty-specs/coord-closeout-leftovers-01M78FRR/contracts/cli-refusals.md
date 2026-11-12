# Contract: closeout refusals and the reclaim command

## `spec-kitty archive reclaim <mission> [--json]`
| Outcome | Exit | Code |
|---|---|---|
| Triple reclaimed (each step reported) | 0 | — |
| Nothing left to reclaim | 0 | — |
| Mission not archived | 1 | `RECLAIM_NOT_ARCHIVED` |
| No coordination topology | 1 | `RECLAIM_NO_COORDINATION` |
| Coordination worktree dirty | 1 | existing teardown code (triple kept) |
| No recorded landing (`merged_at` missing, or no landed-coordination ref) | 1 | `RECLAIM_UNABSORBED` (says why; canceled Mission → `mission close --discard`) |
| Coordination branch moved past the recorded landing | 1 | `RECLAIM_UNABSORBED` (names the branch and the commits after the landing) |
| Commit destination is not reachable (checkout not on the target branch), checked before any change | 1 | `RECLAIM_NOT_ON_TARGET` (names `git checkout <target_branch>`; nothing changed) |
| Worktree still registered after the teardown seam returned | 1 | `RECLAIM_WORKTREE_KEPT` |
| Marker flattened but its commit failed | 1 | `RECLAIM_MARKER_NOT_COMMITTED` (re-run completes) |

## Squash projection refusal
Exit 1 and rollback unchanged. Adds `Error code: SQUASH_PROJECTION_NOT_LANDED.` and up to 20 `path — reason` lines plus a remaining count. Keeps the phrase "projected coordination bookkeeping content did not land".

## `consolidate --abort` kept-record message
Per outcome: dirty checkout → commit or stash, re-run `--abort`; moved by another actor → `--abort --release-branch <b> --release-reason "..."`; kept verified landing → `--resume` labelled as the way to finish teardown.

## accept "Next steps" (local mode, on the target)
Lanes or a coordination branch to consolidate → record branch named + `spec-kitty consolidate --mission <handle>`; otherwise unchanged.
