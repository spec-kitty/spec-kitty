# Research: Remote-only branch recovery remedy

Verified on `main` `ba1aa571` (2026-11-20) with `make_prefix_coord_mission(..., remote_only=True)`.

## R-1 Reproduction

- Status door: `resolve_status_read` raises `StatusSurfaceRefUnreadable` ("ref does not resolve to a commit (missing)"); `agent tasks status --json` exits 1 with that text only.
- `CoordinationWorktreeUnmaterialized.next_step`: "exists on a remote, but this checkout has not fetched it … Run `git fetch origin <b>`". The fixture's only remote is `coord-remote`, so the text is false twice and omits `git branch <b> <remote>/<b>`.

## R-2 Decisions

- **Decision**: builder home `mission_runtime/coord_remedy.py`. **Rationale**: `mission_runtime/write_target_degrade.py` and `specify_cli` both need it; `mission_runtime` may import `kernel` and `specify_cli` imports `mission_runtime` downward. **Alternatives**: `kernel` (rejected: the text names product commands); `specify_cli` (rejected: grows the `mission_runtime → specify_cli` ledger).
- **Decision**: remote resolution via `kernel.git.remote.resolve_remote`, then the unique remote holding a tracking ref. **Rationale**: local config only (ADR 2026-10-06-3). **Alternatives**: `ls-remote` (rejected: network).
- **Decision**: new subtype `StatusSurfaceRefRemoteOnly(StatusSurfaceRefUnreadable)`. **Rationale**: ~60 references catch or relay the parent; a subtype keeps them working and lets `next` relay the new `error_code` verbatim. **Alternatives**: sibling class (rejected: every handler would need editing).
- **Decision**: classify only on read failure, with `ref_names_object(refs/heads/<b>)` False. **Rationale**: NFR-001 (no cost on healthy reads); a corrupt local ref (names a missing object) still answers True and keeps the unreadable code.
- **Decision**: no `CoordState.REMOTE_ONLY`. **Rationale**: blast radius (49 uses). **Alternative**: enum member (deferred; may be revisited under #7408).
- **Decision**: leave `coordination/policy.py::_missing_destination_remedy` (#7726). **Rationale**: different semantics (a one-line `fetch origin b:b` for a policy destination); sharing would change its wording and remote choice.
