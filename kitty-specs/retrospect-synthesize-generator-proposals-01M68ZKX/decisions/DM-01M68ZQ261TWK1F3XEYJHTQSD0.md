# Decision Moment `01M68ZQ261TWK1F3XEYJHTQSD0`

- **Mission:** `retrospect-synthesize-generator-proposals-01M68ZKX`
- **Origin flow:** `specify`
- **Step id:** `discovery`
- **Input key:** `input:discovery`
- **Status:** `resolved`
- **Created:** `2026-10-31T12:42:23.297345+00:00`
- **Resolved:** `2026-10-31T12:42:27.794277+00:00`
- **Resolved by:** `Ivan-Melck`
- **Opened by:** `pi`
- **Other answer:** `false`

## Question

Scope confirmation for #6385: which half of the create->synthesize gap does this Mission deliver, and how does synthesize stop being a silent no-op without changing the documented exit-code contract?

## Options

_(none)_

## Final answer

Application/reporting half only (generation stays in #3947): generator-shape proposals gain an optional structured payload validated by the existing ProposalPayload union, synthesize translates translatable ones into the typed Proposal it applies, names every untranslatable one, and emits a diagnostics block naming record shape, finding counts and zero planned; exit codes stay unchanged so the documented dry-run exit-0 contract holds.

## Rationale

Batch-14 triage on #6385 splits generation (#3947) from application/reporting; the issue itself names a structured field as the safer direction than verb parsing, and its Minimum bar is that a created record with findings must not end in a silent successful-looking empty batch. Changing the documented exit code would be a contract change on a P2 fix.

## Change log

- `2026-10-31T12:42:23.297345+00:00` — opened
- `2026-10-31T12:42:27.794277+00:00` — resolved (final_answer="Application/reporting half only (generation stays in #3947): generator-shape proposals gain an optional structured payload validated by the existing ProposalPayload union, synthesize translates translatable ones into the typed Proposal it applies, names every untranslatable one, and emits a diagnostics block naming record shape, finding counts and zero planned; exit codes stay unchanged so the documented dry-run exit-0 contract holds.")
