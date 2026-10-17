# Data Model: Owned issue-verdict authority (#6320)

No new persisted entities or schema changes. This records the existing entities the fix
threads a fact through, and the one behavioral state change.

## Entities (existing, unchanged shape)

### OwnedCheckout (the threaded fact)
- Fields used: `mission_slug`, owned checkout root.
- Source: `specify_cli.core.owned_mission`; resolved via `_owned_checkout.resolve_owned_or_refuse`.
- Carried as the keyword arg `owned=` (defaulting `None`). Additive only.

### issue-matrix.json (unchanged format)
- Per-mission record of criterion verdicts for cited GitHub issues.
- Written by `specify_cli.tasks.issue_matrix.write_issue_matrix` (already `owned`-capable) through
  the locked re-read/splice/write; gates work-package approval.
- This mission changes **which directory** the matrix is resolved in for an owned mission, not
  its contents or format (C-002).

### Write-target gate (behavior, not data)
- `coordination.surface_resolver.resolve_for_write` →
  `mission_runtime.write_target_degrade.{resolve_write_target_or_degrade, _mission_meta_exists,
  assert_coord_write_materialized}`.
- `_mission_meta_exists` currently reads `read_primary_meta(repo_root, …)` at the repository root.

## State transition (the fix)

For an owned-only mission handed a valid `owned` fact:

```
Before:  issue-verdict --owned-checkout P
         → resolve_for_write(R, slug)  → _mission_meta_exists(R, slug) = False
         → terminus_write raise        → REFUSE (coord_surface_unmaterialized / MISSION_NOT_FOUND)

After:   issue-verdict --owned-checkout P
         → resolve_for_write(R, slug, owned=P) → _mission_meta_exists(R, slug, owned=P) = True
         → resolve_placement_only(..., owned=P).write_dir(ISSUE_MATRIX)
         → write_issue_matrix(..., owned=P)     → verdict recorded in P's issue-matrix.json
```

Invariant preserved (NFR-001): an `owned` fact that resolves **no** real mission still refuses
fail-closed — no silent fallback to `R`.

Invariant preserved (FR-005): the three unrelated callers of `assert_coord_write_materialized`
pass no `owned` (default `None`) and resolve exactly as before.
