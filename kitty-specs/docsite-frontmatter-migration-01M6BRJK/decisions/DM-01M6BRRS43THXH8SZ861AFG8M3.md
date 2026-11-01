# Decision Moment `01M6BRRS43THXH8SZ861AFG8M3`

- **Mission:** `docsite-frontmatter-migration-01M6BRJK`
- **Origin flow:** `specify`
- **Slot key:** `specify.audience.guidance-text`
- **Input key:** `audience_guidance_text`
- **Status:** `resolved`
- **Created:** `2026-11-01T14:38:42.819609+00:00`
- **Resolved:** `2026-11-01T14:39:16.587833+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

doc-kitty requires a guidance_text on every audience entry, and the current path-string audience carries none. What should the mechanical migration write?

## Options

- Persona-derived sentence: Written for the <persona title> reader.
- Copy the page description
- Leave for #6931 with an empty string
- Other

## Final answer

Persona-derived sentence: 'Written for the <persona page title> reader.' (free-text values keep their text as the profile with 'Written for <value>.'). Mechanical and honest; page-specific guidance is authoring work for #6931. Autonomous run default, flagged for the operator in the PR.

## Rationale

_(none)_

## Change log

- `2026-11-01T14:38:42.819609+00:00` — opened
- `2026-11-01T14:39:16.587833+00:00` — resolved (final_answer="Persona-derived sentence: 'Written for the <persona page title> reader.' (free-text values keep their text as the profile with 'Written for <value>.'). Mechanical and honest; page-specific guidance is authoring work for #6931. Autonomous run default, flagged for the operator in the PR.")
