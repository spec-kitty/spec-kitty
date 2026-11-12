# Tracer: design-decisions

Mission: next-lifecycle-integrity-01M77BWP. Append dated entries during implementation; assess at close.

- 2026-11-12: Operator rulings (decisions/): fold #5929+#7565; finished board -> blocked MISSION_AWAITING_ACCEPTANCE / accepted -> terminal; query question stays nullable + additive next_command; rollback reset recorded + narrowable.
- 2026-11-12: Command goes in a new `next_command`, not `remediation` (remediation already means "what next materialized", #7310 WP06).
- 2026-11-12: Gate does not pre-empt a run legitimately at implement/review/accept, so MissionRunCompleted + retrospective gate stay reachable for next-driven missions.
