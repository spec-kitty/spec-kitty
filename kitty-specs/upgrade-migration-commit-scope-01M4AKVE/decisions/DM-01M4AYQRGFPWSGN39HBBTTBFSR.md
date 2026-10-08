# Decision Moment `01M4AYQRGFPWSGN39HBBTTBFSR`

- **Mission:** `upgrade-migration-commit-scope-01M4AKVE`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.manual-review-commit`
- **Input key:** `manual_review_commit`
- **Status:** `resolved`
- **Created:** `2026-10-07T10:32:22.799763+00:00`
- **Resolved:** `2026-10-07T11:45:25.768254+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

After the fix the schema-3 migration's writes are committed only by upgrade's finalizer, which skips the whole commit when the upgrade preserved customised files for manual review (triggered on a realistic legacy fixture by shims the migration itself wrote). What should happen?

## Options

- commit tool-written clean paths except the files under review, warn about the rest
- leave everything uncommitted and list each suppressing condition in the warning
- Other

## Final answer

per validation squad (operator steer): fix the false flag (only a missing version marker means user-authored) AND commit tool-written clean paths except files genuinely held for review, naming them

## Rationale

_(none)_

## Change log

- `2026-10-07T10:32:22.799763+00:00` — opened
- `2026-10-07T11:45:25.768254+00:00` — resolved (final_answer="per validation squad (operator steer): fix the false flag (only a missing version marker means user-authored) AND commit tool-written clean paths except files genuinely held for review, naming them")
