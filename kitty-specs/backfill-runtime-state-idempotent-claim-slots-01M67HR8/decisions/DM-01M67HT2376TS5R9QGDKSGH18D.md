# Decision Moment `01M67HT2376TS5R9QGDKSGH18D`

- **Mission:** `backfill-runtime-state-idempotent-claim-slots-01M67HR8`
- **Origin flow:** `specify`
- **Slot key:** `specify.fix.write-vs-read`
- **Input key:** `fix_layer`
- **Status:** `resolved`
- **Created:** `2026-10-30T23:20:07.015448+00:00`
- **Resolved:** `2026-10-30T23:20:11.635970+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Where should #6689 be fixed: (a) the migration writer, so the minted claim row carries the mission_id meta.json declares; (b) the status reader, so a slug-valued mission_id resolves as absent; (c) the verifier, tolerating a mission_id delta?

## Options

- writer: envelope carries declared mission_id
- reader: treat slug mission_id as absent
- verifier: tolerate mission_id delta

## Final answer

writer: the claim carrier's envelope must carry the mission_id meta.json declares, verbatim (seed id namespace unchanged; reader and lenient-tolerance untouched)

## Rationale

_(none)_

## Change log

- `2026-10-30T23:20:07.015448+00:00` — opened
- `2026-10-30T23:20:11.635970+00:00` — resolved (final_answer="writer: the claim carrier's envelope must carry the mission_id meta.json declares, verbatim (seed id namespace unchanged; reader and lenient-tolerance untouched)")
