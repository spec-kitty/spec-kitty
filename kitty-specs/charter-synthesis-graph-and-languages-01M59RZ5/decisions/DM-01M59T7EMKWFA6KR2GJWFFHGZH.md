# Decision Moment `01M59T7EMKWFA6KR2GJWFFHGZH`

- **Mission:** `charter-synthesis-graph-and-languages-01M59RZ5`
- **Origin flow:** `specify`
- **Slot key:** `specify.languages.kotlin-gap`
- **Input key:** `kotlin_gap`
- **Status:** `resolved`
- **Created:** `2026-10-19T10:10:01.491820+00:00`
- **Resolved:** `2026-10-19T10:10:06.177736+00:00`
- **Resolved by:** `stijn-dejongh`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

How does the Mission avoid Kotlin projects losing JVM doctrine (#6444)?

## Options

_(none)_

## Final answer

Retag java-supply-chain and maven-review-checks to jvm in core packs/built-in, re-seed spec-kitty-open-packs from this branch, and bump the core vendor pin in this Mission; build/test tokens map to jvm.

## Rationale

Operator decision 2026-10-19 after the post-spec squad.

## Change log

- `2026-10-19T10:10:01.491820+00:00` — opened
- `2026-10-19T10:10:06.177736+00:00` — resolved (final_answer="Retag java-supply-chain and maven-review-checks to jvm in core packs/built-in, re-seed spec-kitty-open-packs from this branch, and bump the core vendor pin in this Mission; build/test tokens map to jvm.")
