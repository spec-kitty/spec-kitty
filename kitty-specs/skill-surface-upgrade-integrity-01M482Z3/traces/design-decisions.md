# Design decisions

- 2026-10-06: `--fix` projects missing pack skills itself (operator, DM 01M482ZZ73BDZYM0K2R1CD0SE3).
- 2026-10-06: Doctor fails when no configured tool folder exists; one is enough (operator, same DM).
- 2026-10-06: FR-003 uses snapshot-and-restore of the version trio, not deferred writes (research R-2): four writers, one restore boundary.
- 2026-10-06: Merge rule lives in `coalesce_effects`; managed_skills delegates (C-001).
- 2026-10-06: Verifier/assessment blind spot deferred to a follow-up (C-003).
- 2026-10-06: DRIFT_UNRESOLVED upgrades keep the new stamp (migrations did run); only FAILED outcomes and exceptions restore.
- 2026-10-06: `--fix` reports projected pack skills in the existing `repaired_agents` field rather than adding `repaired`.
- 2026-10-06: Upgrade pre-check now warns `pack_skill_missing` as a side effect of the shared findings function; accepted, not a C-003 fold.
