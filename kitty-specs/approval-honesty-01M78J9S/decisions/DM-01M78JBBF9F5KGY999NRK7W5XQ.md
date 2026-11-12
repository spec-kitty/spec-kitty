# Decision Moment `01M78JBBF9F5KGY999NRK7W5XQ`

- **Mission:** `approval-honesty-01M78J9S`
- **Origin flow:** `specify`
- **Slot key:** `reviewer_identity`
- **Input key:** `reviewer_identity`
- **Status:** `resolved`
- **Created:** `2026-11-12T19:04:29.929120+00:00`
- **Resolved:** `2026-11-12T19:04:31.949830+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

What does an approval record when move-task has no reviewer identity?

## Options

_(none)_

## Final answer

Asserted identity or refuse: reviewer = --reviewer/--agent, else the in_review claimant; never git user.name, never a synthetic token. Unforced approval with no identity refuses with a new refusal code. Forced approval records the forcing actor with the existing force-override reference. No events-schema change.

## Rationale

Operator ruling 2026-11-12; null reviewer needs a spec-kitty-events release (ReviewVerdict.reviewer min_length=1 + 4 core validators).

## Change log

- `2026-11-12T19:04:29.929120+00:00` - opened
- `2026-11-12T19:04:31.949830+00:00` - resolved (final_answer="Asserted identity or refuse: reviewer = --reviewer/--agent, else the in_review claimant; never git user.name, never a synthetic token. Unforced approval with no identity refuses with a new refusal code. Forced approval records the forcing actor with the existing force-override reference. No events-schema change.")
