# Research — Silent Destructive-Write Hardening

Grounding by two profile-loaded opus lenses (paula-patterns structural + planner-priti scope),
confirmed live on `main` @ `d57619a900`. No dependency changes → supply-chain adversarial-evidence
section is N/A (no contested dependency findings).

## WP01 — #4908 charter recompile hardcodes `software-dev`

- **Decision**: Replace the `resolved_mission = resolved_mission_type or "software-dev"` fallback
  at `generate.py:249` with a read of the recorded mission type from the SSOT. In the `activate.py`
  recompile path (`:558-566`) the guard at `:555` guarantees `charter.yaml` exists, so
  `catalog.mission` is present — read it (and/or `answers.yaml` `mission`) and pass as
  `resolved_mission_type` from both `activate.py:562` and `pack.py:212`.
- **Rationale**: The recompile is a *derived-view writer* (rebuilding `catalog.references`) that
  fabricated an input it should read from the source of truth. Reading the SSOT fixes both callers
  at one seam.
- **Alternatives considered**: (a) flip `from_interview=True` — REJECTED, reintroduces the #2940
  malformed-`answers.yaml` abort regression; (b) thread a new parameter through every call site —
  more churn than reading the SSOT at the fallback.
- **Bounds**: `charter.md`, `answers.yaml`, `config.yaml` activations are untouched by the bug and
  by the fix.

## WP02 — #4897 mission-state --fix quarantines DecisionPoint rows

- **Decision** (operator-chosen, decision `01M3560PHPQM617TH5MZHWRF8J`): create ONE authoritative
  non-lane event-type registry and make both `status/store.py:is_non_lane_event` (:597-631) and
  `migration/mission_state.py:_is_preserved_non_lane_row` (:1919-1972) consult it. Also ensure a
  repair that would quarantine a canonical row does not report `errors=0`/success (`_repair_mission`
  :1671-1691).
- **Rationale**: The durable reader already treats any row with `event_type` (incl. all
  `DecisionPoint*`) as authoritative; the repair kept a hand-narrowed *re-statement* of that rule on
  an inverted belief that DecisionPoint rows are a prunable mirror. `status.events.jsonl` is the
  authoritative store; `decisions/index.json` is a derived fold (`decisions/index_fold.py:3-16`). One
  shared registry closes the recurring whack-a-field class (#2376 retrospective, #3066
  WPStatusChanged, #3541 review_result, #4897 DecisionPoint).
- **Alternatives considered**: (a) add `DecisionPoint*` to the preserved set — REJECTED as another
  whack-a-field patch (spec C-002); (b) delegate to `is_non_lane_event` without a named registry —
  viable but leaves the authority implicit in a predicate; the registry makes it explicit and
  gate-testable.
- **Registry placement**: with the existing status event-type authority (`status/lifecycle_events.py`
  already exports `LIFECYCLE_EVENT_TYPES`), as a sibling authoritative set / predicate that
  `is_non_lane_event` and the repair both import. Must keep the already-preserved classes
  (annotation, retrospective, WPStatusChanged, review_result) preserved — no regression.

## WP03 — #4894 merge-driver-traces line-level global dedup

- **Decision**: Replace line-level *global* dedup in `union_trace_texts` (`merge_driver.py:304-325`)
  with section/block-level union — dedup only whole identical sections/blocks at the
  `<!-- section:... -->` delimiter the docstring already names, preserving repeated lines within
  distinct sections. Preferred enhancement: make `merge_driver_traces` (:328-338) 3-way base-aware
  (consume `%O`) like its sibling matrix drivers so base-common content is not misread.
- **Rationale**: Line-level global dedup is unsound for markdown (fences, headings, prose recur
  legitimately). The sibling acceptance/issue-matrix drivers are 3-way base-aware and fail closed on
  a diverged *verdict* field (`_merge_field:411-466`); that fail-closed shape is correct for a keyed
  row artifact but WRONG for keyless append-union prose — failing closed on every repeat would abort
  nearly every real merge (spec C-003).
- **Non-bug sibling**: the second `seen` set at `merge_driver.py:237-245` (`_union_acceptance_history`)
  dedups whole history *entries* by canonical-JSON equality — correct record-granularity dedup, not
  the bug; leave it.
- **Alternatives considered**: (a) fail-closed like acceptance — REJECTED (aborts real merges);
  (b) pure section union without 3-way — acceptable minimum; 3-way base-awareness is the fuller fix.

## Cross-cutting

- These three are one *pattern* family (silent destructive write, exit 0) but three independent
  seams that do NOT share a single guard. **Do NOT route through the `asset_preservation` guard**
  (`asset_preservation/guard.py`, `test_mutation_ownership_routing.py`): it is filesystem-path
  granularity (`OwnershipProof` over a `Path`); these are content/row/line-level writes → category
  error (spec C-001).
- Only WP02 is a recurring whack-a-field class warranting a shared abstraction (the registry). WP01
  and WP04… (n/a) — WP01 and WP03 are first-order SSOT/granularity bugs fixable in isolation.
