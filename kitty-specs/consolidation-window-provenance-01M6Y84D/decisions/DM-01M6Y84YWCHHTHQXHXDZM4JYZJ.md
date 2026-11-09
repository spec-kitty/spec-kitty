# Decision Moment `01M6Y84YWCHHTHQXHXDZM4JYZJ`

- **Mission:** `consolidation-window-provenance-01M6Y84D`
- **Origin flow:** `specify`
- **Slot key:** `specify.provenance.window-unification`
- **Input key:** `window_unification`
- **Status:** `resolved`
- **Created:** `2026-11-08T18:53:50.348203+00:00`
- **Resolved:** `2026-11-08T18:53:51.672642+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

What does the ADR do with the 6 window definitions and 3 claim-input variants?

## Options

- One ClaimInputs + named variants
- Full unification now
- Document only
- Other

## Final answer

One ClaimInputs constructor with three sources (live/forecast, live+saved/fresh run, saved/resume) and one window model whose deliberate variants are named

## Rationale

_(none)_

## Change log

- `2026-11-08T18:53:50.348203+00:00` - opened
- `2026-11-08T18:53:51.672642+00:00` - resolved (final_answer="One ClaimInputs constructor with three sources (live/forecast, live+saved/fresh run, saved/resume) and one window model whose deliberate variants are named")
