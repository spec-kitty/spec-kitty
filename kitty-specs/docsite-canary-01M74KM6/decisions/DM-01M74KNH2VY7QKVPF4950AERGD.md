# Decision Moment `01M74KNH2VY7QKVPF4950AERGD`

- **Mission:** `docsite-canary-01M74KM6`
- **Origin flow:** `specify`
- **Slot key:** `specify.rules.invariants`
- **Input key:** `invariants`
- **Status:** `resolved`
- **Created:** `2026-11-11T06:10:34.203222+00:00`
- **Resolved:** `2026-11-11T06:10:36.393316+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

What must always hold?

## Options

_(none)_

## Final answer

The non-canary push and dispatch path stays DocFX behaviour; deploy stays main-only and core-repository-only; the Pages probe-then-configure job stays; the canary never leaves the doc-kitty site live (DocFX always redeployed); the cutover is a later PR B and not done here. Answered from the operator brief.

## Rationale

_(none)_

## Change log

- `2026-11-11T06:10:34.203222+00:00` - opened
- `2026-11-11T06:10:36.393316+00:00` - resolved (final_answer="The non-canary push and dispatch path stays DocFX behaviour; deploy stays main-only and core-repository-only; the Pages probe-then-configure job stays; the canary never leaves the doc-kitty site live (DocFX always redeployed); the cutover is a later PR B and not done here. Answered from the operator brief.")
