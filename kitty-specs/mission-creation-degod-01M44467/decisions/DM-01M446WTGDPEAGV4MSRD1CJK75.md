# Decision Moment `01M446WTGDPEAGV4MSRD1CJK75`

- **Mission:** `mission-creation-degod-01M44467`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.behaviour-change-followups`
- **Input key:** `behaviour_change_scope`
- **Status:** `resolved`
- **Created:** `2026-10-04T19:40:16.269313+00:00`
- **Resolved:** `2026-10-04T19:40:23.117178+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Grounding found behaviour-changing fixes in the protected-mint area: #5676 (occupancy) and #5704 (mint refusal leaves an orphan scaffold). Fold them into this mission or keep them out?

## Options

- Keep out: pin current behaviour, shape the seam, follow-ups tracked
- Fold in #5676 and #5704
- Other

## Final answer

Keep out: pin current behaviour, shape the seam, follow-ups tracked. The operator brief says to fix #5676 only if it is free within a pure move. It is not: refusing a create on an occupied checkout is an observable behaviour change, and landing it before the #5704 hoist would inherit the orphan-blocks-retry defect. Both stay out, and so does #5707 (bias unification). The golden matrix pins today's behaviour (including the #5704 orphan), and the pure decide_protected_mint core gets a facts shape where the occupancy precondition and the pre-scaffold hoist become small, testable follow-up changes.

## Rationale

_(none)_

## Change log

- `2026-10-04T19:40:16.269313+00:00` — opened
- `2026-10-04T19:40:23.117178+00:00` — resolved (final_answer="Keep out: pin current behaviour, shape the seam, follow-ups tracked. The operator brief says to fix #5676 only if it is free within a pure move. It is not: refusing a create on an occupied checkout is an observable behaviour change, and landing it before the #5704 hoist would inherit the orphan-blocks-retry defect. Both stay out, and so does #5707 (bias unification). The golden matrix pins today's behaviour (including the #5704 orphan), and the pure decide_protected_mint core gets a facts shape where the occupancy precondition and the pre-scaffold hoist become small, testable follow-up changes.")
