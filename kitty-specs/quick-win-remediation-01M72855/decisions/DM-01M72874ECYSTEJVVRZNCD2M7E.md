# Decision Moment `01M72874ECYSTEJVVRZNCD2M7E`

- **Mission:** `quick-win-remediation-01M72855`
- **Origin flow:** `specify`
- **Slot key:** `specify.glossary.rescan`
- **Input key:** `glossary_rescan`
- **Status:** `resolved`
- **Created:** `2026-11-10T08:11:59.308730+00:00`
- **Resolved:** `2026-11-10T08:12:00.621232+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

#7463: how is the quadratic conflict rescan fixed and proven?

## Options

- Hoist the existing-id set out of the loop and add each appended id, preserving de-duplication; deterministic tests only, timings recorded in the PR
- Add a wall-clock performance test
- Other

## Final answer

Build the set of known conflict ids once before the resolved-event pass and add each newly appended id to it, so a repeated resolved event still yields one conflict (dedup preserved). Proof is deterministic: a characterisation test for repeated resolved ids and a scale test asserting 2n conflicts for n requested plus n resolved. No wall-clock performance test; before/after timings are recorded in the PR body.

## Rationale

_(none)_

## Change log

- `2026-11-10T08:11:59.308730+00:00` - opened
- `2026-11-10T08:12:00.621232+00:00` - resolved (final_answer="Build the set of known conflict ids once before the resolved-event pass and add each newly appended id to it, so a repeated resolved event still yields one conflict (dedup preserved). Proof is deterministic: a characterisation test for repeated resolved ids and a scale test asserting 2n conflicts for n requested plus n resolved. No wall-clock performance test; before/after timings are recorded in the PR body.")
