---
title: 'ADR: mission-state repair inverts non-lane preservation to preserve-by-default'
description: "Inverts mission-state repair's non-lane row preservation from a registry allowlist to preserve-by-default with an empty denylist, closing the #4897 whack-a-field class."
status: Accepted
date: '2026-09-23'
---

## Context and Problem Statement

`spec-kitty doctor mission-state --fix` canonicalizes `status.events.jsonl`, a *shared*
append-only log. Lane-transition rows are flat (`wp_id` / `from_lane` / `to_lane`); other
subsystems co-locate rows carrying `event_type` / `type` / `kind` discriminators
(canonical lifecycle events, Decision-Moment `DecisionPoint*` events, retrospective
lifecycle events, `InnerStateChanged` annotations). The durable runtime reader,
`specify_cli.status.store.is_non_lane_event`, is **presence-permissive**: after its
annotation / retrospective / registry branches, its catch-all is `return "event_type" in
obj` — it treats ANY row carrying `event_type` as non-lane, regardless of whether that
specific value has ever been seen before.

Before this ADR, the mutating repair's preservation predicate,
`migration/mission_state.py::_is_preserved_non_lane_row`, was a **registry ALLOWLIST**: it
preserved a row only if its `event_type` was a member of
`specify_cli.status.lifecycle_events.AUTHORITATIVE_NON_LANE_EVENT_TYPES` (or matched one of
three other explicitly-enumerated shapes). Any `event_type` outside that list — including
one written by a *future* subsystem before anyone remembered to add it to the registry —
was routed to `quarantined_non_status_event` and dropped, with the repair reporting a
silent, non-error `status="updated"` / `errors=0` success.

This is the fourth occurrence of the same recurring defect shape ("the repair's
classifier diverges from the reader's classifier, so a row the reader treats as legitimate
non-lane data is silently pruned"):

- **#2376** — retrospective `event_name` rows were dropped.
- **#3066** — a legacy typed `WPStatusChanged` lane row was dropped, regenerating a
  **zero-WP** `status.json` (a data-destroying "successful" repair).
- **#3541** — `review_result`, a nested field on a lane row, was dropped.
- **#4897** — `DecisionPoint*` rows were dropped on the INVERTED belief that
  `decisions/index.json` was their canonical store; in truth `decisions/index_fold.py`
  rebuilds `index.json` FROM this log, so the log is the decision's only durable
  per-mission home.

Each prior fix added the missing case to the registry/allowlist — a **whack-a-field**
pattern: it closes the *symptom* for the one type that was reported, but leaves the
*mechanism* — a hand-maintained allowlist that must independently track every past and
future writer of this shared file — in place. Any future subsystem that starts writing
its own `event_type` to `status.events.jsonl` reopens the same defect on day one, before
anyone can add it to the registry.

An empirical writer census of `status.events.jsonl` found that **every** `event_type` ever
written to this file is either (a) a lane transition (the legacy typed `WPStatusChanged`
writer shape, handled by a dedicated passthrough — see below), or (b) a canonical record
whose *sole* per-mission home is this log (lifecycle / DecisionPoint / retrospective).
Derived folds such as `decisions/index.json` are separate files rebuilt FROM the log, never
rows inside it. There is, empirically, no `event_type`-bearing row in this file that is a
disposable mirror of a copy stored elsewhere.

## Decision

**Invert `_is_preserved_non_lane_row` from a registry allowlist to preserve-by-default,
delegating classification to the durable reader, with an explicit, empty denylist of
genuinely disposable mirrors.**

Formally:

```text
preserved(row) := (row["kind"] == ANNOTATION_KIND)
                   or (is_non_lane_event(row) and row["event_type"] not in PRUNABLE_MIRROR_EVENT_TYPES)
```

- `is_non_lane_event` is imported from the durable reader
  (`specify_cli.status.store`, re-exported on the `specify_cli.status` facade) rather than
  re-implemented. The repair's preserved set is now equal to the reader's non-lane set *by
  construction*, not by two hand-maintained classifiers kept in lock-step by convention —
  the mechanism that generated all four prior incidents.
- The annotation clause is the **only** intended divergence from the reader: the reader
  returns `False` for `kind: "annotation"` rows so they route to their own read path
  (`InnerStateChanged.from_dict`, not `StatusEvent.from_dict`); the repair must return
  `True` for the same rows to keep them on disk (they carry no `from_lane`/`to_lane` by
  construction and would otherwise hard-error the whole mission repair).
- `PRUNABLE_MIRROR_EVENT_TYPES` is a new, named, documented `frozenset[str]` constant in
  `migration/mission_state.py`. **It is empty.** Per the census above, no `event_type` this
  repair has ever encountered is a safe-to-prune mirror. Adding a member is a deliberate,
  individually-reviewed decision that a *specific* type's copy in this file is disposable —
  never a place to route a future symptom fix.
- The legacy typed `WPStatusChanged` lane-transition passthrough
  (`_is_legacy_typed_lane_transition`, requiring top-level `wp_id`/`from_lane`/`to_lane`)
  is evaluated **FIRST**, before the preserve-by-default check, in
  `_rule_reject_non_status_event`. This is unchanged and load-bearing: without it, a
  legacy typed lane row would be preserved verbatim instead of canonicalized into
  `status.json`, reopening #3066's zero-WP regeneration.
- The fail-closed backstop guard, `_registry_authoritative_quarantine_violations`, is
  strengthened from "no *registry-member* row was quarantined" to a genuine
  **reader == repair invariant**: it now flags any quarantined line for which
  `is_non_lane_event(obj)` is `True`, not merely `"event_type" in obj` (which would miss
  the retrospective `event_name`-envelope class, which carries no `event_type` at all).
  The pre-existing #4938 duplicate-`event_id` carve-out (a quarantined row whose
  byte-identical survivor already reached `canonical_rows` is a benign dedup, not data
  loss) is preserved unchanged.

