# Decision Moment `01M2TPY0RC30KYGC27EDJ77F7H`

- **Mission:** `mission-handle-resolution-consistency-01M2TPWG`
- **Origin flow:** `specify`
- **Slot key:** `specify.listing.handle-legibility`
- **Input key:** `mission_listing_fields`
- **Status:** `resolved`
- **Created:** `2026-09-18T16:52:26.508836+00:00`
- **Resolved:** `2026-09-18T17:21:35.672366+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

When a command lists available missions (bare next with >1 mission), what should each entry show?

## Options

- mission_slug only
- slug + mid8 + friendly_name
- Other

## Final answer

Listing entries show slug + mid8 + friendly_name (friendly_name read from meta.json), directly addressing the opaque-ULID legibility complaint.

## Rationale

_(none)_

## Change log

- `2026-09-18T16:52:26.508836+00:00` — opened
- `2026-09-18T17:21:35.672366+00:00` — resolved (final_answer="Listing entries show slug + mid8 + friendly_name (friendly_name read from meta.json), directly addressing the opaque-ULID legibility complaint.")
