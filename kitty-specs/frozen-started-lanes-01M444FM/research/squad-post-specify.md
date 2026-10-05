# Post-specify squad: findings and dispositions

**Question:** does `spec.md` faithfully and completely encode the grounding (D1–D8), with testable, non-vacuous
requirements, the right scope and charter compliance?

**Cast:**
- `reviewer-renata` (spec vs grounding fidelity, non-vacuity)
- `planner-priti` (scope, doctrine)

Both delegates were profile-loaded, read-only, and returned the verdict **READY WITH FOLDS**.

Disposition contract: every finding is `accepted` (with where the change landed), `changed`, or
`deferred_with_rationale`.

## Findings and dispositions

| # | Severity | Source | Finding | Disposition | Evidence |
|---|---|---|---|---|---|
| 1 | HIGH | renata, priti | FR-007 treats an absent log like an unreadable one. A legacy `tasks_finalize.py:308-330` writes `lanes.json` before seeding status, so refusing there would block a legitimate re-finalize. | accepted | spec FR-007; US2 AS5 (malformed or unresolvable) + AS6 (absent log, positive control) |
| 2 | HIGH | renata | The "cancel and re-plan" remedy loops for the collapse case: a canceled WP stays started and lane-eligible. | accepted | spec FR-006 (one remedy per reason); US2 AS7 (applying the remedy makes the next run succeed) |
| 3 | MEDIUM | priti | The cancel remedy must say *without* clearing `owned_files`, or it runs into the deferred #3432 refusal. | accepted | spec FR-006 |
| 4 | MEDIUM | renata | "Write nothing" was unclear: frontmatter and `tasks.md` are written before lane inputs exist. | accepted | spec FR-005 + SC-003 (adds `tasks.md` and `meta.json`). Finalize's existing write-scope snapshot/restore (`mission_finalize.py:1398-1416`) restores mission files on any refusal; the check runs before the first status write. |
| 5 | MEDIUM | renata | The "started" definition misses `blocked → in_progress` and forced skips (`wp_state.py:178`). | accepted | spec Domain Language + FR-008 ("any lane other than planned, blocked, canceled"); fixtures for both paths in the plan's test design |
| 6 | MEDIUM | renata | Refusing the removal of a started WP's file is a behaviour change, so it should be recorded as one. | accepted | spec FR-005 (states it is intentional). Priti independently judged it a consequence of the brief + ADR 3.x `2026-09-26-2` + #3311, not a new operator decision. No existing test removes a started WP. |
| 7 | MEDIUM | renata, priti | The lane-tip fallback over-freezes, because a tip is recorded at allocation. Also extend the #3713 frontmatter-cancel exemption to fallback-started WPs. | accepted | spec Edge Cases (over-freezing is safe; exemption extended); SC-004 reworded |
| 8 | MEDIUM | priti | Three "has execution begun" predicates will coexist. | deferred_with_rationale | Each answers a different question: the planning pin (#3311/#4141 semantics), the doctor snapshot, and the new started authority. Folding the pin changes released pin behaviour. The new predicate is the only "started" authority in the status facade. Follow-up issue filed (see spec Out of Scope); glossary entry planned. |
| 9 | LOW | priti | Key Entities should list all four `lanes.json` write paths and why each is safe. | accepted | spec Key Entities |
| 10 | LOW | renata | A started WP gaining a dependency on a planned lane-mate is not covered. | accepted | spec Edge Cases |
| 11 | LOW | renata | Per-lane lane-tip lookups may break NFR-001. | accepted | plan: a single ref listing for all lane tips |
| 12 | LOW | renata | The NFR-004 20 s CLI budget is tight. | accepted | spec NFR-004 → 30 s on a warm environment |
| 13 | LOW | renata | FR-009 is feasible; the validate-only lane-id preview will change for missions that already have lanes. | accepted | plan: the validate-only preview passes the prior manifest; recorded as an intended output change |
| 14 | INFO | priti | D7 overstated `STALE_CANCELED_DEPENDENCIES` ("every real cancellation"). | accepted | `research/code-grounding.md` D7 corrected |
| 15 | INFO | priti | ADR needed under `docs/adr/4.x/`. | accepted | plan: a new ADR is part of the docs concern |