### Behavioral change

| Row shape | Before | After |
| --- | --- | --- |
| `event_type` registered in `AUTHORITATIVE_NON_LANE_EVENT_TYPES` | preserved | preserved (unchanged) |
| `event_type` NOT registered (a future/unknown type) | quarantined, dropped, silent success | **preserved** |
| Legacy typed `WPStatusChanged` lane row (top-level lane fields) | passthrough → canonicalized | passthrough → canonicalized (unchanged, #3066 invariant) |
| TeamSpace `WPStatusChanged` replay envelope (lane fields nested under `payload`) | quarantined | **preserved verbatim** — safe: the reader already treated it as non-lane via the same catch-all; the repair now aligns with the reader instead of diverging from it |
| Partial-field `WPStatusChanged` (e.g. missing `from_lane`; a corruption shape no writer emits) | quarantined | **preserved, retained-but-inert** — an accepted fail-closed-toward-retention tradeoff |
| Non-retrospective `event_name`-only row, no `event_type` | quarantined | quarantined (unchanged — "genuinely non-status") |
| Quarantined row the reader treats as non-lane, with a duplicate-`event_id` survivor already in `canonical_rows` | not flagged (#4938 carve-out) | not flagged (unchanged) |

After this change, `--fix` prunes **only** rows the durable reader itself does not
recognize as legitimate shared-log content: a bare, non-retrospective `event_name` row
with no `event_type`, or a row with neither discriminator that also fails the lane-row
requirements. Every `event_type`-bearing row — registered or not — now survives.

## Consequences

**Positive:**

- Closes the #2376 → #3066 → #3541 → #4897 whack-a-field class **at the root**: a future
  subsystem that starts writing a new `event_type` to `status.events.jsonl` is preserved
  by the repair from day one, with no registry update required and no silent data loss
  window between "a subsystem starts writing" and "someone remembers to register the
  type."
- `_scan_raw_status_rows` (the TeamSpace dry-run pre-flight scanner) shares
  `_is_preserved_non_lane_row`, so it is corrected by the same edit with no second site to
  maintain.
- The fail-closed guard now catches the exact defect class in the future, rather than only
  a registry-scoped subset of it.

**Trade-offs / accepted tradeoffs:**

- A TeamSpace `WPStatusChanged` replay envelope now survives repair verbatim instead of
  being quarantined. This is judged safe (the reader already treated it as non-lane), but
  it means the repair no longer prunes that specific test/replay artifact shape from a
  mission's log.
- A partial-field, corrupted `WPStatusChanged` row (a shape no known writer emits) is now
  preserved rather than flagged — retained-but-inert, since the lane reducer also skips it
  via the same reader contract. This is fail-closed toward retention, consistent with the
  mission's C-003 constraint, rather than toward deletion.
- `PRUNABLE_MIRROR_EVENT_TYPES` is a new governance surface: a future contributor who
  believes a specific `event_type`'s copy in this file IS a safe-to-prune mirror must add
  it there explicitly and update this ADR's rationale, rather than silently reverting to
  an allowlist-shaped fix.

## Alternatives Considered

- **Add the next missing type to the registry.** Rejected — this is the whack-a-field
  pattern the mission exists to end; it closes only the one reported symptom.
- **A non-empty denylist naming `DecisionPoint*`/lifecycle types as "mirrors."** Rejected
  — the writer census proves these are canonical, sole-per-mission-home records, not
  mirrors; naming them in a denylist would reintroduce the exact #4897 defect.
- **Conservative interim: strengthen the guard only, keep the allowlist pruning
  behavior.** Rejected by operator decision — the guard alone would only ever *detect* a
  future occurrence of this class after the fact (as a hard error), not *prevent* the data
  loss; shipping the full inversion this mission was scoped for closes the class instead
  of merely alarming on it.

## References

- Mission `kitty-specs/silent-write-hardening-residuals-01M37QN4/`: `research.md`
  (Finding A), `contracts/repair-preservation-contract.md`.
- `src/specify_cli/migration/mission_state.py`: `_is_preserved_non_lane_row`,
  `PRUNABLE_MIRROR_EVENT_TYPES`, `_registry_authoritative_quarantine_violations`,
  `_is_legacy_typed_lane_transition`, `_rule_reject_non_status_event`.
- `src/specify_cli/status/store.py::is_non_lane_event` (the durable-reader reference
  contract), re-exported via `src/specify_cli/status/__init__.py`.
- Prior incidents: #2376, #3066, #3541, #4897; PR #4938 (duplicate-`event_id` carve-out).
- This mission: #4993.
- Regression coverage: `tests/status/test_authoritative_non_lane_registry_4897.py`,
  `tests/migration/test_mission_state_repair.py`,
  `tests/integration/migration/test_lifecycle_events_preserved.py`,
  `tests/unit/migration/test_canonicalization_rules.py`.
