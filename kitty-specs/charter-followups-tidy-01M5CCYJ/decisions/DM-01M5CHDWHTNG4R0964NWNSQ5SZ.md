# Decision Moment `01M5CHDWHTNG4R0964NWNSQ5SZ`

- **Mission:** `charter-followups-tidy-01M5CCYJ`
- **Origin flow:** `specify`
- **Slot key:** `specify.seam.language-export-shape`
- **Input key:** `seam_language_export_shape`
- **Status:** `resolved`
- **Created:** `2026-10-20T11:33:58.458367+00:00`
- **Resolved:** `2026-10-20T11:34:02.332674+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

#6541: LANGUAGES is a tuple of LanguageSpec (families, regexes, rank). What goes on charter.offering.api?

## Options

- Token tuple only
- LANGUAGES as-is
- Other

## Final answer

Token tuple only: export a derived read-only LANGUAGE_TOKENS tuple[str, ...] declared in the catalog; LanguageSpec, families and regexes stay internal.

## Rationale

_(none)_

## Change log

- `2026-10-20T11:33:58.458367+00:00` — opened
- `2026-10-20T11:34:02.332674+00:00` — resolved (final_answer="Token tuple only: export a derived read-only LANGUAGE_TOKENS tuple[str, ...] declared in the catalog; LanguageSpec, families and regexes stay internal.")
