# Decision Moment `01M728CNY28WDPTR69B6VWQZ00`

- **Mission:** `quick-win-remediation-01M72855`
- **Origin flow:** `plan`
- **Slot key:** `plan.topology.settlement`
- **Input key:** `topology`
- **Status:** `resolved`
- **Created:** `2026-11-10T08:15:01.058083+00:00`
- **Resolved:** `2026-11-10T08:15:02.382264+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Should dependencies be made artificially linear to keep the Mission single_branch?

## Options

- No: declare only real dependencies (WP05 on WP02) and let finalize-tasks settle topology by size
- Yes: chain all WPs linearly
- Other

## Final answer

No. Declare only the real dependency (WP05 depends on WP02). finalize-tasks settles the topology by size (ADR 2026-11-06-3); with four independent code WPs it is expected to settle lanes_with_coord. Artificial dependencies would misstate the work and serialise independent reviews.

## Rationale

_(none)_

## Change log

- `2026-11-10T08:15:01.058083+00:00` - opened
- `2026-11-10T08:15:02.382264+00:00` - resolved (final_answer="No. Declare only the real dependency (WP05 depends on WP02). finalize-tasks settles the topology by size (ADR 2026-11-06-3); with four independent code WPs it is expected to settle lanes_with_coord. Artificial dependencies would misstate the work and serialise independent reviews.")
