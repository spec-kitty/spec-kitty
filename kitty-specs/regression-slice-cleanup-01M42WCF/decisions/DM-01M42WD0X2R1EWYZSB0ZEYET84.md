# Decision Moment `01M42WD0X2R1EWYZSB0ZEYET84`

- **Mission:** `regression-slice-cleanup-01M42WCF`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.verdict-source`
- **Input key:** `verdict_source`
- **Status:** `resolved`
- **Created:** `2026-10-04T07:17:38.338246+00:00`
- **Resolved:** `2026-10-04T07:17:41.094591+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which verdicts govern the change set, and what is out of scope?

## Options

- Apply issue ledgers #5618-#5622 verbatim, test-only
- Re-derive verdicts
- Other

## Final answer

Apply the per-file ledger verdicts from issues #5618-#5622 (operator brief, non-interactive host): MARKER-ONLY, SPLIT-BY-KIND, SHIFT-LEFT with seam units first, RETIRE only after a planted break re-proves the covering guard, FIX weak oracles; #5620 item 1 is priority; #5622 root-independence. Test-only; product defects found become issues; p0_repro marker work out of scope.

## Rationale

_(none)_

## Change log

- `2026-10-04T07:17:38.338246+00:00` — opened
- `2026-10-04T07:17:41.094591+00:00` — resolved (final_answer="Apply the per-file ledger verdicts from issues #5618-#5622 (operator brief, non-interactive host): MARKER-ONLY, SPLIT-BY-KIND, SHIFT-LEFT with seam units first, RETIRE only after a planted break re-proves the covering guard, FIX weak oracles; #5620 item 1 is priority; #5622 root-independence. Test-only; product defects found become issues; p0_repro marker work out of scope.")
