# Decision Moment `01M2FXP9W8KN9BF99PCX1WFAB8`

- **Mission:** `sonar-per-pr-coverage-reuse-01M2FR32`
- **Origin flow:** `plan`
- **Slot key:** `plan.reliability.nonblocking-seam`
- **Input key:** `nonblocking_seam`
- **Status:** `resolved`
- **Created:** `2026-09-14T12:18:54.984867+00:00`
- **Resolved:** `2026-09-14T12:22:26.366533+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

NFR-003: how is never-merge-blocking enforced in the new home, given ci-aggregate.yml has no verdict job and fleet_verdict.py turns its failures into a red PR verdict?

## Options

- Terminal verdict job excluding Sonar
- Allowlist the job in fleet_verdict.py
- Declare it rests on branch protection
- Other

## Final answer

Add a terminal verdict job to ci-aggregate.yml mirroring ci-quality.yml's quality-gate pattern, evaluating results and explicitly excluding the Sonar job. This gives the workflow a declarable non-blocking seam analogous to NON_BLOCKING_ALLOWLIST, so SC-006's 'under any outcome' is rule-assertable rather than resting on branch-protection configuration.

## Rationale

_(none)_

## Change log

- `2026-09-14T12:18:54.984867+00:00` — opened
- `2026-09-14T12:22:26.366533+00:00` — resolved (final_answer="Add a terminal verdict job to ci-aggregate.yml mirroring ci-quality.yml's quality-gate pattern, evaluating results and explicitly excluding the Sonar job. This gives the workflow a declarable non-blocking seam analogous to NON_BLOCKING_ALLOWLIST, so SC-006's 'under any outcome' is rule-assertable rather than resting on branch-protection configuration.")
