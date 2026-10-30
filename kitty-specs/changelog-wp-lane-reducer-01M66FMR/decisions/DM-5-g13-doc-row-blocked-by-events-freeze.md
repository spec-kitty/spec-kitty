# DM-5: G-13 doc-row update blocked by the events-import freeze

## Status
decided

## Decision
Revert the `docs/architecture/event-ledger-writers-and-readers.md` edits from the
mission branch. ADR 2026-10-29-1 D-9 froze that path the day before this mission
started (missed in grounding): it moves to `spec-kitty/spec-kitty-events` with its
history, and the freeze gate (`tests/architectural/test_events_import_frozen.py`)
pins the blob to `c2943d4997a19d10ffd1289e70220ec602f4e3ac`. The WP02 doc-row
update is therefore not landable here without an operator-approved re-pin of
`_FROZEN_OBJECTS` in the same PR (plus the port to spec-kitty-events), or the
change being made in spec-kitty-events after the import.

## Consequences
- The architecture page keeps its pre-#6612 readers-table row and the G-13 entry
  until the events import moves it; the changelog entry (not frozen) and the code
  tests carry the user-facing documentation of the fix.
- The PR body names this in `## Deferred` for the operator: re-pin in this PR
  (approved) or file the doc update against spec-kitty-events.
- No gate was skipped or weakened; the failing gate was resolved by reverting the
  offending change, per the remedy the gate itself prescribes.
