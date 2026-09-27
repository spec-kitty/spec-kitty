# Decision Moment `01M3GM85PM3D5R1FT5TRW8F1Z3`

- **Mission:** `review-feedback-to-implementer-01M3GKZ8`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.mission-scope`
- **Input key:** `mission_scope`
- **Status:** `resolved`
- **Created:** `2026-09-27T05:08:51.028116+00:00`
- **Resolved:** `2026-09-27T05:14:02.485233+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

What is the in-scope behavioral change for this mission?

## Options

_(none)_

## Final answer

In scope: issues #4899 and #5024 only. (#4899) The rejection edge that moves a work package from in_review to in_progress must produce the SAME durable feedback record as the in_review-to-planned edge — a committed review-cycle artifact, a set feedback path, and a resolvable reference — and a rejection carrying no rationale on that edge must be refused. (#5024) Once feedback is persisted, the regenerated implementer prompt must carry it; a fix-mode prompt-regeneration failure must emit a visible warning instead of silently falling back to a feedback-less prompt, and feedback must render into the regenerated prompt on both single-branch and coordination topologies. The existing synthetic-marker/resolvable-pointer vocabulary is reused unchanged.

## Rationale

_(none)_

## Change log

- `2026-09-27T05:08:51.028116+00:00` — opened
- `2026-09-27T05:14:02.485233+00:00` — resolved (final_answer="In scope: issues #4899 and #5024 only. (#4899) The rejection edge that moves a work package from in_review to in_progress must produce the SAME durable feedback record as the in_review-to-planned edge — a committed review-cycle artifact, a set feedback path, and a resolvable reference — and a rejection carrying no rationale on that edge must be refused. (#5024) Once feedback is persisted, the regenerated implementer prompt must carry it; a fix-mode prompt-regeneration failure must emit a visible warning instead of silently falling back to a feedback-less prompt, and feedback must render into the regenerated prompt on both single-branch and coordination topologies. The existing synthetic-marker/resolvable-pointer vocabulary is reused unchanged.")
