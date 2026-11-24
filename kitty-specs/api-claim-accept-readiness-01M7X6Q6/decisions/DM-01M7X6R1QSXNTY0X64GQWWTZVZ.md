# Decision Moment `01M7X6R1QSXNTY0X64GQWWTZVZ`

- **Mission:** `api-claim-accept-readiness-01M7X6Q6`
- **Origin flow:** `specify`
- **Step id:** `intent_scope`
- **Input key:** `intent_scope`
- **Status:** `resolved`
- **Created:** `2026-11-20T19:25:46.105059+00:00`
- **Resolved:** `2026-11-20T19:25:53.203818+00:00`
- **Opened by:** `claude::python-pedro`
- **Other answer:** `false`

## Question

What must change so an API-claimed or never-claimed-canceled Mission reaches acceptance?

## Options

_(none)_

## Final answer

Operator rulings 2026-11-20 (binding): (1) strict accept gate reads the implementer from status/review_roles; (2) the API claim records agent=--actor through the shared claim-sidecar builder, also API transition --to claimed and agent status emit --to claimed; (3) a canceled WP with no claim history needs no implementer, never fabricated; (4) the repair hint names a command that works from that state, derived from the state machine, else no hint, and a test runs it; (5) fold #5818: accept-mission uses the provenance-aware acceptable-ending predicate; (6) fold #7644: API --to planned releases the claim slots; (7) #7752 only if a shared canceled helper falls out (it does not); (8) #5782 sequenced after.

## Rationale

_(none)_

## Change log

- `2026-11-20T19:25:46.105059+00:00` - opened
- `2026-11-20T19:25:53.203818+00:00` - resolved (final_answer="Operator rulings 2026-11-20 (binding): (1) strict accept gate reads the implementer from status/review_roles; (2) the API claim records agent=--actor through the shared claim-sidecar builder, also API transition --to claimed and agent status emit --to claimed; (3) a canceled WP with no claim history needs no implementer, never fabricated; (4) the repair hint names a command that works from that state, derived from the state machine, else no hint, and a test runs it; (5) fold #5818: accept-mission uses the provenance-aware acceptable-ending predicate; (6) fold #7644: API --to planned releases the claim slots; (7) #7752 only if a shared canceled helper falls out (it does not); (8) #5782 sequenced after.")
