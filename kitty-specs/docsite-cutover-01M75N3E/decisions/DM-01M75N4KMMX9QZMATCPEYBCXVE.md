# Decision Moment `01M75N4KMMX9QZMATCPEYBCXVE`

- **Mission:** `docsite-cutover-01M75N3E`
- **Origin flow:** `specify`
- **Slot key:** `specify.rules.rollback`
- **Input key:** `rollback_invariants`
- **Status:** `resolved`
- **Created:** `2026-11-11T15:55:31.348660+00:00`
- **Resolved:** `2026-11-11T15:55:33.788351+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

What must always hold, and what must a revert restore?

## Options

_(none)_

## Final answer

Deploy stays main-only and core-repository-only behind the pages probe-then-configure job, the pages concurrency group, least-privilege permissions and SHA pins; a failed doc-kitty build blocks the deploy; nothing publishes from a fork or off main. Rollback is reverting the PR (ADR D-13 step 4): the DocFX build path, docfx.json, toc.yml, the template and the DocFX scripts stay in the tree until #6943, and a revert restores the DocFX build and deploy jobs, the canary jobs and docs/llms.txt. docs/llms.txt is deleted with every live reference; immutable history is untouched. Answered from the operator brief.

## Rationale

_(none)_

## Change log

- `2026-11-11T15:55:31.348660+00:00` - opened
- `2026-11-11T15:55:33.788351+00:00` - resolved (final_answer="Deploy stays main-only and core-repository-only behind the pages probe-then-configure job, the pages concurrency group, least-privilege permissions and SHA pins; a failed doc-kitty build blocks the deploy; nothing publishes from a fork or off main. Rollback is reverting the PR (ADR D-13 step 4): the DocFX build path, docfx.json, toc.yml, the template and the DocFX scripts stay in the tree until #6943, and a revert restores the DocFX build and deploy jobs, the canary jobs and docs/llms.txt. docs/llms.txt is deleted with every live reference; immutable history is untouched. Answered from the operator brief.")
