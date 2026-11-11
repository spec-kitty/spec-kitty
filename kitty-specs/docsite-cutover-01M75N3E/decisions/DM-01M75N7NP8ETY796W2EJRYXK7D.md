# Decision Moment `01M75N7NP8ETY796W2EJRYXK7D`

- **Mission:** `docsite-cutover-01M75N3E`
- **Origin flow:** `plan`
- **Slot key:** `plan.security.permissions`
- **Input key:** `least_privilege_layout`
- **Status:** `resolved`
- **Created:** `2026-11-11T15:57:11.752398+00:00`
- **Resolved:** `2026-11-11T15:57:14.241606+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How are token permissions laid out?

## Options

_(none)_

## Final answer

Workflow default contents: read. pages job: pages: read (GET the Pages site and configure-pages without enablement read only). build job (calls the shared build): contents: read. deploy: pages: write and id-token: write, nothing else. smoketest: contents: read. Brief-derived engineering decision.

## Rationale

_(none)_

## Change log

- `2026-11-11T15:57:11.752398+00:00` - opened
- `2026-11-11T15:57:14.241606+00:00` - resolved (final_answer="Workflow default contents: read. pages job: pages: read (GET the Pages site and configure-pages without enablement read only). build job (calls the shared build): contents: read. deploy: pages: write and id-token: write, nothing else. smoketest: contents: read. Brief-derived engineering decision.")
