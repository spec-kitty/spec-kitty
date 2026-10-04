# Decision Moment `01M42ZJNERKY2TB1RPKF2GJ0GT`

- **Mission:** `consolidation-god-module-decomposition-01M42Z57`
- **Origin flow:** `specify`
- **Slot key:** `specify.tests.monkeypatch_policy`
- **Input key:** `monkeypatch_policy`
- **Status:** `resolved`
- **Created:** `2026-10-04T08:13:08.952940+00:00`
- **Resolved:** `2026-10-04T08:13:29.263451+00:00`
- **Opened by:** `claude`
- **Other answer:** `true`

## Question

How are test monkeypatches on executor attributes handled after the move?

## Options

- Re-point each patch to every module that now looks the name up (same interception set); no back-compat re-export aliases
- Keep re-export aliases in executor so old patch strings resolve
- Other

## Final answer

Re-point each patch to every module that now looks the name up, computed from the AST so the interception set is unchanged; no back-compat aliases kept only for patch strings (brief §3: re-pointing imports and monkeypatch targets is fine).

## Rationale

_(none)_

## Change log

- `2026-10-04T08:13:08.952940+00:00` — opened
- `2026-10-04T08:13:29.263451+00:00` — resolved (final_answer="Re-point each patch to every module that now looks the name up, computed from the AST so the interception set is unchanged; no back-compat aliases kept only for patch strings (brief §3: re-pointing imports and monkeypatch targets is fine).")
