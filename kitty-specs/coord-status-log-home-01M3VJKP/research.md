# Research: Coordination status log stays off the target branch

## Decision: seed the status log on the coordination branch at create

**Rationale**: Issue #5440's primary expected outcome is that a coord mission's status byte-sets never land on the target branch through CLI commits. Traced on `main` (`src/specify_cli/core/mission_creation.py`):

- `_scaffold_mission_dir` puts `status.events.jsonl` into `scaffold_paths` for every topology.
- `_emit_create_events` writes `MissionCreated` and `SpecifyStarted` into the primary copy.
- `_commit_create_scaffold` commits the set onto the create-time target, the target branch.
- `ensure_coordination_branch` mints the coordination branch off the target *before* the scaffold commit, so the coordination worktree, once materialized, has no mission directory. `resolve_status_surface_with_anchor` then reports `CoordState.EMPTY` and falls back to the primary copy. Every later status write follows that fallback until some coordination write creates the mission directory, which flips the surface with no carry-over (#5519).

**Live evidence** (scratch e2e on `main`, coord mission on a topic target): the target branch carries `kitty-specs/<m>/status.events.jsonl` from the create step through every later step. With the fix, the target branch carries none at any step, and every lane transition commits on the coordination branch.

**Alternatives considered**:

- *Reconcile a target-side copy at consolidate* (the issue's alternative): rejected. It keeps the CLI writing a COORD-partition kind onto the target and repairs it later; the single-authority principle prefers fixing the writer.
- *Commit the log to the coordination branch through git plumbing, without a worktree*: rejected. The resolver returns the composed coordination path while the worktree is unmaterialized, so readers would see a missing file until the first write materializes it.

## Notes for the sibling remediation (#5513, PR #5520)

After this change a coord mission's coordination worktree carries the status log from birth, so `accept`'s coordination-dirty status files become the normal case for the commit-router fix.
