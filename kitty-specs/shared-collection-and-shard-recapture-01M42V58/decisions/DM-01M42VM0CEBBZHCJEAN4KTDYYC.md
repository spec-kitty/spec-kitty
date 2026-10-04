# Decision Moment `01M42VM0CEBBZHCJEAN4KTDYYC`

- **Mission:** `shared-collection-and-shard-recapture-01M42V58`
- **Origin flow:** `specify`
- **Slot key:** `specify.design.sharing-transport`
- **Input key:** `sharing_transport`
- **Status:** `resolved`
- **Created:** `2026-10-04T07:03:58.606647+00:00`
- **Resolved:** `2026-10-04T07:04:01.784574+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

The battery legs (ci-router.yml, Python 3.12) and the ci shard (ci-modules.yml, Python 3.11) run in independent workflows, so one collection per run cannot span all three consumers. Which design should the mission build?

## Options

- Uncontended pre-step in each consuming job
- Producer job for the battery legs
- Local store only
- Other

## Final answer

Uncontended pre-step in each consuming job

## Rationale

_(none)_

## Change log

- `2026-10-04T07:03:58.606647+00:00` — opened
- `2026-10-04T07:04:01.784574+00:00` — resolved (final_answer="Uncontended pre-step in each consuming job")
