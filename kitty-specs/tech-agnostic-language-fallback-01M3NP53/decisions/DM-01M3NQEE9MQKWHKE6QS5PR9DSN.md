# Decision Moment `01M3NQEE9MQKWHKE6QS5PR9DSN`

- **Mission:** `tech-agnostic-language-fallback-01M3NP53`
- **Origin flow:** `plan`
- **Slot key:** `plan.language.doctrine-vocabulary`
- **Input key:** `doctrine_derived_language_vocabulary`
- **Status:** `resolved`
- **Created:** `2026-09-29T04:40:54.324603+00:00`
- **Resolved:** `2026-09-29T04:40:56.980339+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Doctrine is scoped to languages the detector does not know (go/csharp): how to handle?

## Options

- Doctrine-derived vocabulary
- Accept and document
- Other

## Final answer

Doctrine-derived vocabulary: a language named (whole-word, casefolded) in the languages/frameworks answer counts as recognised when any active doctrine artifact is scoped to it; no hardcoded per-language additions; unknown means no specialist guidance exists.

## Rationale

_(none)_

## Change log

- `2026-09-29T04:40:54.324603+00:00` — opened
- `2026-09-29T04:40:56.980339+00:00` — resolved (final_answer="Doctrine-derived vocabulary: a language named (whole-word, casefolded) in the languages/frameworks answer counts as recognised when any active doctrine artifact is scoped to it; no hardcoded per-language additions; unknown means no specialist guidance exists.")
