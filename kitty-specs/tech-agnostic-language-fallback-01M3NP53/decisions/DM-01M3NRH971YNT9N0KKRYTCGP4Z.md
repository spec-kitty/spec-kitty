# Decision Moment `01M3NRH971YNT9N0KKRYTCGP4Z`

- **Mission:** `tech-agnostic-language-fallback-01M3NP53`
- **Origin flow:** `plan`
- **Slot key:** `plan.doctrine.descope-tactics`
- **Input key:** `descope_language_independent_tactics`
- **Status:** `resolved`
- **Created:** `2026-09-29T04:59:56.001168+00:00`
- **Resolved:** `2026-09-29T04:59:58.650008+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How to remediate wrongly-scoped language-independent tactics?

## Options

- New WP, 2 tactics + gate fix
- New WP, all 3 tactics
- File an issue only

## Final answer

New WP, all 3 tactics: remove applies_to_languages from secure-regex, chain-of-responsibility and dependency-hygiene (label language examples, strip in-house repo paths/Sonar ids), close the bias-test scope loophole, drop the stale neutrality allowlist entry, regenerate-graph; accept a rebase against PR #5324.

## Rationale

_(none)_

## Change log

- `2026-09-29T04:59:56.001168+00:00` — opened
- `2026-09-29T04:59:58.650008+00:00` — resolved (final_answer="New WP, all 3 tactics: remove applies_to_languages from secure-regex, chain-of-responsibility and dependency-hygiene (label language examples, strip in-house repo paths/Sonar ids), close the bias-test scope loophole, drop the stale neutrality allowlist entry, regenerate-graph; accept a rebase against PR #5324.")
