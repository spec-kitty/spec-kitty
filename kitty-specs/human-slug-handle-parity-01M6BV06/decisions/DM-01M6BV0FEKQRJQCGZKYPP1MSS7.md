# Decision Moment `01M6BV0FEKQRJQCGZKYPP1MSS7`

- **Mission:** `human-slug-handle-parity-01M6BV06`
- **Origin flow:** `specify`
- **Step id:** `specify`
- **Input key:** `intent-summary`
- **Status:** `resolved`
- **Created:** `2026-11-01T15:17:52.211123+00:00`
- **Resolved:** `2026-11-01T15:17:58.851312+00:00`
- **Resolved by:** `Ivan-Melck`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

Which handle policy should #6278 adopt: the identity resolver learns the human slug (option A, keeps the shipped agent tasks status behavior) or the human slug is refused everywhere (option B)?

## Options

- A: identity resolver learns the human slug, folding only the mission's own mid8, with loud ambiguity refusal
- B: refuse the human slug on every command

## Final answer

A: identity resolver learns the human slug, folding only the mission's own mid8, with loud ambiguity refusal

## Rationale

Operator intent recorded in issue #6278 (first option). The human slug is already a supported, documented handle on agent tasks status / agent status; refusing it everywhere would remove shipped behavior and leave the same split in the other direction. Folding in the shared ladder fixes implement and every other resolve_mission caller at once.

## Change log

- `2026-11-01T15:17:52.211123+00:00` — opened
- `2026-11-01T15:17:58.851312+00:00` — resolved (final_answer="A: identity resolver learns the human slug, folding only the mission's own mid8, with loud ambiguity refusal")
