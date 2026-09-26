# Decision Moment `01M3560PHPQM617TH5MZHWRF8J`

- **Mission:** `silent-destructive-write-hardening-01M355VK`
- **Origin flow:** `specify`
- **Slot key:** `specify.wp02.repair-preservation-depth`
- **Input key:** `wp02_preservation_fix_depth`
- **Status:** `resolved`
- **Created:** `2026-09-22T18:28:27.318562+00:00`
- **Resolved:** `2026-09-22T18:28:35.513275+00:00`
- **Resolved by:** `stijn-dejongh`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

How far should the #4897 fix go: minimal (add DecisionPoint to preserved set), delegate to is_non_lane_event, or a shared authoritative-non-lane-event-type registry both subsystems consult?

## Options

- shared-registry
- delegate-to-reader
- minimal-decisionpoint-only

## Final answer

shared-registry

## Rationale

Operator-chosen (grounding squad + AskUserQuestion): create ONE authoritative-non-lane-event-type registry that both status/store.py:is_non_lane_event and the mission_state repair (_is_preserved_non_lane_row) consult, closing the recurring whack-a-field class (#2376/#3066/#3541) by construction rather than adding another hand-maintained preserved-set entry.

## Change log

- `2026-09-22T18:28:27.318562+00:00` — opened
- `2026-09-22T18:28:35.513275+00:00` — resolved (final_answer="shared-registry")
