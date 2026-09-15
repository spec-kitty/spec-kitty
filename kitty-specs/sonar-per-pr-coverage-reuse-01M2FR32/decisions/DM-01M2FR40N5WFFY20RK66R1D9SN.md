# Decision Moment `01M2FR40N5WFFY20RK66R1D9SN`

- **Mission:** `sonar-per-pr-coverage-reuse-01M2FR32`
- **Origin flow:** `specify`
- **Slot key:** `specify.topology.scan-home`
- **Input key:** `scan_home`
- **Status:** `resolved`
- **Created:** `2026-09-14T10:41:32.837803+00:00`
- **Resolved:** `2026-09-14T10:44:01.231953+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Where should the per-PR SonarCloud scan live once it stops re-running the fast tier?

## Options

- New job in ci-aggregate.yml
- New sonar-pr.yml workflow
- Extend sonar.yml with a workflow_run trigger
- Other

## Final answer

New job in ci-aggregate.yml, needs: collect. Rides the existing workflow_run:[CI Modules] chain and consumes the already-published ci-aggregate-reconciled-coverage + ci-aggregate-source artefacts; inherits that file's workflow_dispatch + mode input so test_dual_mode_contract gates it with no new candidate-tuple entry.

## Rationale

_(none)_

## Change log

- `2026-09-14T10:41:32.837803+00:00` — opened
- `2026-09-14T10:44:01.231953+00:00` — resolved (final_answer="New job in ci-aggregate.yml, needs: collect. Rides the existing workflow_run:[CI Modules] chain and consumes the already-published ci-aggregate-reconciled-coverage + ci-aggregate-source artefacts; inherits that file's workflow_dispatch + mode input so test_dual_mode_contract gates it with no new candidate-tuple entry.")
