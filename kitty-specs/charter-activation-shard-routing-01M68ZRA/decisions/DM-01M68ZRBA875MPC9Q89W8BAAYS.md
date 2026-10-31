# Decision Moment `01M68ZRBA875MPC9Q89W8BAAYS`

- **Mission:** `charter-activation-shard-routing`
- **Origin flow:** `specify`
- **Step id:** `specify.problem_statement`
- **Input key:** `problem_statement`
- **Status:** `resolved`
- **Created:** `2026-10-31T12:43:05.416291+00:00`
- **Resolved:** `2026-10-31T12:44:34.272931+00:00`
- **Opened by:** `22272470+Ivan-Melck@users.noreply.github.com`
- **Other answer:** `false`

## Question

What problem does this Mission solve?

## Options

_(none)_

## Final answer

An activation-store (.kittify/charter/charter.yaml, .kittify/charter/activation.yaml) or internal-pack-pin (packs/internal.source.yaml) edit selects no CI module today, so the charter shard's config-parity tests never run and a parity-breaking activation can land green on main (#6333). #6334 refused to append those non-src paths to the charter filter group because its globs are a verbatim transcription of the scrub roots; this mission registers a new NON-src group and fans it out to the charter module.

## Rationale

_(none)_

## Change log

- `2026-10-31T12:43:05.416291+00:00` — opened
- `2026-10-31T12:44:34.272931+00:00` — resolved (final_answer="An activation-store (.kittify/charter/charter.yaml, .kittify/charter/activation.yaml) or internal-pack-pin (packs/internal.source.yaml) edit selects no CI module today, so the charter shard's config-parity tests never run and a parity-breaking activation can land green on main (#6333). #6334 refused to append those non-src paths to the charter filter group because its globs are a verbatim transcription of the scrub roots; this mission registers a new NON-src group and fans it out to the charter module.")
