# Decision Moment `01M3X64DEKX8WVRZWSDQTDE0P1`

- **Mission:** `coord-artifact-single-home-01M3V4BE`
- **Origin flow:** `plan`
- **Slot key:** `plan.design.review-cycle-read-fallback`
- **Input key:** `review_cycle_read_fallback`
- **Status:** `resolved`
- **Created:** `2026-10-02T02:12:15.443237+00:00`
- **Resolved:** `2026-10-02T02:12:16.921984+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

After WP08 moves review-cycle writes to the coordination surface, how do readers (review-cycle:// pointer, has_prior_rejection, fix mode) find a rejection recorded before WP08 in local-only mode that lives only in the PRIMARY checkout?

## Options

_(none)_

## Final answer

Readers resolve the coordination copy first and fall back to the PRIMARY copy (read-only) when the coordination copy is absent — consistent with C-002 (read-side fallback kept). Writes never go to PRIMARY. Prevents has_prior_rejection / fix mode failing open for pre-WP08 local-only rejection cycles. Pinned by a test with a PRIMARY-only cycle file.

## Rationale

_(none)_

## Change log

- `2026-10-02T02:12:15.443237+00:00` — opened
- `2026-10-02T02:12:16.921984+00:00` — resolved (final_answer="Readers resolve the coordination copy first and fall back to the PRIMARY copy (read-only) when the coordination copy is absent — consistent with C-002 (read-side fallback kept). Writes never go to PRIMARY. Prevents has_prior_rejection / fix mode failing open for pre-WP08 local-only rejection cycles. Pinned by a test with a PRIMARY-only cycle file.")
