# Decision Moment `01M3NR7QRXJBZXQR1B91XKY3JQ`

- **Mission:** `mixed-lane-authorship-soundness-01M3M7Y0`
- **Origin flow:** `plan`
- **Slot key:** `plan.gate.refuse-escape-hatch`
- **Input key:** `refuse_escape_hatch`
- **Status:** `resolved`
- **Created:** `2026-09-29T04:54:43.229854+00:00`
- **Resolved:** `2026-09-29T04:54:46.191509+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

A mixed-lane REFUSE can be permanent (append-only log: unstamped/straddling/late-cancel windows never clear). What escape hatch ships?

## Options

- Operator-attested override
- Attested window bounds
- Ship now, file it
- Other

## Final answer

Operator-attested override: spec-kitty consolidate --attest-canceled-superseded WPnn --reason '...' records an append-only operator-provenance attestation; for that WP's lane the per-WP check falls back to today's behaviour; FAIL is never overridable; REFUSE text tailored per reason naming the flag.

## Rationale

_(none)_

## Change log

- `2026-09-29T04:54:43.229854+00:00` — opened
- `2026-09-29T04:54:46.191509+00:00` — resolved (final_answer="Operator-attested override: spec-kitty consolidate --attest-canceled-superseded WPnn --reason '...' records an append-only operator-provenance attestation; for that WP's lane the per-WP check falls back to today's behaviour; FAIL is never overridable; REFUSE text tailored per reason naming the flag.")
