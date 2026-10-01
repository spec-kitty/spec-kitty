# Decision Moment `01M3V027T8WF0CR3D1B8VY2VZ0`

- **Mission:** `ci-runtime-stabilisation-01M3TZH6`
- **Origin flow:** `specify`
- **Slot key:** `specify.ci.corpus-owner`
- **Input key:** `corpus_owner`
- **Status:** `resolved`
- **Created:** `2026-10-01T05:47:43.816998+00:00`
- **Resolved:** `2026-10-01T05:47:45.357127+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Router tests(corpus) feeds the required router gate; Packs is not required. Who owns the corpus suite?

## Options

- Router owns, drop Packs copy
- Packs owns, make it required
- Packs owns, accept non-blocking
- Other

## Final answer

Packs owns, accept non-blocking (corpus failures become advisory; Packs triggers must cover every path the Router corpus job triggered on)

## Rationale

_(none)_

## Change log

- `2026-10-01T05:47:43.816998+00:00` — opened
- `2026-10-01T05:47:45.357127+00:00` — resolved (final_answer="Packs owns, accept non-blocking (corpus failures become advisory; Packs triggers must cover every path the Router corpus job triggered on)")
