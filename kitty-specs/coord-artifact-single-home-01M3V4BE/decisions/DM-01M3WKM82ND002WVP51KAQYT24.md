# Decision Moment `01M3WKM82ND002WVP51KAQYT24`

- **Mission:** `coord-artifact-single-home-01M3V4BE`
- **Origin flow:** `plan`
- **Slot key:** `plan.design.published-status-state-write`
- **Input key:** `published_status_state_write`
- **Status:** `resolved`
- **Created:** `2026-10-01T20:48:51.285504+00:00`
- **Resolved:** `2026-10-01T20:48:53.390466+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Where does a STATUS_STATE append go for a consolidated (PUBLISHED) coordination Mission whose coordination branch was deleted (retrospect create after merge)?

## Options

_(none)_

## Final answer

Extend D23 in the single accessor: for a PUBLISHED Mission, write_dir(STATUS_STATE) resolves to the target-branch surface (same composition as the E2 consolidated kinds), and the commit router commits it on the target branch. One shared PUBLISHED predicate for write_dir and the router's commit ref; pre-consolidation behaviour unchanged. Implemented in WP14 (declared out-of-map edits to resolution.py / commit routing), red-first.

## Rationale

_(none)_

## Change log

- `2026-10-01T20:48:51.285504+00:00` — opened
- `2026-10-01T20:48:53.390466+00:00` — resolved (final_answer="Extend D23 in the single accessor: for a PUBLISHED Mission, write_dir(STATUS_STATE) resolves to the target-branch surface (same composition as the E2 consolidated kinds), and the commit router commits it on the target branch. One shared PUBLISHED predicate for write_dir and the router's commit ref; pre-consolidation behaviour unchanged. Implemented in WP14 (declared out-of-map edits to resolution.py / commit routing), red-first.")
