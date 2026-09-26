# Tasks: Silent Destructive-Write Hardening

**Mission**: `silent-destructive-write-hardening-01M355VK`
**Branch**: `fix/silent-destructive-write-hardening` (planning base + merge target)
**Topology**: single_branch

Three independent WPs (no dependency edges). Each lands an issue-pinned red-first regression
test through the pre-existing entry point (RED on merge-base, GREEN after fix).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first regression: `charter activate` on a research project flips catalog.mission + shrinks references | WP01 | [P] |
| T002 | Read recorded mission type from SSOT as the recompile fallback (replace `"software-dev"` literal, generate.py:249) | WP01 | |
| T003 | Thread recorded mission type through the activate.py recompile call site (:558-566) | WP01 | |
| T004 | Apply the same SSOT read to `pack apply --compile` (pack.py:208-217) | WP01 | |
| T005 | Focused unit tests for the SSOT-read helper; confirm #2940 malformed-answers guard preserved | WP01 | |
| T006 | Red-first regression: `doctor mission-state --fix` drops DecisionPoint rows / decisions goes unclean | WP02 | [P] |
| T007 | Create authoritative-non-lane-event-type registry (frozenset + predicate) | WP02 | |
| T008 | `status/store.py:is_non_lane_event` consults the registry | WP02 | |
| T009 | `migration/mission_state.py:_is_preserved_non_lane_row` consults the registry (delegate) | WP02 | |
| T010 | `_repair_mission` does not report errors=0 when it quarantines a canonical row | WP02 | |
| T011 | Single-authority test (both consumers derive from one registry) + no-regression for already-preserved classes | WP02 | |
| T012 | Red-first regression: merging two fenced-section appends to one traces file collapses fences/prose | WP03 | [P] |
| T013 | Replace line-level global dedup with section/block-level union in `union_trace_texts` | WP03 | |
| T014 | Make `merge_driver_traces` 3-way base-aware (consume `%O`) | WP03 | |
| T015 | Unit tests: repeated lines within distinct sections preserved; identical whole sections deduped; INV-3; `_union_acceptance_history` unchanged | WP03 | |

## Work Packages

### WP01 — Charter recompile preserves recorded mission type (#4908)

- **Goal**: `charter activate`/`deactivate`/`pack apply --compile` keep the project's recorded
  mission type and never shrink `catalog.references`.
- **Priority**: P1 · **Requirements**: FR-001, FR-002, FR-003
- **Independent test**: on a `research` project, `charter activate <kind> <id>` leaves
  `catalog.mission=research`, `template_set=research-default`, references not shrinking.
- **Subtasks**: T001–T005
- **Prompt**: [tasks/WP01-charter-recompile-ssot.md](tasks/WP01-charter-recompile-ssot.md) (~300 lines)
- **Dependencies**: none

### WP02 — Authoritative non-lane event-type registry (#4897)

- **Goal**: one registry both the durable reader and the mission-state repair consult, so
  `doctor mission-state --fix` never quarantines authoritative DecisionPoint rows; repair reports
  honest status.
- **Priority**: P1 · **Requirements**: FR-004, FR-005, FR-006
- **Independent test**: `--fix` on a healthy mission with a Decision Moment keeps DecisionPoint
  rows, `doctor decisions clean:true`, `agent decision list` count unchanged.
- **Subtasks**: T006–T011
- **Prompt**: [tasks/WP02-non-lane-event-registry.md](tasks/WP02-non-lane-event-registry.md) (~380 lines)
- **Dependencies**: none

### WP03 — Traces merge driver section-level union (#4894)

- **Goal**: traces merge driver unions at section granularity (+ 3-way base-awareness); preserves
  every non-empty input line or produces a git conflict.
- **Priority**: P1 · **Requirements**: FR-007, FR-008
- **Independent test**: merging two fenced-section appends to one `traces/*.md` keeps both sections
  with all fences/repeated prose (or conflicts).
- **Subtasks**: T012–T015
- **Prompt**: [tasks/WP03-traces-section-union.md](tasks/WP03-traces-section-union.md) (~320 lines)
- **Dependencies**: none

## MVP / sequencing

All three are independent P1 bug fixes; any is a shippable slice. Recommended parallel dispatch
(single_branch — lanes land sequentially at merge, avoiding pushing the mission's own traces
through the WP03-target driver).
