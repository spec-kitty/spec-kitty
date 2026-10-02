# Decision Moment `01M3VE9CTR20T4ME1K6KHKABRX`

- **Mission:** `coord-artifact-single-home-01M3V4BE`
- **Origin flow:** `plan`
- **Slot key:** `plan.design.topology-less-callers`
- **Input key:** `topology_less_callers`
- **Status:** `resolved`
- **Created:** `2026-10-01T09:56:18.392802+00:00`
- **Resolved:** `2026-10-01T09:56:20.356789+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How are topology-less residue callers handled after the ledger reclassification (analyze I8)?

## Options

_(none)_

## Final answer

WP12 single-predicate design: coherence.py resolves the stored topology from the slug when topology is None; lanes/single_branch keep today's verdict (C-008); coordination Missions get the PRIMARY ledger rule at every caller. No _TOPOLOGY_LESS_LEGACY_RESIDUE_KINDS set. Add coordination-Mission tests at move-task, implement and auto-rebase for the now-PRIMARY ledger. Design docs follow.

## Rationale

_(none)_

## Change log

- `2026-10-01T09:56:18.392802+00:00` — opened
- `2026-10-01T09:56:20.356789+00:00` — resolved (final_answer="WP12 single-predicate design: coherence.py resolves the stored topology from the slug when topology is None; lanes/single_branch keep today's verdict (C-008); coordination Missions get the PRIMARY ledger rule at every caller. No _TOPOLOGY_LESS_LEGACY_RESIDUE_KINDS set. Add coordination-Mission tests at move-task, implement and auto-rebase for the now-PRIMARY ledger. Design docs follow.")
