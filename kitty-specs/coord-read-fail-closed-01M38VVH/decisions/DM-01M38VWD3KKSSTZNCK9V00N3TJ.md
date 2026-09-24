# Decision Moment `01M38VWD3KKSSTZNCK9V00N3TJ`

- **Mission:** `coord-read-fail-closed-01M38VVH`
- **Origin flow:** `specify`
- **Slot key:** `specify.contract.fail-closed-locus`
- **Input key:** `fail_closed_locus`
- **Status:** `resolved`
- **Created:** `2026-09-24T04:48:18.547992+00:00`
- **Resolved:** `2026-09-24T04:59:47.903664+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Where should the fail-closed contract for an unresolved/unmaterialised coord read live: at the placement read seam itself (resolution.py raises), or at each reader (they honour the PRIMARY/coord stamp and refuse)?

## Options

- Seam-level: resolution.py raises on unresolved/unmaterialised coord reads (both surfaces + all future readers inherit it; broader blast radius across seam callers)
- Reader-level: each reader checks the stamp/result and fails closed itself (localized, smaller blast radius; future readers not auto-protected)
- Hybrid: seam exposes an explicit unresolved/empty signal readers MUST handle; keep NONE raising, make UNMATERIALIZED a typed signal not a silent empty
- Other

## Final answer

Seam-level: the placement read seam (src/mission_runtime/resolution.py) raises a typed error on an unresolved/unmaterialised coord read (it already raises CoordinationBranchDeleted on NONE; extend that fail-closed posture to UNMATERIALIZED instead of returning empty PRIMARY on a coord-topology mission). Both surfaces (tracer-append writer, decision-ledger reader) and any future reader inherit fail-closed by construction. Mandatory blast-radius consequence: audit every caller of the read seam so each handles the raise correctly (refuse/materialise/resolve-to-authoritative) and none swallows it or is a non-coord caller that must keep working. NONE keeps raising; non-coord topologies (SINGLE_BRANCH/LANES route to primary) are unaffected.

## Rationale

_(none)_

## Change log

- `2026-09-24T04:48:18.547992+00:00` — opened
- `2026-09-24T04:59:47.903664+00:00` — resolved (final_answer="Seam-level: the placement read seam (src/mission_runtime/resolution.py) raises a typed error on an unresolved/unmaterialised coord read (it already raises CoordinationBranchDeleted on NONE; extend that fail-closed posture to UNMATERIALIZED instead of returning empty PRIMARY on a coord-topology mission). Both surfaces (tracer-append writer, decision-ledger reader) and any future reader inherit fail-closed by construction. Mandatory blast-radius consequence: audit every caller of the read seam so each handles the raise correctly (refuse/materialise/resolve-to-authoritative) and none swallows it or is a non-coord caller that must keep working. NONE keeps raising; non-coord topologies (SINGLE_BRANCH/LANES route to primary) are unaffected.")
