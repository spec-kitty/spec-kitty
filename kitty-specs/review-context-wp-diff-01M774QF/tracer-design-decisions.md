# Tracer: design decisions (#7578)

Seeded 2026-11-12. Append dated entries: the decision, why, and the alternatives.

- 2026-11-12: the range is window open → newest `for_review` `lane_head` (R1). The window rule moves to `status/` (R4). See research.md R1–R8.
- 2026-11-12: risk recorded before implementation: `_mixed_lanes` includes planning lanes, so the commit-to-target stamp gives canceled-content attribution real inputs. Characterize first (IC-06a), then record the after-state here and in the ADR amendment.
- 2026-11-12, post-plan squad: the commit-to-target verdict change reaches consolidation only through `_mixed_lanes` / `lacks_lane_head_stamps`, `_recorded_lane_heads` and `_has_review_approval_stamp`. It never goes through `check_write_branch_windows`, as the Q3 ruling text assumed; `_bound_write_branch` returns None for commit-to-target. Event-commit fallbacks are limited to `single_branch`. The review range owns the WP pathspecs, and `matches_owned` moves to `ownership/`.
