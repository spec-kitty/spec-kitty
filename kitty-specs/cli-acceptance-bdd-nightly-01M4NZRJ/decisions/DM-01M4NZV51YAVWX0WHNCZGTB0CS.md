# Decision Moment `01M4NZV51YAVWX0WHNCZGTB0CS`

- **Mission:** `cli-acceptance-bdd-nightly-01M4NZRJ`
- **Origin flow:** `specify`
- **Slot key:** `specify.scenarios.seed-tag-posture`
- **Input key:** `seed_scenario_tag_posture`
- **Status:** `resolved`
- **Created:** `2026-10-11T17:23:21.278735+00:00`
- **Resolved:** `2026-10-11T17:25:04.896303+00:00`
- **Opened by:** `cli`
- **Other answer:** `true`

## Question

How should the two seed init scenarios be tagged, given core gives tags no meaning beyond the nightly 'not @wip and not @manual' filter and the promise index is out of core scope?

## Options

- Bound and untagged — run in the gating nightly from day one
- Bound with inert @promise tags for QA to map later
- Land as @wip — only the non-gating run executes them

## Final answer

The two seed init scenarios land bound and untagged, so they run in the gating 'not @wip and not @manual' nightly from day one (they are lightweight: each runs spec-kitty init in a temp repo and asserts). @manual is an allowed tag reserved for heavy or on-demand scenarios added later; core gives @manual, like @wip, no meaning beyond excluding the scenario from the gating nightly run. The bound-vs-@manual choice for future scenarios depends on their runtime cost.

## Rationale

_(none)_

## Change log

- `2026-10-11T17:23:21.278735+00:00` — opened
- `2026-10-11T17:25:04.896303+00:00` — resolved (final_answer="The two seed init scenarios land bound and untagged, so they run in the gating 'not @wip and not @manual' nightly from day one (they are lightweight: each runs spec-kitty init in a temp repo and asserts). @manual is an allowed tag reserved for heavy or on-demand scenarios added later; core gives @manual, like @wip, no meaning beyond excluding the scenario from the gating nightly run. The bound-vs-@manual choice for future scenarios depends on their runtime cost.")
