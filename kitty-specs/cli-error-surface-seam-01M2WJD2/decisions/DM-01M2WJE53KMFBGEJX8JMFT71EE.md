# Decision Moment `01M2WJE53KMFBGEJX8JMFT71EE`

- **Mission:** `cli-error-surface-seam-01M2WJD2`
- **Origin flow:** `specify`
- **Slot key:** `specify.name-validation.non-ascii-policy`
- **Input key:** `non_ascii_name_policy`
- **Status:** `resolved`
- **Created:** `2026-09-19T10:12:21.235208+00:00`
- **Resolved:** `2026-09-19T10:20:47.930043+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

For specify (#4720): when a mission/feature name contains non-ASCII characters (CJK, Cyrillic, accented Latin, emoji), should the CLI transliterate to ASCII, or reject explicitly with an actionable error?

## Options

- reject-explicitly
- transliterate
- Other

## Final answer

Reject explicitly: fail closed with an actionable error naming the offending value; consistent JSON envelope under --json; no silent transliteration or character drop. Preserve the original name only for human display (friendly_name), never as a storage/slug identifier. Aligns with charter Identifier Safety Rules (ASCII allowlist, deterministic).

## Rationale

_(none)_

## Change log

- `2026-09-19T10:12:21.235208+00:00` — opened
- `2026-09-19T10:20:47.930043+00:00` — resolved (final_answer="Reject explicitly: fail closed with an actionable error naming the offending value; consistent JSON envelope under --json; no silent transliteration or character drop. Preserve the original name only for human display (friendly_name), never as a storage/slug identifier. Aligns with charter Identifier Safety Rules (ASCII allowlist, deterministic).")
