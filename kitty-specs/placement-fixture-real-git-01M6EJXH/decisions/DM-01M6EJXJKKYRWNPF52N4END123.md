# Decision Moment `01M6EJXJKKYRWNPF52N4END123`

- **Mission:** `placement-fixture-real-git`
- **Origin flow:** `specify`
- **Step id:** `specify.problem_statement`
- **Input key:** `problem_statement`
- **Status:** `resolved`
- **Created:** `2026-11-02T16:54:11.827594+00:00`
- **Resolved:** `2026-11-02T16:55:59.094915+00:00`
- **Resolved by:** `Ivan-Melck`
- **Opened by:** `22272470+Ivan-Melck@users.noreply.github.com`
- **Other answer:** `false`

## Question

What problem does this Mission solve?

## Options

_(none)_

## Final answer

The placement test's bare .git marker trips the #6673 tracked-meta refusal (TRACKED_META_UNAVAILABLE) before the placement check, so test_mismatched_feature_dir_fails_closed_without_writing never reaches PlacementMismatchError; the fixture must be a real git repo.

## Rationale

Evidence in research.md D1/D2, including a probe of both fixture shapes.

## Change log

- `2026-11-02T16:54:11.827594+00:00` — opened
- `2026-11-02T16:55:59.094915+00:00` — resolved (final_answer="The placement test's bare .git marker trips the #6673 tracked-meta refusal (TRACKED_META_UNAVAILABLE) before the placement check, so test_mismatched_feature_dir_fails_closed_without_writing never reaches PlacementMismatchError; the fixture must be a real git repo.")
