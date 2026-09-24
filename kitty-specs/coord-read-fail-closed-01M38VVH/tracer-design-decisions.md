# Tracer — Design Decisions

- DM-01M38VWD: fail-closed locus = SEAM-LEVEL (resolution.py raises), not per-reader. Closes the
  class; blast-radius audit of every seam caller is the load-bearing planning task.
- Preserve NONE→CoordinationBranchDeleted (#4403); leave non-coord topologies (SINGLE_BRANCH/LANES/
  flat) unaffected.
- Scope guard: do NOT touch surface_resolver._coord_branch_exists / doctor coordination --fix (#4979,
  adjacent to merged #4950).

## Append log (during implement)
- (planning) seeded.
