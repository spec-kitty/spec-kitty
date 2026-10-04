# design-decisions

- #5459: share one repo-root guard helper between `create_lane_workspace` and the action path rather than calling `top_level_implement` (which would emit its own claim).
- #5655: scope the annotation commit change to stored SINGLE_BRANCH; flat/legacy keep the uncommitted write.
