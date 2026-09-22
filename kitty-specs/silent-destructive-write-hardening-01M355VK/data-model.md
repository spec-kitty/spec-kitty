# Data model — Silent Destructive-Write Hardening

No new persisted schemas. The mission touches three existing artifacts and adds one small
in-code registry.

## Existing artifacts (owned per seam)

| Artifact | Owner seam | Canonical for | Derived views |
|----------|-----------|---------------|---------------|
| `charter.yaml` `catalog` | charter compile | `mission`, `template_set`, `references` | consumed by `charter context`, prompt builder, dispatch router |
| `.kittify/charter/interview/answers.yaml` `mission` | charter interview | recorded mission type (SSOT) | `catalog.mission` mirrors it |
| `status.events.jsonl` | status | append-only event log; **authoritative** for `DecisionPoint*` rows | `decisions/index.json` (fold), lane snapshots |
| `traces/*.md` | mission trace authoring | section-delimited authored prose | — |

## New in-code entity (WP02)

- **Authoritative non-lane event-type registry**: a single frozenset (+ predicate) of `event_type`
  values that are authoritative non-lane rows sharing `status.events.jsonl`. Consulted by BOTH
  `status/store.py:is_non_lane_event` and `migration/mission_state.py:_is_preserved_non_lane_row`.
  Superset must cover at least: DecisionPoint{Opened,Resolved,Deferred,Canceled,Widened}, plus the
  already-preserved lifecycle/retrospective/annotation/WPStatusChanged/review_result classes as they
  are represented today. No behavior change for already-preserved classes.

## Invariants

- INV-1 (WP01): `catalog.mission` after any recompile == recorded mission type; `catalog.references`
  is a superset of prior ∪ {activated artifact}.
- INV-2 (WP02): for every `event_type` row, `is_non_lane_event(row)` and repair-preservation agree
  (both derive from the one registry).
- INV-3 (WP03): every non-empty line present in either merge input is present in the merged output,
  OR the merge exits non-zero (conflict).
