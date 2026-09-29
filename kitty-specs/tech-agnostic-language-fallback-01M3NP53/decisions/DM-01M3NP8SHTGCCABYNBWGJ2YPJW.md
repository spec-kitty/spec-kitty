# Decision Moment `01M3NP8SHTGCCABYNBWGJ2YPJW`

- **Mission:** `tech-agnostic-language-fallback-01M3NP53`
- **Origin flow:** `specify`
- **Slot key:** `specify.charter.stale-languages-reset`
- **Input key:** `stale_languages_reset`
- **Status:** `resolved`
- **Created:** `2026-09-29T04:20:20.666202+00:00`
- **Resolved:** `2026-09-29T04:20:23.373586+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How should a corrected interview answer take effect on an existing charter (#4614)?

## Options

- --from-interview re-derives
- Newer answers.yaml wins
- Explicit reset flag
- Other

## Final answer

--from-interview re-derives: only charter generate --from-interview derives languages from the fresh interview; runtime readers keep compiled-first precedence; activate/pack recompiles preserve the recorded value.

## Rationale

_(none)_

## Change log

- `2026-09-29T04:20:20.666202+00:00` — opened
- `2026-09-29T04:20:23.373586+00:00` — resolved (final_answer="--from-interview re-derives: only charter generate --from-interview derives languages from the fresh interview; runtime readers keep compiled-first precedence; activate/pack recompiles preserve the recorded value.")
