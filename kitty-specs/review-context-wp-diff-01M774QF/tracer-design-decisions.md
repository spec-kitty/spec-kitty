# Tracer: design decisions (#7578)

Seeded 2026-11-12. Append dated entries: the decision, why, and the alternatives.

- 2026-11-12: the range is window open → newest `for_review` `lane_head` (R1). The window rule moves to `status/` (R4). See research.md R1–R8.
- 2026-11-12: risk recorded before implementation: `_mixed_lanes` includes planning lanes, so the commit-to-target stamp gives canceled-content attribution real inputs. Characterize first (IC-06a), then record the after-state here and in the ADR amendment.
- 2026-11-12, post-plan squad: the commit-to-target verdict change reaches consolidation only through `_mixed_lanes` / `lacks_lane_head_stamps`, `_recorded_lane_heads` and `_has_review_approval_stamp`. It never goes through `check_write_branch_windows`, as the Q3 ruling text assumed; `_bound_write_branch` returns None for commit-to-target. Event-commit fallbacks are limited to `single_branch`. The review range owns the WP pathspecs, and `matches_owned` moves to `ownership/`.
- 2026-11-12, post-tasks squad: C-010 is read per work package, as charter C-011 says ("often the first commit of the lane"). A separate red-only acceptance WP would leave its lane red until consolidation. The reviewer lens proposed that option; the planner lens's per-WP reading was adopted. WP05 was split into WP05 (site 1) and WP07 (sites 2 and 3), each with its own red-first acceptance commit.
- 2026-11-12: accepted deviation from the Q5 ruling's wording. The selector moves to the sibling `status/wp_window_selector.py`, not into `status/wp_window.py`, which keeps that codec's git-free, no-specify_cli-imports invariant. The substance of the ruling (one rule, in `status/`) is unchanged.
- 2026-11-12, operator ruling Q7: `OWNED_REVIEW_BASE_UNAVAILABLE` keeps its code and message and fires only on real lineage problems: no provable range, or no owned files.
