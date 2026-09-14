# Decision Moment `01M2FR4CFQSYX0RSGX02S3ZZ9W`

- **Mission:** `sonar-per-pr-coverage-reuse-01M2FR32`
- **Origin flow:** `specify`
- **Slot key:** `specify.security.untrusted-source-posture`
- **Input key:** `untrusted_source_posture`
- **Status:** `resolved`
- **Created:** `2026-09-14T10:41:44.951788+00:00`
- **Resolved:** `2026-09-14T10:44:30.228730+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

A Sonar scan must read the PR's source tree, but ci-aggregate.yml deliberately never checks out PR code and would hold SONAR_TOKEN. What posture should the mission take?

## Options

- Trusted config + sandboxed PR sources
- Same-repo PRs only, no fork decoration
- Defer to a follow-up issue
- Other

## Final answer

Same-repo PRs only, no fork decoration. Fork PRs get no Sonar today (SONAR_TOKEN is empty on fork pull_request events), so the blast radius stays at today's level and nothing regresses; fork-PR Sonar is a separately-reasoned follow-up, not a side effect of this change.

## Rationale

_(none)_

## Change log

- `2026-09-14T10:41:44.951788+00:00` — opened
- `2026-09-14T10:44:30.228730+00:00` — resolved (final_answer="Same-repo PRs only, no fork decoration. Fork PRs get no Sonar today (SONAR_TOKEN is empty on fork pull_request events), so the blast radius stays at today's level and nothing regresses; fork-PR Sonar is a separately-reasoned follow-up, not a side effect of this change.")
