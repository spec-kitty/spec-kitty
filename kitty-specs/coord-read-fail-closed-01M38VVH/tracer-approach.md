# Tracer — Approach

Mission `coord-read-fail-closed-01M38VVH` (#4959, #4966; epic #5002).

Seam-level fail-closed (operator DM-01M38VWD): `src/mission_runtime/resolution.py` raises a typed
error on an unresolved/unmaterialised coord-topology read; both surfaces (tracer-append writer,
decision-ledger reader) + all audited callers inherit it. Foundational seam-raise lands first,
then surfaces + caller adaptations. ATDD red-first.

## Append log (during implement)
- (planning) seeded.
