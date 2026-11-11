# Decision Moment `01M75N4A07HT273XMSQW21JCJ5`

- **Mission:** `docsite-cutover-01M75N3E`
- **Origin flow:** `specify`
- **Slot key:** `specify.scenario.actor-trigger`
- **Input key:** `cutover_trigger`
- **Status:** `resolved`
- **Created:** `2026-11-11T15:55:21.479317+00:00`
- **Resolved:** `2026-11-11T15:55:23.929717+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

What publishes the docsite after cutover, and when?

## Options

_(none)_

## Final answer

Every push to main that touches a docsite input, and a plain workflow_dispatch, runs docs-pages.yml: the pages probe, then the doc-kitty build from the shared docs-site-build.yml with pages-artifact true, then the deploy from main of the core repository only, then the post-deploy smoketest. DocFX is no longer built or published by this workflow. Answered from the operator brief for #6938 PR B.

## Rationale

_(none)_

## Change log

- `2026-11-11T15:55:21.479317+00:00` - opened
- `2026-11-11T15:55:23.929717+00:00` - resolved (final_answer="Every push to main that touches a docsite input, and a plain workflow_dispatch, runs docs-pages.yml: the pages probe, then the doc-kitty build from the shared docs-site-build.yml with pages-artifact true, then the deploy from main of the core repository only, then the post-deploy smoketest. DocFX is no longer built or published by this workflow. Answered from the operator brief for #6938 PR B.")
