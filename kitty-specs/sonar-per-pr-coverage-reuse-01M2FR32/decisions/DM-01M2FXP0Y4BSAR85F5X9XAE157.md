# Decision Moment `01M2FXP0Y4BSAR85F5X9XAE157`

- **Mission:** `sonar-per-pr-coverage-reuse-01M2FR32`
- **Origin flow:** `plan`
- **Slot key:** `plan.coverage.breadth-fix`
- **Input key:** `coverage_breadth_fix`
- **Status:** `resolved`
- **Created:** `2026-09-14T12:18:45.828093+00:00`
- **Resolved:** `2026-09-14T12:21:54.554678+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How should the per-module coverage breadth be corrected (FR-013)?

## Options

- Broaden every row to top-level packages
- Broaden only orphaned packages
- Add a second broad-target row
- Other

## Final answer

Broaden every registry row's cov_targets to the top-level packages it can reach. Coverage XMLs merge by union (a line covered in any report wins), so this is correct by construction and needs no per-package mapping to maintain. Accepted cost: coverage.py traces more code per shard, so shard runtime and XML size grow; NFR-002 requires this be measured, not assumed.

## Rationale

_(none)_

## Change log

- `2026-09-14T12:18:45.828093+00:00` — opened
- `2026-09-14T12:21:54.554678+00:00` — resolved (final_answer="Broaden every registry row's cov_targets to the top-level packages it can reach. Coverage XMLs merge by union (a line covered in any report wins), so this is correct by construction and needs no per-package mapping to maintain. Accepted cost: coverage.py traces more code per shard, so shard runtime and XML size grow; NFR-002 requires this be measured, not assumed.")
