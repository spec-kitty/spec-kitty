# Design decisions

- 2026-10-04: No `resync_checkouts=True` outside consolidation/rollback.py (gate). Follow the mission-create precedent instead: CAS ref restore, `read-tree` of the captured index tree, byte restore of the status directory.
- 2026-10-04: A ref that moved after our own last status commit is never forced: the run reports the commits it made and could not undo.
- 2026-10-04: The owned-only `_restore_owned_head` (mixed `git reset`, not CAS) is retired; the guard covers P's branch, so the atomicity guard has one restore authority.
- 2026-10-04: Coordination status bytes are restored only once the branch is back at its pre-run tip, so a refused restore never leaves that worktree diverged from its own HEAD (#5633's `COORD_STATUS_SURFACE_DIVERGED`).
- 2026-10-04: Retry needed no separate fix: with no seed commit left behind, the retry is an ordinary first run (research/retry-evidence.md).
