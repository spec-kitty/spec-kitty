# Decision Moment `01M3W6J63JSPT07CRQN7FEHSW4`

- **Mission:** `coord-artifact-single-home-01M3V4BE`
- **Origin flow:** `plan`
- **Slot key:** `plan.design.translate-if-present-kinds`
- **Input key:** `translate_if_present_kinds`
- **Status:** `resolved`
- **Created:** `2026-10-01T17:00:32.242399+00:00`
- **Resolved:** `2026-10-01T17:00:33.846106+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

During migration, how does the commit router treat TRACER_FILE / REVIEW_CYCLE / ISSUE_MATRIX / ACCEPTANCE_MATRIX passed by repository-root path when the coordination copy exists (WP05 review B1)?

## Options

_(none)_

## Final answer

Keep the legacy root-to-coordination overwrite (copy2) for these four kinds in WP05 (behaviour-preserving, no data loss while their writers still write the root copy). The 'owning copy wins' rule moves into the WP that migrates each writer to write in place via write_dir: review-cycle -> WP08, tracer + issue-matrix -> WP10, acceptance-matrix (finalize) -> WP15. STATUS_LOG and DECISION_LOG keep owning-surface translation via write_dir in WP05.

## Rationale

_(none)_

## Change log

- `2026-10-01T17:00:32.242399+00:00` — opened
- `2026-10-01T17:00:33.846106+00:00` — resolved (final_answer="Keep the legacy root-to-coordination overwrite (copy2) for these four kinds in WP05 (behaviour-preserving, no data loss while their writers still write the root copy). The 'owning copy wins' rule moves into the WP that migrates each writer to write in place via write_dir: review-cycle -> WP08, tracer + issue-matrix -> WP10, acceptance-matrix (finalize) -> WP15. STATUS_LOG and DECISION_LOG keep owning-surface translation via write_dir in WP05.")
