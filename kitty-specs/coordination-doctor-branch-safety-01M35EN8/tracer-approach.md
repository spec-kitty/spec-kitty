# Approach Tracer

## 2026-09-22 — Plan

- Selected the existing real-Git coord-staleness contract as the outside-in test seam.
- Selected the existing `_coord_worktree_head_finding` as the only branch-identity
  authority.
- Kept one work package because the test, guard, and truthful-success postcondition are
  one atomic safety contract.
