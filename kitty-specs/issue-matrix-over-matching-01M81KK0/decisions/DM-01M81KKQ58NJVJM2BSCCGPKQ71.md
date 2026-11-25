# Decision Moment `01M81KKQ58NJVJM2BSCCGPKQ71`

- **Mission:** `issue-matrix-over-matching-01M81KK0`
- **Origin flow:** `specify`
- **Slot key:** `specify.colours.rule`
- **Input key:** `colour_rule`
- **Status:** `resolved`
- **Created:** `2026-11-22T12:27:33.416063+00:00`
- **Resolved:** `2026-11-22T12:27:41.266003+00:00`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

How should hex colour values like #000000 and #112233 be excluded?

## Options

_(none)_

## Final answer

Reject a leading zero in every issue-number pattern, and filter an all-digit hex colour only in CSS declaration form (property: #hex), never by a CSS keyword elsewhere on the line (hand-off on #7808). Backticks stay an allowed prefix.

## Rationale

_(none)_

## Change log

- `2026-11-22T12:27:33.416063+00:00` - opened
- `2026-11-22T12:27:41.266003+00:00` - resolved (final_answer="Reject a leading zero in every issue-number pattern, and filter an all-digit hex colour only in CSS declaration form (property: #hex), never by a CSS keyword elsewhere on the line (hand-off on #7808). Backticks stay an allowed prefix.")
