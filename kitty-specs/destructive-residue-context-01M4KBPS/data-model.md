# Data Model: Destructive ops never delete the only copy

## CheckoutRole (enum)
- `REPOSITORY_ROOT`: the repository root checkout.
- `COORDINATION`: a Mission's coordination worktree.
- `MISSION`: a Mission branch worktree.
- `LANE`: a lane worktree.
- `TOOL_OWNED`: a checkout the tool created and owns (pack cache, scratch worktree); no user file can be in it.

## ResidueContext (frozen value object)
| Field | Type | Rule |
|---|---|---|
| `role` | `CheckoutRole` | required |
| `mission_slug` | `str` | required, non-empty, unless `role` is `TOOL_OWNED` |
| `topology` | `MissionTopology` | required (the stored topology), unless `role` is `TOOL_OWNED` |

Invariants: no `None` defaults; construction from an unreadable `meta.json` raises rather than projecting a topology. A factory `ResidueContext.for_mission(repo_root, mission_slug, role)` reads the stored topology.

## is_disposable_residue(path, context) -> bool
Decision table (first match wins):
1. `role == TOOL_OWNED` → every path disposable.
2. path under `kitty-specs/<slug>/` with `slug != context.mission_slug` → not disposable.
3. `is_self_bookkeeping_churn(path)` → disposable.
4. `role == COORDINATION` → not disposable.
5. otherwise → `is_coord_residue_churn(path, mission_slug=..., topology=...)`.

## Refusals
- `DestructiveOpRefused` (existing) gains no new fields; new error codes are listed in `contracts/refusal-codes.md`.
- No new consolidation-state field: a refused teardown is derived from the PASS anchor equalling the live target tip while the coordination branch still exists (WP03).
