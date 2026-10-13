---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-11T14:32:19Z'
reviewer_agent: reviewer-renata
wp_id: WP05
---

# WP05 review cycle 1: returned for two fixes (reviewer-renata + operator rulings)

The reviewer found no blocking defect. Two items are fixed now so that WP17 does not build on them. The full evidence is in wp05-review-verdict.md (orchestrator scratchpad). The rulings are at the end of reviews/analyze.ruling.md (2026-10-11), the amended data-model.md, and DD-78 to DD-80.

| id | severity | file | problem | remedy |
|---|---|---|---|---|
| R1 | medium | domain/model/LineKind.java, domain/reducer/StatusReducer.java | An annotation row becomes `Ignored` and is dropped. In the oracle (spec_kitty_events diary.py around lines 1606-1612), an annotation-only WP stays in `work_packages` and counts in `wpTotal` and in the progress denominator, but in no lane count. The operator ruled for an explicit line kind. | Add `LineKind.Annotation(String wpId)` (data-model.md now lists it). `reduceLines` passes annotation WP ids into the annotation pass. Remove the side-channel `reduce(events, annotatedWpIds)` overload, or make it private, so that there is ONE public path. Add tests: an annotation-only WP counts in `wpTotal` and the progress denominator but in no lane, and its `lifecycleStatus` effect matches the oracle. Add a revert row (drop Annotation handling, tests go red). Keep per-class JaCoCo floors green and update the floor count if the class count changes. |
| R2 | low | domain/reducer/StatusReducer.java (`project` / reduction order) | Projections run over dedup-then-sort events. The oracle (reducer.py around lines 93-116 and 127-172, `reduce_shared_state`) sorts first and then dedups, keeping the first in sorted order. For a duplicate `event_id` with a different `at`, the results differ: the reviewer reproduced `cancellation_reason="Force move to canceled"` (`reason_source` synthetic) in Python against a different Java result. | Reduce and project over sort-then-dedup exactly as the oracle does. Add a duplicate-id-with-different-`at` test whose expected values come from running the Python oracle on the same rows (record the rows and the Python output in the test comment). Add a revert row. |

Not in scope for this round: F3, F4, F5, F6 and F7 (notes and known divergences, recorded as DD-79), and P3/P6 (WP06/WP10 own the 400-misaligned and clamp mappings).
