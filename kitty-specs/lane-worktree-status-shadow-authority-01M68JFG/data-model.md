# Data model — lane worktree status shadow authority

No new entity, field or persisted artifact. The mission changes *which directory* a status read
resolves; the data model is unchanged.

## Entities in play

- **Status surface** — a mission directory holding `status.events.jsonl` (append-only authority) and
  `status.json` (derived snapshot). Located by `coordination/surface_resolver.py`.
- **Lane worktree** — a registered git worktree of the mission's repository whose name is not
  `-coord`. Carries a fork-time copy of the mission directory that is non-authoritative.
- **Repository root** (`repo_root`) — the anchor a read is resolved against. Normalised once per read
  by `_canonical_status_read_root` when it is a lane worktree.

## Invariants

1. Exactly one status surface per mission is authoritative (coordination husk, or primary copy).
2. `status.json` is derived and disposable; it is never merged by timestamp.
3. A lane worktree's copy is read-only history and is never consulted as authority.
