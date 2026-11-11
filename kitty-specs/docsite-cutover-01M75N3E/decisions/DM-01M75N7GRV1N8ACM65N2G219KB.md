# Decision Moment `01M75N7GRV1N8ACM65N2G219KB`

- **Mission:** `docsite-cutover-01M75N3E`
- **Origin flow:** `plan`
- **Slot key:** `plan.architecture.canary-and-docfx`
- **Input key:** `canary_and_docfx_fate`
- **Status:** `resolved`
- **Created:** `2026-11-11T15:57:06.715865+00:00`
- **Resolved:** `2026-11-11T15:57:09.243870+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

What happens to the canary jobs and to the DocFX build in docs-pages.yml?

## Options

_(none)_

## Final answer

One live-probe mechanism: the canary jobs (canary-build, canary-deploy, canary-probe) and the canary dispatch input are removed; the post-deploy smoketest reuses the same probe on every deploy, so a canary of the current site would be a second, redundant path. The DocFX build job is removed from docs-pages.yml as well: it would build a site nothing publishes, and a DocFX failure would turn a successful doc-kitty deploy red. The DocFX sources (docfx.json, toc.yml, the template, scripts and their tests) stay until #6943; a revert of this PR restores the DocFX build and deploy jobs and the canary. Brief-derived engineering decision.

## Rationale

_(none)_

## Change log

- `2026-11-11T15:57:06.715865+00:00` - opened
- `2026-11-11T15:57:09.243870+00:00` - resolved (final_answer="One live-probe mechanism: the canary jobs (canary-build, canary-deploy, canary-probe) and the canary dispatch input are removed; the post-deploy smoketest reuses the same probe on every deploy, so a canary of the current site would be a second, redundant path. The DocFX build job is removed from docs-pages.yml as well: it would build a site nothing publishes, and a DocFX failure would turn a successful doc-kitty deploy red. The DocFX sources (docfx.json, toc.yml, the template, scripts and their tests) stay until #6943; a revert of this PR restores the DocFX build and deploy jobs and the canary. Brief-derived engineering decision.")
