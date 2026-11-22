# Tracer: design-decisions

Mission `single-branch-planning-pin-rebase-01M81KRS`. Append during implementation; assess at close.

- R4: the derived freeze is stateless (recorded == derived now). It replaces a `lanes.json` provenance key; the R3 window guard is the real safety net.
- R1: the pin branch line is the mission branch for single_branch (capture, refresh, derive). This awaits the dispatcher's confirmation.
