# Decision Moment `01M2XQGD3YXMYXE0ZB194RM0KE`

- **Mission:** `merge-destructive-op-safety-01M2XQF8`
- **Origin flow:** `specify`
- **Slot key:** `specify.approach.guard-strategy`
- **Input key:** `guard_strategy`
- **Status:** `resolved`
- **Created:** `2026-09-19T21:00:12.286500+00:00`
- **Resolved:** `2026-09-19T21:00:18.769332+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Should the three destructive-op bugs be fixed by unifying one refuse-before-destroy guard primitive, or by patching each site independently?

## Options

- Unify a shared guard primitive
- Patch each of the three sites independently

## Final answer

Unify a shared refuse-before-destroy guard primitive (modeled on git/ref_advance._dirty_entries + a typed RefAdvance-style refusal), routed through the destructive sites. Grounding squad found ~9 forked dirty-check predicates with no canonical owner (file-lock-authority-gap-shaped); patch-3 would mint a 10th and guarantee the next whack-a-field. Operator-delegated answer from grounding findings.

## Rationale

_(none)_

## Change log

- `2026-09-19T21:00:12.286500+00:00` — opened
- `2026-09-19T21:00:18.769332+00:00` — resolved (final_answer="Unify a shared refuse-before-destroy guard primitive (modeled on git/ref_advance._dirty_entries + a typed RefAdvance-style refusal), routed through the destructive sites. Grounding squad found ~9 forked dirty-check predicates with no canonical owner (file-lock-authority-gap-shaped); patch-3 would mint a 10th and guarantee the next whack-a-field. Operator-delegated answer from grounding findings.")
