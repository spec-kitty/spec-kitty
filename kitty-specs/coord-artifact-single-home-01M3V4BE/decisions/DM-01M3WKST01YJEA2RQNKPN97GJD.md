# Decision Moment `01M3WKST01YJEA2RQNKPN97GJD`

- **Mission:** `coord-artifact-single-home-01M3V4BE`
- **Origin flow:** `plan`
- **Slot key:** `plan.design.owning-copy-flip-allocation`
- **Input key:** `owning_copy_flip_allocation`
- **Status:** `resolved`
- **Created:** `2026-10-01T20:51:53.473872+00:00`
- **Resolved:** `2026-10-01T20:51:55.067239+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Who implements the router-side 'owning coordination copy wins' flip for TRACER_FILE/REVIEW_CYCLE/ISSUE_MATRIX/ACCEPTANCE_MATRIX, given commit_router.py is already edited in three lanes (amends plan.design.translate-if-present-kinds)?

## Options

_(none)_

## Final answer

Writer WPs (WP08 review-cycle, WP10 tracer+issue-matrix, WP15 acceptance-matrix finalize, WP16 accept matrix leg) migrate their writers to write in place via write_dir and pass ONLY the owning (coordination) path to the router — never the root copy — so the legacy copy2 never fires for their kind. The single router-side flip (drop copy2 / owning copy wins for all four kinds) is done once in WP20, whose lane depends on every writer lane; the four B1 regression guards must stay green. No writer WP edits commit_router.py for this.

## Rationale

_(none)_

## Change log

- `2026-10-01T20:51:53.473872+00:00` — opened
- `2026-10-01T20:51:55.067239+00:00` — resolved (final_answer="Writer WPs (WP08 review-cycle, WP10 tracer+issue-matrix, WP15 acceptance-matrix finalize, WP16 accept matrix leg) migrate their writers to write in place via write_dir and pass ONLY the owning (coordination) path to the router — never the root copy — so the legacy copy2 never fires for their kind. The single router-side flip (drop copy2 / owning copy wins for all four kinds) is done once in WP20, whose lane depends on every writer lane; the four B1 regression guards must stay green. No writer WP edits commit_router.py for this.")
