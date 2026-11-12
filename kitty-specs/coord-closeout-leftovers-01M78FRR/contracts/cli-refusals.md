# Contract: closeout refusals and the reclaim command

## `spec-kitty archive reclaim <mission> [--json]`
| Outcome | Exit | Code |
|---|---|---|
| Triple reclaimed (each step reported) | 0 | — |
| Nothing left to reclaim | 0 | — |
| Mission not archived | 1 | `RECLAIM_NOT_ARCHIVED` |
| No coordination topology | 1 | `RECLAIM_NO_COORDINATION` |
| Coordination worktree dirty | 1 | existing teardown code (triple kept) |
| Coordination content not on the target | 1 | `RECLAIM_UNABSORBED` (names branch + remedy: `mission close --discard` for a canceled Mission) |
| git < 2.38 (absorption unsupported) | 1 | `RECLAIM_UNABSORBED` (fails closed, says why) |

## Squash projection refusal
Exit 1 and rollback unchanged. Adds `Error code: SQUASH_PROJECTION_NOT_LANDED.` and up to 20 `path — reason` lines plus a remaining count. Keeps the phrase "projected coordination bookkeeping content did not land".

## `consolidate --abort` kept-record message
Per outcome: dirty checkout → commit or stash, re-run `--abort`; moved by another actor → `--abort --release-branch <b> --release-reason "..."`; kept verified landing → `--resume` labelled as the way to finish teardown.

## accept "Next steps" (local mode, on the target)
Lanes or a coordination branch to consolidate → record branch named + `spec-kitty consolidate --mission <handle>`; otherwise unchanged.
