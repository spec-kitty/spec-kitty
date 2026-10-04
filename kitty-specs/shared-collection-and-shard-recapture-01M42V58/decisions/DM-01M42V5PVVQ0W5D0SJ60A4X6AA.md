# Decision Moment `01M42V5PVVQ0W5D0SJ60A4X6AA`

- **Mission:** `shared-collection-and-shard-recapture-01M42V58`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.collection-sharing-boundary`
- **Input key:** `collection_sharing_boundary`
- **Status:** `resolved`
- **Created:** `2026-10-04T06:56:10.107911+00:00`
- **Resolved:** `2026-10-04T06:56:17.805294+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

The per-PR jobs each run collect_universe() exactly once on separate runners, so a worker-shared cache does not move the cited setup time. How should the mission treat #5559?

## Options

- Re-scope to cross-job sharing
- Implement as written with an honest claim
- Drop #5559 from the mission
- Other

## Final answer

Re-scope to cross-job sharing

## Rationale

_(none)_

## Change log

- `2026-10-04T06:56:10.107911+00:00` — opened
- `2026-10-04T06:56:17.805294+00:00` — resolved (final_answer="Re-scope to cross-job sharing")
