# Tracer: design-decisions

Mission `single-branch-planning-pin-rebase-01M81KRS`. Append during implementation; assess at close.

- R4 (revised): the stateless freeze also froze timely pins on direct histories (R17 red). Switched to a persisted `planning_commit_derived` marker.
- R4b: execution has begun once any WP ever left `planned`. Without that, the #7793 path (the WP rejected back to `planned`) took the pre-execution capture branch.
- R1: the pin branch line is the mission branch for single_branch (capture, refresh, derive). This awaits the dispatcher's confirmation.
