# Decision Moment `01M3NSKHE8T6TBKNFPSJ6BRD2G`

- **Mission:** `requirement-id-grammar-01M3NRCA`
- **Origin flow:** `specify`
- **Slot key:** `specify.storage.on-disk-form`
- **Input key:** `on_disk_form`
- **Status:** `resolved`
- **Created:** `2026-09-29T05:18:38.536382+00:00`
- **Resolved:** `2026-09-29T05:18:40.007548+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

What do finalize-tasks and map-requirements write back for existing authored refs?

## Options

- Never rewrite existing
- Canonicalise well-formed
- Other

## Final answer

Never rewrite existing: finalize never rewrites an item; map-requirements writes added refs canonical, keeps existing byte-identical, dedups by canonical form

## Rationale

_(none)_

## Change log

- `2026-09-29T05:18:38.536382+00:00` — opened
- `2026-09-29T05:18:40.007548+00:00` — resolved (final_answer="Never rewrite existing: finalize never rewrites an item; map-requirements writes added refs canonical, keeps existing byte-identical, dedups by canonical form")
