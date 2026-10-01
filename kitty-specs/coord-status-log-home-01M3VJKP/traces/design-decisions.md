# Design decisions: coord-status-log-home-01M3VJKP

- 2026-10-01: Seed the status log on the coordination branch at create rather than reconciling at consolidate (decision recorded under `decisions/`).
- 2026-10-01: The coordination worktree's mission dir holds only the status log, matching the documented STATUS-only husk shape; `meta.json` stays primary.
- 2026-10-01: When no local coordination branch exists (target does not resolve), the log keeps its primary home and rides the scaffold commit, as before.
- 2026-10-01: finalize's lifecycle emitters resolve their directory through `resolve_status_surface_with_anchor(for_write=True)` and keep `planning_dir` when that does not name an existing directory (owned checkout, unresolvable meta, unmaterialized coord worktree).
- 2026-10-01: bootstrap's final `materialize` is skipped when the feature dir holds no event log, rather than re-resolving the surface there; the transactional emitter already materializes on the right surface per event.
- 2026-10-01: Review cycle 1 — the failed-create rollback removes the coordination worktree through `guarded_worktree_remove` with a residue predicate that accepts only the salvaged status log; the coordination worktree root is carried on `_Scaffold` from `CoordinationWorkspace.worktree_path` rather than walked up from the status dir.
- 2026-10-01: When `materialize_coord_surface_for_write` refuses a coordination branch it cannot see locally, create keeps the primary status home instead of failing.
- 2026-10-01: Consequence accepted: right after create the coordination branch is one commit ahead of its fork point while the target carries the scaffold commit, so a same-identity `ensure_coordination_branch` re-run reports divergence. Production never re-ensures an existing identity (each create mints a fresh ULID).
